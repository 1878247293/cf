// mp_server.js — 零依赖 Node 联机中继（纯 http+crypto+fs，自实现 WebSocket）
// 启动:  PORT=8080 node mp_server.js
// 玩家:  打开 http://<服务器IP或域名>:PORT/  （会自动跳到 ?mp=1）
// 模型:  哑中继 + 花名册。客户端权威（各自管自己的角色；host=玩家1 兼管 bot）。
const http = require("http");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 8080;
const HTML = path.join(__dirname, "transport-ship-lockon.html");
const GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";

let nextSlot = 1;
const clients = new Map(); // slot -> {sock, slot, name, team, host}
const score = { BL: 0, GR: 0 };

const server = http.createServer((req, res) => {
  const u = (req.url || "/").split("?")[0];
  if (u === "/") {
    res.writeHead(302, { Location: "/transport-ship-lockon.html?mp=1" });
    res.end();
    return;
  }
  if (u === "/transport-ship-lockon.html") {
    fs.readFile(HTML, (err, buf) => {
      if (err) { res.writeHead(404); res.end("build transport-ship-lockon.html first"); return; }
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
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
    broadcast({ t: "kill", killer: m.killer, victim: m.victim, killerName: m.killerName });
    broadcast({ t: "score", BL: score.BL, GR: score.GR });
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
    if (first) { first.host = true; send(first, { t: "host" }); }
  }
  broadcast({ t: "leave", slot });
  broadcastRoster();
}
function onConnect(sock) {
  const slot = nextSlot++;
  const isHost = ![...clients.values()].some((c) => c.host);
  const client = { sock, slot, name: "玩家" + slot, team: null, host: isHost };
  clients.set(slot, client);
  let buf = Buffer.alloc(0);

  sock.on("data", (chunk) => {
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

  send(client, { t: "welcome", slot, name: client.name, host: isHost });
  broadcastRoster();
}

server.listen(PORT, () => {
  console.log("MP relay listening on http://0.0.0.0:" + PORT + "/");
  console.log("players open  http://<this-server-ip-or-domain>:" + PORT + "/");
});

module.exports = { server, clients, sendFrame }; // for tests


