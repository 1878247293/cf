// mp_server.js — 零依赖 Node 联机中继（纯 http+crypto+fs，自实现 WebSocket）
// 启动:  PORT=8080 node mp_server.js
// 玩家:  打开 http://<服务器IP或域名>:PORT/  （会自动跳到 ?mp=1）
// 模型:  哑中继 + 花名册。客户端权威（各自管自己的角色；host=玩家1 兼管 bot）。
const http = require("http");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 8080;
const BUILD_V = Date.now(); // 每次启动生成新版本号，作为跳转/页面的缓存指纹，绕过 CDN 旧缓存
const PING_EVERY = 20000;   // 服务端心跳周期
const IDLE_KICK = 90000;    // 超过此时长无任何数据（含 pong）视为掉线
const HTML = path.join(__dirname, "transport-ship-lockon.html");
const GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

const clients = new Map(); // slot -> {sock, slot, name, team, host}（Map 保留连接先后顺序 → 房主顺延给最早进来的）
const score = { BL: 0, GR: 0 };
// 5v5 房间配置（房主可改）与房间状态。lobby=在大厅；playing=对局进行中（新连入者留在大厅等下一局）。
let roomCfg = { size: 5, diff: "normal", goal: 50, tod: "day" };
let roomState = "lobby";

// 玩家名用「最小空闲编号」：在场编号不变，空号留给下一个进来的人（避免只增不减出现玩家9/10却没有1-8）。
function lowestFreeSlot() { let n = 1; while (clients.has(n)) n++; return n; }

const server = http.createServer((req, res) => {
  const u = (req.url || "/").split("?")[0];
  // 静态文件一律 no-store：游戏页经常更新，若不显式禁缓存，EdgeOne 会把旧版 HTML 缓存住，
  // 导致重新部署后玩家仍拿到旧版（之前踩过的坑）。
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

function handleMsg(client, str) {
  let m;
  try { m = JSON.parse(str); } catch (e) { return; }
  if (m.t === "join") {
    client.team = m.team === "GR" ? "GR" : "BL";
    broadcastRoster();
    return;
  }
  if (m.t === "kill") {
    if (m.team === "BL" || m.team === "GR") score[m.team]++;
    broadcast({ t: "kill", killer: m.killer, victim: m.victim,
      killerName: m.killerName, killerTeam: m.killerTeam || m.team || null,
      victimName: m.victimName || null, victimTeam: m.victimTeam || null,
      w: m.w || "ak47", hs: !!m.hs });
    broadcast({ t: "score", BL: score.BL, GR: score.GR });
    return;
  }
  // 房主专属：修改房间配置 / 开局 / 结束回大厅
  if (m.t === "config") {
    if (!client.host) return;
    if (m.cfg) {
      if (typeof m.cfg.size === "number") roomCfg.size = Math.max(1, Math.min(8, m.cfg.size | 0));
      if (m.cfg.diff) roomCfg.diff = m.cfg.diff;
      if (typeof m.cfg.goal === "number") roomCfg.goal = m.cfg.goal | 0;
      if (m.cfg.tod) roomCfg.tod = m.cfg.tod;
    }
    broadcast({ t: "config", cfg: roomCfg });
    return;
  }
  if (m.t === "start") {
    if (!client.host) return;
    roomState = "playing";
    score.BL = 0; score.GR = 0;
    broadcast({ t: "start", cfg: roomCfg }, client.slot); // 房主自己已从点击手势里开局，别人收到后「点击进入」
    broadcast({ t: "score", BL: 0, GR: 0 });
    return;
  }
  if (m.t === "end") {
    if (!client.host) return;
    roomState = "lobby";
    broadcast({ t: "end" });
    return;
  }
  if (m.t === "grabhost") {
    // 任意玩家按 F1 直接抢房主（仅大厅可抢：对局进行中拒绝，避免中途接管使 bot 冻结）
    if (roomState === "playing") return;
    for (const c of clients.values()) c.host = false;
    client.host = true;
    broadcast({ t: "host", slot: client.slot });
    broadcastRoster();
    return;
  }
  m.from = client.slot;
  broadcast(m, client.slot); // relay state/fire/hit/death/spawn/bots to everyone else
}

function closeClient(slot) {
  const c = clients.get(slot);
  if (!c) return;
  clients.delete(slot);
  try { c.sock.destroy(); } catch (e) {}
  if (c.host) {
    const first = [...clients.values()][0];
    if (first) { first.host = true; broadcast({ t: "host", slot: first.slot }); }
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
  broadcastRoster();
}

// 心跳：定期 ping，超时踢除僵尸连接（浏览器会自动回 pong）
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

module.exports = { server, clients, sendFrame }; // for tests


