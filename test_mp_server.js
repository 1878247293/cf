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

  // 最小空闲编号：玩家1 已走，b 占 slot2 → 新连接应拿回 slot1、名「玩家1」
  const c = await open();
  await wait(80);
  const wc = c.msgs.find((m) => m.t === "welcome");
  ok(wc && wc.slot === 1 && wc.name === "玩家1", "reuses lowest free slot (1) after leave");
  ok(wc && wc.host === false && wc.cfg && wc.state === "lobby", "welcome carries cfg + lobby state");

  // 房主改配置：b 现在是房主，改 size/goal → 全员收到 config 广播
  b.send(JSON.stringify({ t: "config", cfg: { size: 6, goal: 100 } }));
  await wait(80);
  const cfgC = last(c, "config");
  ok(cfgC && cfgC.cfg && cfgC.cfg.size === 6 && cfgC.cfg.goal === 100, "host config broadcast");

  // 非房主改配置无效：c 发 config 不应改变房间
  c.send(JSON.stringify({ t: "config", cfg: { size: 4 } }));
  await wait(80);
  const cfgC2 = last(c, "config");
  ok(!cfgC2 || cfgC2.cfg.size === 6, "non-host config ignored");

  // 房主开局：start → playing，非房主收到 start{cfg}，分数清零
  b.send(JSON.stringify({ t: "start" }));
  await wait(80);
  const st = last(c, "start");
  ok(st && st.cfg && st.cfg.size === 6, "host start broadcast with cfg to peers");
  const sc0 = last(c, "score");
  ok(sc0 && sc0.BL === 0 && sc0.GR === 0, "score reset on start");

  // 对局进行中 F1 抢房主应被拒绝（roomState=playing）：c 发 grabhost 无 host 广播
  c.send(JSON.stringify({ t: "grabhost" }));
  await wait(80);
  ok(!last(c, "host"), "grabhost rejected during playing");

  // 对局进行中新连入：welcome.state==="playing"（客户端据此停留大厅）
  const d = await open();
  await wait(80);
  const wd = d.msgs.find((m) => m.t === "welcome");
  ok(wd && wd.state === "playing", "mid-match joiner sees playing state");

  // kill 扩展字段转发：killerName/killerTeam/victimName/victimTeam/w/hs 原样广播
  b.send(JSON.stringify({ t: "kill", killer: 2, victim: 1, team: "GR",
    killerName: "玩家2", killerTeam: "GR", victimName: "玩家1", victimTeam: "BL", w: "awp", hs: true }));
  await wait(80);
  const kf2 = last(c, "kill");
  ok(kf2 && kf2.killerName === "玩家2" && kf2.victimTeam === "BL" && kf2.w === "awp" && kf2.hs === true,
    "kill relay carries extended fields");

  // 房主结束回大厅：end → 全员 roomState 回 lobby
  b.send(JSON.stringify({ t: "end" }));
  await wait(80);
  ok(last(c, "end"), "host end broadcast");
  const e = await open();
  await wait(80);
  const we = e.msgs.find((m) => m.t === "welcome");
  ok(we && we.state === "lobby", "after end, new joiner sees lobby state");

  // F1 抢房主：c(slot1) 发 grabhost → 全体收到 host{slot:1}，旧房主 b 被降级
  c.send(JSON.stringify({ t: "grabhost" }));
  await wait(80);
  const hc = last(c, "host");
  ok(hc && hc.slot === 1, "grabhost promotes sender (host slot=1 broadcast)");
  const hb = last(b, "host");
  ok(hb && hb.slot === 1, "old host sees host slot=1 (demoted)");
  // 抢房主后 c 可改配置、b 不能
  c.send(JSON.stringify({ t: "config", cfg: { goal: 30 } }));
  b.send(JSON.stringify({ t: "config", cfg: { goal: 999 } }));
  await wait(80);
  const cfgAfter = last(e, "config");
  ok(cfgAfter && cfgAfter.cfg.goal === 30, "new host config applies, old host ignored");

  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();
