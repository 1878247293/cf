// test_mp_server.js — 真实 WebSocket 跑通服务器权威协议：
// 握手/分配/花名册 · world 聚合下发 · frag→stats/score 权威计分 · bot 归属与 botsassign 迁移 · config/start/end/grabhost
process.env.PORT = "8199";
const srv = require("./mp_server.js");
const BASE = "ws://127.0.0.1:8199";
let pass = 0, fail = 0;
const ok = (c, m) => { c ? pass++ : (fail++, console.error("FAIL:", m)); };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
function open() {
  const ws = new WebSocket(BASE);
  ws.msgs = [];
  ws.addEventListener("message", (e) => { try { ws.msgs.push(JSON.parse(e.data)); } catch (x) {} });
  return new Promise((res) => ws.addEventListener("open", () => res(ws)));
}
const send = (ws, o) => ws.send(JSON.stringify(o));
const last = (ws, t) => [...ws.msgs].reverse().find((m) => m.t === t);
const has = (ws, t) => ws.msgs.some((m) => m.t === t);

(async () => {
  await wait(150);
  // 玩家1 → welcome slot1 host lobby，并附带 score + stats 初始态
  const a = await open(); await wait(80);
  const wa = a.msgs.find((m) => m.t === "welcome");
  ok(wa && wa.slot === 1 && wa.host === true && wa.state === "lobby", "welcome 玩家1 host lobby");
  ok(has(a, "score") && has(a, "stats"), "welcome 附带 score+stats 初始态");
  send(a, { t: "join", team: "BL" }); await wait(60);

  // 玩家2 → welcome slot2 非 host
  const b = await open(); await wait(80);
  const wb = b.msgs.find((m) => m.t === "welcome");
  ok(wb && wb.slot === 2 && wb.host === false, "welcome 玩家2 non-host");
  send(b, { t: "join", team: "GR" }); await wait(80);

  const ra = last(a, "roster");
  ok(ra && ra.players.length === 2, "roster 2 players");
  const rp1 = ra.players.find((p) => p.slot === 1), rp2 = ra.players.find((p) => p.slot === 2);
  ok(rp1 && rp1.team === "BL" && rp2 && rp2.team === "GR", "roster teams BL/GR");
  ok(rp1.host === true && rp2.host === false, "roster host flag");

  // 房主改配置 → 全员 config；非房主改配置被忽略
  send(a, { t: "config", cfg: { size: 6, goal: 100 } }); await wait(80);
  const cfgB = last(b, "config");
  ok(cfgB && cfgB.cfg.size === 6 && cfgB.cfg.goal === 100, "host config 广播");
  send(b, { t: "config", cfg: { size: 4 } }); await wait(80);
  ok(last(b, "config").cfg.size === 6, "非房主 config 被忽略");

  // 大厅态：state 存入 world 但不 tick 下发
  send(a, { t: "state", ents: [{ id: 1, x: 1.5, y: 2, z: 0, yaw: 0, pitch: 0 }] }); await wait(150);
  ok(!has(b, "world"), "大厅不下发 world");

  // 房主开局 → playing；非房主收 start{cfg}；score 清零；world+stats 清空
  send(a, { t: "start" }); await wait(90);
  const st = last(b, "start");
  ok(st && st.cfg.size === 6, "start 带 cfg 广播给非房主");
  ok(last(b, "score").BL === 0 && last(b, "score").GR === 0, "start 清分");
  ok(srv.world.size === 0 && srv.stats.size === 0, "start 清空 world+stats");

  // world 聚合：真人自己的实体被聚合下发给同伴
  send(a, { t: "state", ents: [{ id: 1, x: 3.5, y: 2, z: 1, yaw: .2, pitch: 0, al: 1, hp: 100, tm: "BL", nm: "玩家1" }] });
  await wait(150);
  const w1 = last(b, "world");
  ok(w1 && w1.ents.some((e) => e.id === 1 && e.x === 3.5), "同伴收到含真人实体的 world");
  // 房主上报 bot → 进 world；非房主上报 bot → 被忽略
  send(a, { t: "state", ents: [{ id: 1001, x: 5, y: 0, z: 0, yaw: 0, al: 1, hp: 100, tm: "GR", nm: "人机" }] });
  await wait(150);
  ok(srv.world.has(1001), "房主 bot 进 world");
  send(b, { t: "state", ents: [{ id: 1002, x: 9, y: 0, z: 0 }] }); await wait(120);
  ok(!srv.world.has(1002), "非房主 bot 被忽略");

  // frag → 权威 stats + score
  send(a, { t: "frag", killer: 1, victim: 2, killerTeam: "BL", hs: true, w: "awp",
    killerName: "玩家1", victimName: "玩家2", victimTeam: "GR" });
  await wait(80);
  const fr = last(b, "frag");
  ok(fr && fr.killer === 1 && fr.victim === 2 && fr.w === "awp" && fr.hs === true && fr.victimTeam === "GR", "frag 广播含全字段");
  const sB = last(b, "stats");
  ok(sB && sB.stats["1"] && sB.stats["1"].k === 1 && sB.stats["1"].hs === 1, "击杀者 stats k+hs");
  ok(sB.stats["2"] && sB.stats["2"].d === 1, "受害者 stats d");
  ok(last(b, "score").BL === 1 && last(b, "score").GR === 0, "frag 累加队伍分");
  ok(srv.stats.get(1).k === 1 && srv.stats.get(2).d === 1, "服务器 stats 权威");

  // grabhost（对局进行中无限制）→ host slot2；新房主 b 收到 botsassign（只含真实 bot 1001）
  send(b, { t: "grabhost" }); await wait(80);
  ok(last(a, "host").slot === 2 && last(b, "host").slot === 2, "grabhost 对局中无限制，全体见 host slot2");
  const ba = last(b, "botsassign");
  ok(ba && ba.ids.indexOf(1001) >= 0 && ba.ids.indexOf(1002) < 0, "botsassign 只列真实 bot 给新房主");

  // b（现房主）end → 回大厅、world 清空
  send(b, { t: "end" }); await wait(80);
  ok(has(a, "end"), "end 广播");
  ok(srv.world.size === 0, "end 清空 world");
  const d = await open(); await wait(80);
  ok(d.msgs.find((m) => m.t === "welcome").state === "lobby", "end 后新连入见 lobby");

  // 最小空闲编号复用：关掉 a(slot1) → 新连入 e 拿回 slot1
  a.close(); await wait(150);
  const e = await open(); await wait(80);
  ok(e.msgs.find((m) => m.t === "welcome").slot === 1, "复用最小空闲编号 slot1");

  // 掉线房主迁移：b 再开局+上报 bot，掉线 → 顺延最早连接者当房主并收 botsassign
  send(b, { t: "start" }); await wait(80);
  send(b, { t: "state", ents: [{ id: 1003, x: 1, y: 0, z: 0, al: 1, hp: 100 }] }); await wait(120);
  ok(srv.world.has(1003), "迁移前房主 bot 在 world");
  b.close(); await wait(160);
  const hostAfter = last(d, "host") || last(e, "host");
  ok(hostAfter, "掉线后房主顺延");
  const bad = last(d, "botsassign") || last(e, "botsassign");
  ok(bad && bad.ids.indexOf(1003) >= 0, "迁移新房主收到含 bot 的 botsassign");

  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();
