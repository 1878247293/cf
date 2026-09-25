// mp_server.js — 零依赖 Node 联机服务器（服务器权威记账 + 聚合 world 快照下发）
// 启动:  PORT=8080 node mp_server.js
// 玩家:  打开 http://<服务器IP或域名>:PORT/  （会自动跳到 ?mp=1）
// 模型:  服务器权威「记账状态」——花名册 / 分数 / K-D 统计 / 房间回合 / bot 归属，
//        并把各客户端上报的实体快照聚合成一份 world 按 tick 下发（O(N)，替代旧的 O(N²) 哑中继）。
//        服务器**不跑物理/AI**（物理与 AI 仍在客户端；bot 由房主客户端模拟，掉线自动移交新房主）。
const http = require("http");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 8080;
const BUILD_V = Date.now(); // 每次启动生成新版本号，作缓存指纹，绕过 CDN 旧缓存
const PING_EVERY = 20000;   // 服务端心跳周期
const IDLE_KICK = 90000;    // 超过此时长无任何数据（含 pong）视为掉线
const TICK_MS = 50;         // world 聚合快照下发频率（20Hz）
const KEYFRAME_EVERY = 20;  // 每 20 tick(~1s) 发一次全量关键帧（热加入初始态 + 漂移校正）
const HTML = path.join(__dirname, "transport-ship-lockon.html");
const GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

const clients = new Map(); // slot -> {sock, slot, name, team, host, last}（Map 保序 → 房主顺延给最早进来的）
const scores = { BL: 0, GR: 0 };
const stats = new Map();   // netId -> {k, d, hs}   （权威 K/D/爆头，frag 事件唯一累加）
const world = new Map();   // netId -> 最新快照（来自各实体属主：真人报自己、房主报 bot）
let roomCfg = { size: 5, diff: "normal", goal: 50, tod: "day" };
let roomState = "lobby";   // lobby=大厅；playing=对局进行中
let changed = new Set();   // 自上次 tick 起有更新的 netId（增量下发用）
let tickSeq = 0, kfCount = 0;
let forceKeyframe = false;  // 换房主/掉线迁移后置位：下一 tick 强制全量下发，新房主据此立刻收编所有 bot（免最长 1s 冻结窗口）

// 玩家名用「最小空闲编号」：在场编号不变，空号留给下一个进来的人。slot 即 netId。
function lowestFreeSlot() { let n = 1; while (clients.has(n)) n++; return n; }
function statOf(id) { let s = stats.get(id); if (!s) { s = { k: 0, d: 0, hs: 0 }; stats.set(id, s); } return s; }
function statsObj() { const o = {}; for (const [id, s] of stats) o[id] = s; return o; }

const server = http.createServer((req, res) => {
  const u = (req.url || "/").split("?")[0];
  // 静态文件一律 no-store：游戏页经常更新，若不禁缓存，边缘 CDN 会把旧版 HTML 缓存住（踩过的坑）。
  const NO_STORE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
  };
  if (u === "/") {
    res.writeHead(302, { Location: "/transport-ship-lockon.html?mp=1&v=" + BUILD_V, ...NO_STORE });
    res.end();
    return;
  }
  if (u === "/transport-ship-lockon.html") {
    fs.readFile(HTML, (err, buf) => {
      if (err) { res.writeHead(404); res.end("build transport-ship-lockon.html first"); return; }
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", ...NO_STORE });
      res.end(buf);
    });
    return;
  }
  res.writeHead(404);
  res.end("not found");
});
server.on("upgrade", (req, socket) => {
  const key = req.headers["sec-websocket-key"];
  if (!key) { socket.destroy(); return; }
  const accept = crypto.createHash("sha1").update(key + GUID).digest("base64");
  socket.write(
    "HTTP/1.1 101 Switching Protocols\r\n" +
    "Upgrade: websocket\r\nConnection: Upgrade\r\n" +
    "Sec-WebSocket-Accept: " + accept + "\r\n\r\n"
  );
  onConnect(socket);
});

function sendFrame(sock, str, opcode) {
  opcode = opcode || 0x1;
  const payload = Buffer.from(str, "utf8");
  const len = payload.length;
  let header;
  if (len < 126) { header = Buffer.alloc(2); header[1] = len; }
  else if (len < 65536) { header = Buffer.alloc(4); header[1] = 126; header.writeUInt16BE(len, 2); }
  else { header = Buffer.alloc(10); header[1] = 127; header.writeBigUInt64BE(BigInt(len), 2); }
  header[0] = 0x80 | opcode;
  try { sock.write(Buffer.concat([header, payload])); } catch (e) {}
}
function send(client, obj) { sendFrame(client.sock, JSON.stringify(obj)); }
function broadcast(obj, exceptSlot) {
  const s = JSON.stringify(obj);
  for (const c of clients.values()) if (c.slot !== exceptSlot) sendFrame(c.sock, s);
}
function broadcastRoster() {
  const players = [...clients.values()].map((c) => ({ slot: c.slot, name: c.name, team: c.team, host: c.host }));
  broadcast({ t: "roster", players });
}
// 把当前所有 bot（netId>=1000）的归属指派给房主客户端：新房主据此把手里的远程化身收编为本地 bot 续算。
function assignBots(host) {
  if (!host) return;
  const ids = [];
  for (const id of world.keys()) if (id >= 1000) ids.push(id);
  send(host, { t: "botsassign", ids });
  forceKeyframe = true; // 迁移后强制下一 tick 全量：新房主立刻拿到全部 bot 快照并收编，不用等下一个关键帧
}

function handleMsg(client, str) {
  let m;
  try { m = JSON.parse(str); } catch (e) { return; }
  switch (m.t) {
    case "join":
      client.team = m.team === "GR" ? "GR" : "BL";
      statOf(client.slot);
      broadcastRoster();
      return;
    case "state": {
      // 客户端上报自己拥有的实体（真人=自己 slot；房主=全部 bot）。服务器存入 world，按 tick 聚合下发。
      if (!Array.isArray(m.ents)) return;
      for (const sn of m.ents) {
        if (!sn || sn.id == null) continue;
        if (sn.id < 1000) { if (sn.id !== client.slot) continue; } // 真人只能报自己
        else if (!client.host) continue;                           // bot 只能由房主报
        world.set(sn.id, sn);
        changed.add(sn.id);
      }
      return;
    }
    case "fire":
      m.from = client.slot;
      broadcast(m, client.slot); // 纯视听中继
      return;
    case "hit":
      m.from = client.slot;
      broadcast(m, client.slot); // 定向给受害者属主（客户端按 target 过滤）
      return;
    case "frag": {
      // 服务器权威计分：K/D/爆头/队伍分的**唯一累加点**，然后广播 frag(展示) + stats(权威表) + score。
      const killer = m.killer, victim = m.victim, hs = !!m.hs;
      if (killer && killer !== victim) { const ks = statOf(killer); ks.k++; if (hs) ks.hs++; }
      if (victim != null) statOf(victim).d++;
      const kt = m.killerTeam || m.team;
      if (kt === "BL" || kt === "GR") scores[kt]++;
      broadcast({ t: "frag", killer, victim, hs, w: m.w || "ak47",
        killerName: m.killerName || null, killerTeam: kt || null,
        victimName: m.victimName || null, victimTeam: m.victimTeam || null });
      broadcast({ t: "stats", stats: statsObj() });
      broadcast({ t: "score", BL: scores.BL, GR: scores.GR });
      return;
    }
    case "config":
      if (!client.host || !m.cfg) return;
      if (typeof m.cfg.size === "number") roomCfg.size = Math.max(1, Math.min(8, m.cfg.size | 0));
      if (m.cfg.diff) roomCfg.diff = m.cfg.diff;
      if (typeof m.cfg.goal === "number") roomCfg.goal = m.cfg.goal | 0;
      if (m.cfg.tod) roomCfg.tod = m.cfg.tod;
      broadcast({ t: "config", cfg: roomCfg });
      return;
    case "start":
      if (!client.host) return;
      roomState = "playing";
      scores.BL = 0; scores.GR = 0;
      stats.clear(); world.clear(); changed.clear();
      broadcast({ t: "start", cfg: roomCfg }, client.slot); // 房主自己已从点击手势开局，别人收到后「加入战场」
      broadcast({ t: "score", BL: 0, GR: 0 });
      return;
    case "end":
      if (!client.host) return;
      roomState = "lobby";
      world.clear(); changed.clear();
      broadcast({ t: "end" });
      return;
    case "grabhost": {
      // 任意玩家按 F1 直接抢房主（无限制：大厅或对局进行中均可）。指派 bot 给新房主收编 → 不再冻结。
      // 若抢主者身处大厅（m.end）且有对局在跑 → 顺带终止该对局，把所有人拉回大厅（用户要求）。
      for (const c of clients.values()) c.host = false;
      client.host = true;
      broadcast({ t: "host", slot: client.slot });
      if (m.end && roomState === "playing") {
        roomState = "lobby";
        world.clear(); changed.clear();
        broadcast({ t: "end" });
      }
      assignBots(client);
      broadcastRoster();
      return;
    }
    default:
      m.from = client.slot;
      broadcast(m, client.slot); // 其余消息透传
  }
}

function closeClient(slot) {
  const c = clients.get(slot);
  if (!c) return;
  clients.delete(slot);
  try { c.sock.destroy(); } catch (e) {}
  world.delete(slot); changed.delete(slot); // 移除该真人实体（bot 快照留在 world，待新房主接管）
  if (c.host) {
    const first = [...clients.values()][0];
    if (first) { first.host = true; broadcast({ t: "host", slot: first.slot }); assignBots(first); }
  }
  broadcast({ t: "leave", slot });
  broadcastRoster();
}

function onConnect(sock) {
  const slot = lowestFreeSlot();
  const isHost = ![...clients.values()].some((c) => c.host);
  const client = { sock, slot, name: "玩家" + slot, team: null, host: isHost, last: Date.now() };
  clients.set(slot, client);
  let buf = Buffer.alloc(0);

  sock.on("data", (chunk) => {
    client.last = Date.now(); // 任何数据（含浏览器自动回的 pong）都算存活
    buf = Buffer.concat([buf, chunk]);
    for (;;) {
      if (buf.length < 2) break;
      const b1 = buf[1];
      const opcode = buf[0] & 0x0f;
      const masked = (b1 & 0x80) !== 0;
      let len = b1 & 0x7f;
      let off = 2;
      if (len === 126) { if (buf.length < 4) break; len = buf.readUInt16BE(2); off = 4; }
      else if (len === 127) { if (buf.length < 10) break; len = Number(buf.readBigUInt64BE(2)); off = 10; }
      const need = off + (masked ? 4 : 0) + len;
      if (buf.length < need) break;
      let payload;
      if (masked) {
        const start = off + 4;
        payload = Buffer.alloc(len);
        for (let i = 0; i < len; i++) payload[i] = buf[start + i] ^ buf[off + (i & 3)];
      } else {
        payload = buf.subarray(off, off + len);
      }
      buf = buf.subarray(need);
      if (opcode === 0x8) { closeClient(slot); return; }
      else if (opcode === 0x9) sendFrame(sock, payload.toString("utf8"), 0xA);
      else if (opcode === 0x1) handleMsg(client, payload.toString("utf8"));
    }
  });
  sock.on("close", () => closeClient(slot));
  sock.on("error", () => closeClient(slot));

  send(client, { t: "welcome", slot, name: client.name, host: isHost, cfg: roomCfg, state: roomState });
  send(client, { t: "score", BL: scores.BL, GR: scores.GR });
  send(client, { t: "stats", stats: statsObj() });
  broadcastRoster();
}

// world 聚合下发：只在 playing 且有更新时发；每 KEYFRAME_EVERY tick 发全量关键帧，其余发增量。
setInterval(() => {
  if (roomState !== "playing") return;
  kfCount++;
  const keyframe = forceKeyframe || kfCount % KEYFRAME_EVERY === 0;
  forceKeyframe = false;
  let ents;
  if (keyframe) ents = [...world.values()];
  else {
    if (!changed.size) return;
    ents = [];
    for (const id of changed) { const sn = world.get(id); if (sn) ents.push(sn); }
  }
  changed = new Set();
  if (!ents.length) return;
  const str = JSON.stringify({ t: "world", tick: ++tickSeq, ents });
  for (const c of clients.values()) sendFrame(c.sock, str);
}, TICK_MS).unref();

// 心跳：定期 ping，超时踢除僵尸连接（浏览器自动回 pong）
setInterval(() => {
  const now = Date.now();
  for (const c of clients.values()) {
    if (now - c.last > IDLE_KICK) { try { c.sock.destroy(); } catch (e) {} continue; }
    sendFrame(c.sock, "", 0x9);
  }
}, PING_EVERY).unref();

server.listen(PORT, "0.0.0.0", () => {
  console.log("MP relay listening on http://0.0.0.0:" + PORT + "/");
  console.log("players open  http://<this-server-ip-or-domain>:" + PORT + "/");
});

module.exports = { server, clients, sendFrame, stats, world }; // for tests
