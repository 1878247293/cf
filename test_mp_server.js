// test_mp_server.js — 用真实 WebSocket 连接跑通服务器：握手/分配/花名册/中继/掉线
process.env.PORT = "8199";
require("./mp_server.js");
const BASE = "ws://127.0.0.1:8199";
let pass = 0, fail = 0;
const ok = (c, m) => { c ? (pass++) : (fail++, console.error("FAIL:", m)); };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function open(onMsg) {
  const ws = new WebSocket(BASE);
  ws.msgs = [];
  ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); ws.msgs.push(m); onMsg && onMsg(m, ws); });
  return new Promise((res) => ws.addEventListener("open", () => res(ws)));
}
const last = (ws, t) => [...ws.msgs].reverse().find((m) => m.t === t);

(async () => {
  await wait(150);
  // 玩家1 连接 -> welcome slot1 host
  const a = await open();
  await wait(80);
  const wa = a.msgs.find((m) => m.t === "welcome");
  ok(wa && wa.slot === 1 && wa.name === "玩家1" && wa.host === true, "welcome 玩家1 host");
  a.send(JSON.stringify({ t: "join", team: "BL" }));
  await wait(60);

  // 玩家2 连接 -> welcome slot2 非host
  const b = await open();
  await wait(80);
  const wb = b.msgs.find((m) => m.t === "welcome");
  ok(wb && wb.slot === 2 && wb.name === "玩家2" && wb.host === false, "welcome 玩家2 non-host");
  b.send(JSON.stringify({ t: "join", team: "GR" }));
  await wait(80);

  // 花名册应含两人及其队伍
  const ra = last(a, "roster");
  ok(ra && ra.players.length === 2, "roster has 2 players");
  const p1 = ra.players.find((p) => p.slot === 1), p2 = ra.players.find((p) => p.slot === 2);
  ok(p1 && p1.team === "BL" && p2 && p2.team === "GR", "roster teams BL/GR");

  // state 中继：a 发 state，b 收到且带 from=1，a 自己不回显
  const beforeB = b.msgs.length;
  a.send(JSON.stringify({ t: "state", x: 1.5, y: 2 }));
  await wait(80);
  const relayed = b.msgs.slice(beforeB).find((m) => m.t === "state");
  ok(relayed && relayed.from === 1 && relayed.x === 1.5, "state relayed to peer with from");
  ok(!a.msgs.slice().reverse().slice(0, 3).some((m) => m.t === "state"), "sender does not get own state echo");

  // kill 计分 + 广播
  a.send(JSON.stringify({ t: "kill", killer: 1, victim: 2, team: "BL" }));
  await wait(80);
  const sc = last(a, "score");
  ok(sc && sc.BL === 1 && sc.GR === 0, "kill tallies team score");
  const kf = last(b, "kill");
  ok(kf && kf.killer === 1 && kf.victim === 2, "kill event broadcast");

  // 掉线：关 a（host），b 应被提升为 host 并收到 leave
  a.close();
  await wait(150);
  const hostMsg = last(b, "host");
  ok(hostMsg, "host promoted on host disconnect");
  const rb = last(b, "roster");
  ok(rb && rb.players.length === 1 && rb.players[0].slot === 2, "roster shrinks after leave");

  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();
