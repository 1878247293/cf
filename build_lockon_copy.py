from pathlib import Path
import re


source = Path("page.html")
target = Path("transport-ship-lockon.html")
html = source.read_text(encoding="utf-8")

# ---------------------------------------------------------------- 可调参数
# 步枪/冲锋枪/手枪按住右键的开镜（ADS）参数，想改手感直接调这三个数。
ADS_FOV   = ".8"    # 开镜后视场角 = 当前 fov × 该值（越小放大越多）
ADS_SPREAD = ".35"  # 开镜散布倍率（越小越准）
ADS_MOVE  = ".72"   # 开镜移动速度倍率

# 角色技能参数（Ctrl 滑铲 / V 向前喷气）
SLIDE_TIME  = ".55"   # 滑铲持续时间（秒）
SLIDE_CD    = "1"     # 滑铲冷却（秒）
SLIDE_SPEED = "12"    # 滑铲初速（米/秒，正常走速为 5.7）
SLIDE_MULT  = "2.1"   # 滑铲期间目标速度倍率（基数 5.7）
SLIDE_FRIC  = ".15"   # 滑铲期间地面摩擦倍率（越小滑得越远）
JET_SPEED   = "11"    # 喷气水平推力（米/秒）
JET_LIFT    = "2.4"   # 喷气抬升速度（米/秒，跳起为 6.6）
JET_CD      = "1.2"   # 喷气冷却（秒）

# 虎蹲炮参数（G 键部署，向准星落点抛射一串炮弹）
CAN_CD       = "20"    # 冷却（秒）
CAN_DEPLOY   = ".55"   # 从按下到首发的架设时间（秒）
CAN_SHOTS    = "6"     # 一轮打几发
CAN_INTERVAL = ".16"   # 两发间隔（秒）
CAN_RANGE    = "20"    # 准星没打到任何东西时的默认落点距离（米）
CAN_SPREAD   = "2.2"   # 每发相对落点的随机散布半径（米）
CAN_DMG      = "72"    # 单发伤害（原版手雷 115，这里一发弱但一轮 6 发）
CAN_RADIUS   = "5.6"   # 单发爆炸半径（原版手雷 7.5）
CAN_G        = "14"    # 弹道重力（与手雷一致）

ADS_COMPUTE = (
    "this.ads=!!(this.alive&&this.mouse.r&&this.weapon&&!this.weapon.reloading&&"
    '(this.weapon.def.type==="rifle"||this.weapon.def.type==="smg"||this.weapon.def.type==="pistol"))'
)

old_constructor = "this.pendingThrow=0"
new_constructor = "this.pendingThrow=0,this.lockAim=!1,this.ads=!1,this.slideT=0,this.slideCD=0,this.jetCD=0,this.cannonCD=0"
if old_constructor not in html:
    raise SystemExit("player constructor marker not found")
html = html.replace(old_constructor, new_constructor, 1)

old_update = "this.mouse.lp=this.mouse.rp=!1,this.touch.firePressed=!1,this.weaponUpdate(t,{fire:this.mouse.l||this.touch.fire,firePressed:g,alt:this.mouse.r||this.touch.alt,altPressed:y,reload:this.consumePressed(\"KeyR\"),sw:m})"
if old_update not in html:
    old_update = "this.mouse.lp=this.mouse.rp=!1,this.touch.firePressed=!1,this.weaponUpdate(t,{fire:this.mouse.l||this.touch.fire,firePressed:g,alt:this.mouse.r,altPressed:y,reload:this.consumePressed(\"KeyR\"),sw:m})"
if old_update not in html:
    raise SystemExit("player update marker not found")
new_update = "this.mouse.lp=this.mouse.rp=!1,this.touch.firePressed=!1," + ADS_COMPUTE + ",e.applySkills(this,t,d,f),this.consumePressed(\"KeyL\")&&(this.lockAim=!this.lockAim,e.hud.toast(this.lockAim?\"\\u9501\\u5934\\u8F85\\u52A9\\uFF1A\\u5F00\\u542F\":\"\\u9501\\u5934\\u8F85\\u52A9\\uFF1A\\u5173\\u95ED\",1.5)),this.weaponUpdate(t,{fire:this.mouse.l||this.touch.fire,firePressed:g,alt:this.mouse.r,altPressed:y,reload:this.consumePressed(\"KeyR\"),sw:m})"
html = html.replace(old_update, new_update, 1)
camera_marker = "this.pressed.clear(),this.updateCamera(t)"
assert html.count(camera_marker) == 1
html = html.replace(camera_marker, "this.pressed.clear(),e.applyLockAim(this),this.updateCamera(t)")

# ------------------------------------------------ 步枪/冲锋枪/手枪 ADS 注入
# ------------------------------------------------- 按键不再触发浏览器行为
# 原版只对 Tab/Space/KeyB/KeyF/KeyQ/↑/↓ 调了 preventDefault，于是按住 Ctrl 滑铲时再按方向键
# 会同时触发浏览器快捷键：Ctrl+W 关标签、Ctrl+D 加书签、Ctrl+S 存页、Ctrl+A 全选、Ctrl+R 刷新页面
# （R 恰好是换弹键），都会打断游戏。这里改成：游戏自己的键一律拦，另外只要按住 Ctrl/Alt/Meta
# 就拦掉浏览器默认行为；但放行 F 键（保留 F5 刷新 / F12 开发者工具）与 Ctrl+Shift 组合
# （保留 Ctrl+Shift+I/T/R）。Shift 单独按（奔跑）不受影响，Esc 也不拦（交给浏览器退出鼠标锁）。
keydown_old = 'window.addEventListener("keydown",n=>{let s=i();s&&(["Tab","Space","KeyB","KeyF","KeyQ","ArrowUp","ArrowDown"].includes(n.code)&&n.preventDefault(),!n.repeat&&(s.keys.add(n.code),s.pressed.add(n.code)))}),'
keydown_new = r'''window.addEventListener("keydown",n=>{let s=i();if(s){let a=["Tab","Space","KeyB","KeyF","KeyQ","ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(n.code),m=(n.ctrlKey||n.altKey||n.metaKey)&&!n.shiftKey&&!/^F\d{1,2}$/.test(n.code);(a||m)&&n.preventDefault(),!n.repeat&&(s.keys.add(n.code),s.pressed.add(n.code))}}),'''
assert html.count(keydown_old) == 1, "keydown handler marker"
html = html.replace(keydown_old, keydown_new, 1)

# ------------------------------------------ 全屏 + Keyboard Lock（治本方案）
# preventDefault 拦不住浏览器保留快捷键（Ctrl+W 关标签 → 弹到微软登录页、Ctrl+T/N/Tab/Ctrl+数字）。
# 唯一能拦住它们的是 Keyboard Lock API，而它只在「文档处于全屏」时才会抑制这些快捷键。
# 所以在游戏请求指针锁定（lock()，由 mousedown 用户手势触发）时，顺带请求全屏并锁定键盘；
# 回主菜单时释放键盘锁并退出全屏。
# 仅 Chromium 系（Chrome/Edge/Opera）支持 navigator.keyboard.lock；Firefox/Safari 无此 API，
# 全部做了特性检测，不支持时静默跳过（退化为仅 preventDefault 的旧行为，不报错）。
# 锁定的按键列表**刻意不含 Escape**：这样单击 Esc 仍会退出指针锁→触发游戏暂停（onLockChange），
# 手感不变；同时不含 F 系（保留 F5/F12），Ctrl+Shift+I/T/R 也照常可用（列表里无对应 code 组合语义）。
# 覆盖的保留组合：Ctrl+W/A/S/D/R/F/Q/... 关标签/存页/刷新等 + Ctrl+T/N/P 新标签新窗口打印
# + Ctrl+Tab 切标签 + Ctrl+0~9 切到第 N 个标签。这些 code 本来就是游戏用键，锁定它们只是额外
# 顺手屏蔽掉浏览器的 Ctrl+ 动作，对操作零影响。
KBD_LOCK_KEYS = (
    '["KeyW","KeyA","KeyS","KeyD","KeyR","KeyF","KeyQ","KeyB","KeyC","KeyL","KeyV","KeyG",'
    '"KeyE","KeyH","KeyT","KeyN","KeyP","Tab",'
    '"Digit1","Digit2","Digit3","Digit4","Digit5","Digit6","Digit7","Digit8","Digit9","Digit0"]'
)
enter_immersive = (
    "try{let _d=document.documentElement;"
    "_d.requestFullscreen&&!document.fullscreenElement&&_d.requestFullscreen().catch(()=>{});"
    "navigator.keyboard&&navigator.keyboard.lock&&navigator.keyboard.lock(" + KBD_LOCK_KEYS + ").catch(()=>{})"
    "}catch{}"
)
exit_immersive = (
    "(()=>{try{"
    "navigator.keyboard&&navigator.keyboard.unlock&&navigator.keyboard.unlock();"
    "document.fullscreenElement&&document.exitFullscreen&&document.exitFullscreen().catch(()=>{})"
    "}catch{}})()"
)

lock_old = "}catch{try{t.requestPointerLock()}catch{}}}onLockChange"
lock_new = "}catch{try{t.requestPointerLock()}catch{}}" + enter_immersive + "}onLockChange"
assert html.count(lock_old) == 1, "pointer lock() marker"
html = html.replace(lock_old, lock_new, 1)

menu_old = ',document.pointerLockElement&&document.exitPointerLock(),this.hud.show("menu")'
menu_new = ',document.pointerLockElement&&document.exitPointerLock(),' + exit_immersive + ',this.hud.show("menu")'
assert html.count(menu_old) == 1, "return-to-menu marker"
html = html.replace(menu_old, menu_new, 1)


ads_fov_old = 'let u=this.weapon,d=e.opts.fov;u&&u.def.type==="sniper"&&this.scoped&&(d=u.def.zoom[this.scoped-1]);let f=this.scoped?1:Math.min(1,t*10);'
ads_fov_new = (
    'let u=this.weapon,d=e.opts.fov;'
    'u&&u.def.type==="sniper"&&this.scoped&&(d=u.def.zoom[this.scoped-1]);'
    'this.ads&&u&&u.def.type!=="sniper"&&(d=e.opts.fov*' + ADS_FOV + ');'
    'let f=this.scoped&&u&&u.def.type==="sniper"?1:Math.min(1,t*10);'
)
assert html.count(ads_fov_old) == 1, "ads fov marker"
html = html.replace(ads_fov_old, ads_fov_new, 1)

# 2) 把 ads 状态传进散布函数
ads_spread_old = 'let l=Ff(s,{speed:this.speed||0,onGround:this.onGround,crouch:this.crouch,scoped:this.scoped>0,scopeReady:this.scopeReady});'
ads_spread_new = 'let l=Ff(s,{speed:this.speed||0,onGround:this.onGround,crouch:this.crouch,scoped:this.scoped>0,scopeReady:this.scopeReady,ads:this.ads});'
assert html.count(ads_spread_old) == 1, "ads spread call marker"
html = html.replace(ads_spread_old, ads_spread_new, 1)

# 3) 散布函数里对开镜状态整体收紧（再守一道 sniper，避免与狙击的 scoped 逻辑耦合）
ads_ff_old = ',Math.min(i,e.max+e.base+(t.onGround?0:e.air))}'
ads_ff_new = ',t.ads&&r.def.type!=="sniper"&&(i*=' + ADS_SPREAD + '),Math.min(i,e.max+e.base+(t.onGround?0:e.air))}'
assert html.count(ads_ff_old) == 1, "ads spread fn marker"
html = html.replace(ads_ff_old, ads_ff_new, 1)

# 4) 移动速度：滑铲期间用高倍率顶替蹲/走倍率，开镜再叠一层减速
move_speed_old = 'let h=wy*c*(this.crouch?.42:a?.5:1)*(this.scoped?.55:1),'
move_speed_new = ('let h=wy*c*(this.slideT>0?' + SLIDE_MULT + ':(this.crouch?.42:a?.5:1))'
                  '*(this.scoped?.55:1)*(this.ads?' + ADS_MOVE + ':1),')
assert html.count(move_speed_old) == 1, "move speed marker"
html = html.replace(move_speed_old, move_speed_new, 1)

# 5) 滑铲期间大幅降低地面摩擦，否则速度一帧就被吃掉
slide_fric_old = 'let w=Math.max(y,1.5)*9*t,b=Math.max(0,y-w)/y;'
slide_fric_new = 'let w=Math.max(y,1.5)*9*t*(this.slideT>0?' + SLIDE_FRIC + ':1),b=Math.max(0,y-w)/y;'
assert html.count(slide_fric_old) == 1, "slide friction marker"
html = html.replace(slide_fric_old, slide_fric_new, 1)

# 6) 滑铲借用引擎原有的下蹲机制：碰撞高度、视点高度、起身卡墙检测全都自动生效
slide_crouch_old = 'this.walk=i.has("ShiftLeft")||i.has("ShiftRight"),this.move(t,d,f,p,x,this.walk)'
slide_crouch_new = 'this.walk=i.has("ShiftLeft")||i.has("ShiftRight"),this.move(t,d,f,p,x||this.slideT>0,this.walk)'
assert html.count(slide_crouch_old) == 1, "slide crouch marker"
html = html.replace(slide_crouch_old, slide_crouch_new, 1)

# ------------------------------------------------------ 虎蹲炮（G 键）注入
# A) 让 explode() 接受一个可选爆炸定义，缺省仍是手雷 mi.he（原路径一字不动）。
#    这样虎蹲炮的单发伤害/半径能和手雷分开调。
explode_old = "explode(t,e){let i=mi.he;"
explode_new = "explode(t,e,i){i=i||mi.he;"
assert html.count(explode_old) == 1, "explode marker"
html = html.replace(explode_old, explode_new, 1)

# B) 把炮弹的推进挂进游戏主循环（紧挨着手雷的 updateNades）
mortar_hook_old = "this.updateNades(t),"
mortar_hook_new = "this.updateMortars(t),this.updateNades(t),"
assert html.count(mortar_hook_old) == 1, "updateNades hook marker"
html = html.replace(mortar_hook_old, mortar_hook_new, 1)

old_fire = "let n=e.def,s=t.eye(new R),a=t.forward(new R);Of(a,i,Math.random);let o;"
if old_fire not in html:
    raise SystemExit("fire marker not found")
new_fire = "let n=e.def,s=t.eye(new R),a=t.forward(new R);if(t.isPlayer&&t.lockAim){let c=this.findLockTarget(t,a);c&&(a.copy(c).sub(s).normalize(),i=0)}t.isPlayer&&this.mp&&this.netFire(s,a,n.id);Of(a,i,Math.random);let o;"
html = html.replace(old_fire, new_fire, 1)

old_trace = "traceBullet(t,e,i,n){let s=n.range"
if old_trace not in html:
    raise SystemExit("trace marker not found")
lock_method = r'''
findLockTarget(player, forward) {
    let best = null, bestScore = Infinity;
    const eye = player.eye(new R);
    for (const actor of this.actors) {
        if (!actor.alive || actor === player || actor.team === player.team || actor.protectT > 0) continue;
        const head = actor.soldier.headWorld(new R);
        const direction = head.clone().sub(eye);
        const distance = direction.length();
        if (distance < .001 || distance > Math.min(80, player.weapon.def.range || 80)) continue;
        direction.normalize();
        const alignment = forward.dot(direction);
        if (alignment < Math.cos(.32)) continue;
        const wall = this.world.raycast(eye.x, eye.y, eye.z, direction.x, direction.y, direction.z, distance, "sight");
        if (wall && wall.t < distance) continue;
        const score = 1 - alignment + distance * .00001;
        if (score < bestScore) { bestScore = score; best = head; }
    }
    return best;
}
applyLockAim(player) {
    const type = player.weapon?.def.type;
    const active = player.lockAim && player.alive && type !== "melee" && type !== "grenade";
    const head = active ? this.findLockTarget(player, player.forward(new R)) : null;
    if (head) {
        const direction = head.sub(player.eye(new R)).normalize();
        player.yaw = Math.atan2(-direction.x, -direction.z) - player.punchY * .75;
        player.pitch = Math.asin(Math.max(-1, Math.min(1, direction.y))) - player.punchP * .75 - player.aimPunch;
    }
    let status = document.getElementById("lockAimStatus");
    if (!status) {
        status = document.createElement("div");
        status.id = "lockAimStatus";
        status.style.cssText = "position:fixed;top:86px;left:50%;transform:translateX(-50%);z-index:100;pointer-events:none;color:#ffe082;background:#111b;padding:7px 14px;border-radius:6px;font:13px sans-serif;max-width:96vw;text-align:center";
        document.body.appendChild(status);
    }
    status.textContent = "右键开镜：" + (player.ads ? "开" : "关")
        + "  ｜  Ctrl 滑铲：" + (player.slideCD > 0 ? player.slideCD.toFixed(1) + "s" : "就绪")
        + "  ｜  V 喷气：" + (player.jetCD > 0 ? player.jetCD.toFixed(1) + "s" : "就绪")
        + "  ｜  G 虎蹲炮：" + (player.cannonCD > 0 ? player.cannonCD.toFixed(1) + "s" : "就绪");
}
'''

skill_method = r'''
applySkills(player, dt, dx, dz) {
    player.slideT = Math.max(0, player.slideT - dt);
    player.slideCD = Math.max(0, player.slideCD - dt);
    player.jetCD = Math.max(0, player.jetCD - dt);
    player.cannonCD = Math.max(0, player.cannonCD - dt);
    if (!player.onGround) player.slideT = 0;
    if (!player.alive) return;
    const fx = this.fx, pos = player.pos, yaw = player.yaw;
    const surface = (player.ground && player.ground.surface) || "metal";
    if ((player.consumePressed("ControlLeft") || player.consumePressed("ControlRight"))
        && player.onGround && player.slideCD <= 0) {
        let dirX = dx, dirZ = dz;
        const mag = Math.hypot(dirX, dirZ);
        if (mag > .01) { dirX /= mag; dirZ /= mag; }
        else { dirX = -Math.sin(yaw); dirZ = -Math.cos(yaw); }
        player.slideT = __SLIDE_TIME__;
        player.slideCD = __SLIDE_CD__;
        player.vel.x = dirX * __SLIDE_SPEED__;
        player.vel.z = dirZ * __SLIDE_SPEED__;
        Jt.playFootstep(null, surface, { run: !0, crouch: !1 });
        if (fx) {
            fx.shake = Math.max(fx.shake, .3);
            for (let i = 0; i < 10; i++) {
                const angle = Math.random() * 6.2832, speed = 1 + Math.random() * 2.5;
                fx.smoke.emit({ x: pos.x, y: pos.y + .12, z: pos.z,
                    vx: Math.cos(angle) * speed - dirX * 1.6,
                    vy: .4 + Math.random() * 1.1,
                    vz: Math.sin(angle) * speed - dirZ * 1.6,
                    life: 0, max: .7 + Math.random() * .5, s0: .12, s1: .95,
                    r: .62, g: .6, b: .55, a0: .5, a1: 0, grav: -.4, drag: 2.6 });
            }
        }
    }
    if (player.consumePressed("KeyV") && player.jetCD <= 0) {
        const fwdX = -Math.sin(yaw), fwdZ = -Math.cos(yaw);
        player.jetCD = __JET_CD__;
        player.vel.x += fwdX * __JET_SPEED__;
        player.vel.z += fwdZ * __JET_SPEED__;
        player.vel.y = Math.max(player.vel.y, __JET_LIFT__);
        player.onGround = !1;
        Jt.playJump(null);
        if (fx) {
            fx.light(pos, 26, .22, 16758512, 13);
            for (let i = 0; i < 18; i++) {
                const angle = Math.random() * 6.2832, speed = 1 + Math.random() * 3;
                fx.smoke.emit({ x: pos.x - fwdX * .3, y: pos.y + .5 + Math.random() * .5, z: pos.z - fwdZ * .3,
                    vx: -fwdX * (3 + Math.random() * 5) + Math.cos(angle) * speed,
                    vy: -.5 + Math.random() * 1.5,
                    vz: -fwdZ * (3 + Math.random() * 5) + Math.sin(angle) * speed,
                    life: 0, max: .5 + Math.random() * .6, s0: .18, s1: 1.4,
                    r: .75, g: .78, b: .8, a0: .6, a1: 0, grav: -.3, drag: 2.2 });
            }
            for (let i = 0; i < 8; i++) {
                fx.add.emit({ x: pos.x - fwdX * .25, y: pos.y + .5, z: pos.z - fwdZ * .25,
                    vx: -fwdX * (4 + Math.random() * 4), vy: -.2 + Math.random(),
                    vz: -fwdZ * (4 + Math.random() * 4),
                    life: 0, max: .25, s0: .5, s1: .1, r: 1.2, g: .9, b: .55, a0: .9, a1: 0, grav: 0, drag: 3 });
            }
        }
    }
    if (player.consumePressed("KeyG") && player.onGround && player.cannonCD <= 0) {
        this.deployCannon(player);
    }
}
'''
for token, value in [("__SLIDE_TIME__", SLIDE_TIME), ("__SLIDE_CD__", SLIDE_CD),
                     ("__SLIDE_SPEED__", SLIDE_SPEED), ("__JET_SPEED__", JET_SPEED),
                     ("__JET_LIFT__", JET_LIFT), ("__JET_CD__", JET_CD)]:
    assert token in skill_method
    skill_method = skill_method.replace(token, value)

cannon_method = r'''
cannonTarget(player) {
    const eye = player.eye(new R), fwd = player.forward(new R);
    const hit = this.world.raycast(eye.x, eye.y, eye.z, fwd.x, fwd.y, fwd.z, 60, "bullet");
    if (hit) return eye.clone().addScaledVector(fwd, hit.t);
    const far = eye.clone().addScaledVector(fwd, __CAN_RANGE__);
    const down = this.world.raycast(far.x, far.y + 12, far.z, 0, -1, 0, 40, "bullet");
    if (down) far.y = far.y + 12 - down.t;
    return far;
}
deployCannon(player) {
    this.mortars || (this.mortars = []);
    player.cannonCD = __CAN_CD__;
    const yaw = player.yaw, pos = player.pos.clone();
    const mat = new qe({ color: 3556922, roughness: .62, metalness: .7 });
    const group = new ke();
    const plate = new Yt(new Le(.6, .1, .6), mat);
    plate.position.y = .06;
    const hub = new Yt(new xi(.15, .19, .2, 12), mat);
    hub.position.y = .21;
    const tube = new Yt(new xi(.08, .095, .84, 12), mat);
    tube.position.set(0, .52, -.2);
    tube.rotation.x = -.62;
    const legA = new Yt(new xi(.042, .048, .68, 8), mat);
    legA.position.set(.23, .31, .13);
    legA.rotation.z = -.5;
    const legB = new Yt(new xi(.042, .048, .68, 8), mat);
    legB.position.set(-.23, .31, .13);
    legB.rotation.z = .5;
    group.add(plate, hub, tube, legA, legB);
    group.position.copy(pos);
    group.rotation.y = yaw;
    this.renderer.scene.add(group);
    this.mortars.push({ kind: "device", mesh: group, pos, yaw, owner: player,
        target: this.cannonTarget(player), life: 0, deploy: __CAN_DEPLOY__,
        shots: __CAN_SHOTS__, next: __CAN_DEPLOY__ });
    Jt.playGrenadeThrow();
    this.hud.toast("虎蹲炮 已部署 \xB7 覆盖射击", 1.8);
    if (this.fx) this.fx.shake = Math.max(this.fx.shake, .22);
}
fireShell(m) {
    const fx0 = -Math.sin(m.yaw), fz0 = -Math.cos(m.yaw);
    const pos = new R(m.pos.x + fx0 * .45, m.pos.y + 1, m.pos.z + fz0 * .45);
    const dx = m.target.x - pos.x + (Math.random() - .5) * __CAN_SPREAD__ * 2;
    const dz = m.target.z - pos.z + (Math.random() - .5) * __CAN_SPREAD__ * 2;
    const dy = m.target.y - pos.y;
    const span = Math.max(1, Math.hypot(dx, dz));
    const fly = Math.min(2, Math.max(.75, span / 13));
    const mesh = Na("he");
    mesh.scale.setScalar(.62);
    mesh.position.copy(pos);
    this.renderer.scene.add(mesh);
    Jt.playGrenadeThrow();
    if (this.fx) this.fx.light(pos, 12, .1, 16758512, 6);
    return { kind: "shell", mesh, pos, owner: m.owner, fuse: 4,
        vel: new R(dx / fly, dy / fly + .5 * __CAN_G__ * fly, dz / fly),
        spin: new R(Math.random() * 10, Math.random() * 10, 0) };
}
updateMortars(dt) {
    const list = this.mortars;
    if (!list || !list.length) return;
    const world = this.world, G = __CAN_G__, spawned = [];
    const kept = list.filter((m) => {
        if (m.kind === "device") {
            m.life += dt;
            if (m.life >= m.deploy) {
                if (m.shots > 0) {
                    if (m.life >= m.next) {
                        m.next = m.life + __CAN_INTERVAL__;
                        m.shots--;
                        const sh = this.fireShell(m);
                        sh && spawned.push(sh);
                    }
                } else if (m.life >= m.next + 1) {
                    this.renderer.scene.remove(m.mesh);
                    return !1;
                }
            }
            return !0;
        }
        const steps = 3, s = dt / steps;
        let hit = !1;
        for (let a = 0; a < steps; a++) {
            m.vel.y -= G * s;
            const sp = m.vel.length();
            if (sp < 1e-4) continue;
            const dir = m.vel.clone().divideScalar(sp);
            const reach = sp * s + .06;
            const wall = world.raycast(m.pos.x, m.pos.y, m.pos.z, dir.x, dir.y, dir.z, reach, "move");
            if (wall) { m.pos.addScaledVector(dir, Math.max(0, wall.t - .06)); hit = !0; break; }
            m.pos.addScaledVector(m.vel, s);
        }
        m.fuse -= dt;
        m.mesh.position.copy(m.pos);
        m.mesh.rotation.x += m.spin.x * dt;
        m.mesh.rotation.y += m.spin.y * dt;
        if (!hit) {
            for (const act of this.actors) {
                if (!act.alive || act === m.owner) continue;
                if (act.pos.distanceTo(m.pos) < 1.15) { hit = !0; break; }
            }
        }
        if (this.fx) this.fx.add.emit({ x: m.pos.x, y: m.pos.y, z: m.pos.z,
            vx: 0, vy: .2, vz: 0, life: 0, max: .28, s0: .17, s1: .02,
            r: 1.1, g: .78, b: .42, a0: .5, a1: 0, grav: 0, drag: 2 });
        if (hit || m.fuse <= 0) {
            this.explode(m.pos.clone(), m.owner, { dmg: __CAN_DMG__, radius: __CAN_RADIUS__ });
            this.renderer.scene.remove(m.mesh);
            return !1;
        }
        return !0;
    });
    this.mortars = kept.concat(spawned);
}
'''
for token, value in [("__CAN_CD__", CAN_CD), ("__CAN_DEPLOY__", CAN_DEPLOY),
                     ("__CAN_SHOTS__", CAN_SHOTS), ("__CAN_INTERVAL__", CAN_INTERVAL),
                     ("__CAN_RANGE__", CAN_RANGE), ("__CAN_SPREAD__", CAN_SPREAD),
                     ("__CAN_DMG__", CAN_DMG), ("__CAN_RADIUS__", CAN_RADIUS),
                     ("__CAN_G__", CAN_G)]:
    assert token in cannon_method, token
    cannon_method = cannon_method.replace(token, value)

# ---------------------------------------------------------- 联机（?mp=1 门控）
# 客户端权威 + 服务器哑中继（mp_server.js）。每个客户端只管自己的角色；host=玩家1 兼管 bot。
# 不带 ?mp=1 时下面所有 this.mp 分支都为假，单机路径完全不变。
net_method = r'''
netConnect() {
    if (this._ws) return;
    this.remotes = this.remotes || {};
    this.netAcc = 0;
    let url = (location.protocol === "https:" ? "wss://" : "ws://") + location.host;
    let ws;
    try { ws = new WebSocket(url); } catch (e) { return; }
    this._ws = ws;
    ws.onopen = () => this.netSend({ t: "join", team: this.opts ? this.opts.team : "BL" });
    ws.onmessage = (e) => { try { this.onNetMsg(JSON.parse(e.data)); } catch (err) {} };
    ws.onclose = () => { this._ws = null; };
    ws.onerror = () => {};
    if (!this._grabWired) { // F1 抢房主（无限制，随时可抢）；F2 房主在大厅终止正在进行的对局
        this._grabWired = true;
        window.addEventListener("keydown", (ev) => {
            if (ev.code === "F1" && this.mp) {
                ev.preventDefault();
                // 抢房主无限制；若我此刻在大厅（没进战场）则连带终止正在进行的对局，把大家拉回大厅
                if (!this.isHost) this.netSend({ t: "grabhost", end: !this.playing });
            } else if (ev.code === "F2" && this.mp) {
                ev.preventDefault();
                // 房主在大厅等待（自己没进战场）且前面有对局在跑 → 一键终止那局，全体回大厅
                if (this.isHost && !this.playing && this.roomState === "playing") {
                    this.netSend({ t: "end" });
                    this.roomState = "lobby"; this.pendingStart = null;
                    if (this.hud && this.hud.toast) this.hud.toast("已终止当前对局", 1.5);
                    this.renderLobby();
                }
            }
        });
    }
}
netSend(o) {
    let w = this._ws;
    if (w && w.readyState === 1) { try { w.send(JSON.stringify(o)); } catch (e) {} }
}
netOwns(a) {
    if (!a) return false;
    if (a === this.player) return true;
    return !!(this.isHost && a instanceof Fa && !a.isRemote);
}
onNetMsg(m) {
    if (m.t === "welcome") {
        this.netId = m.slot; this.isHost = !!m.host;
        if (m.cfg) this.roomCfg = m.cfg;
        this.roomState = m.state || "lobby";
        if (this.player) { this.player.netId = m.slot; this.player.name = "玩家" + m.slot; }
        this.renderLobby();
        return;
    }
    if (m.t === "host") { // 房主变更（顺延 / F1 抢夺）：据 netId 判定；对局中切换要收编 / 交还 bot 以免冻结
        let was = this.isHost;
        this.isHost = (m.slot == null) ? true : (m.slot === this.netId);
        if (this.isHost && !was) { if (this.hud && this.hud.toast) this.hud.toast("你已成为房主", 1.5); if (this.playing) this.adoptBots(); }
        else if (!this.isHost && was) { if (this.hud && this.hud.toast) this.hud.toast("房主已被接管", 1.5); if (this.playing) this.releaseBots(); }
        this.renderLobby(); return;
    }
    if (m.t === "roster") { this.netRoster = m.players; this.renderLobby(); return; }
    if (m.t === "config") { this.roomCfg = m.cfg || this.roomCfg; this.renderLobby(); return; }
    if (m.t === "start") { // 只有非房主会收到（服务器已排除房主）→ 需要一次点击手势进入
        this.roomState = "playing"; this.pendingStart = m.cfg || this.roomCfg; this.renderLobby(); return;
    }
    if (m.t === "end") { // 房主结束本局 → 全体回大厅
        this.roomState = "lobby"; this.pendingStart = null;
        if (this.playing || this.ended) this.netToLobby();
        this.renderLobby();
        return;
    }
    if (m.t === "leave") { this.removeRemote(m.slot); this.renderLobby(); return; }
    if (m.t === "score" && this.score) { this.score.BL = m.BL; this.score.GR = m.GR; return; }
    if (m.t === "stats") { this.netStats = m.stats || {}; this.applyNetStats(this.netStats); return; }
    if (m.t === "botsassign") { if (this.isHost && this.playing) this.adoptBots(); return; }
    if (!this.playing) return;
    if (m.t === "state" || m.t === "world") this.applyNetState(m);
    else if (m.t === "fire") this.netShowFire(m);
    else if (m.t === "hit") this.netTakeHit(m);
    else if (m.t === "frag") this.netShowKill(m);
}
netMine() {
    let out = [];
    if (this.player) out.push(this.player);
    if (this.isHost) for (let a of this.actors) if (a instanceof Fa && !a.isRemote) { if (a.netId == null) a.netId = 1000 + a.id; out.push(a); }
    return out;
}
netSnap(a) {
    return { id: a.netId, x: +a.pos.x.toFixed(2), y: +a.pos.y.toFixed(2), z: +a.pos.z.toFixed(2),
        yaw: +a.yaw.toFixed(3), pitch: +(a.pitch || 0).toFixed(3), sp: Math.round(a.speed || 0),
        cr: a.crouch ? 1 : 0, og: a.onGround ? 1 : 0, al: a.alive ? 1 : 0,
        hp: Math.max(0, Math.round(a.hp || 0)), w: a.weapon ? a.weapon.def.id : "ak47",
        nm: a.name, tm: a.team };
}
netUpdate(t) {
    if (!this._ws || !this.playing) return;
    let mine = this.netMine();
    for (let a of mine) {
        if (a._wa === undefined) a._wa = a.alive;
        if (a._wa && !a.alive) {
            if (a === this.player) this.dmgFlash = 0; // 清掉致命弹幕累积的红闪，避免死亡瞬间连闪
            let k = a.lastAttacker;
            this.netSend({ t: "frag", killer: k && k.netId ? k.netId : 0, killerName: k ? k.name : "",
                killerTeam: k && k.team ? k.team : null, victim: a.netId, victimName: a.name, victimTeam: a.team,
                w: a._lastW || (a.weapon ? a.weapon.def.id : "ak47"), hs: a._lastN === "head",
                team: k && k.team ? k.team : null });
        }
        a._wa = a.alive;
    }
    for (let id in this.remotes) {
        let av = this.remotes[id], g = av._nt;
        if (g) {
            let k = Math.min(1, t * 14);
            av.pos.x += (g.x - av.pos.x) * k;
            av.pos.y += (g.y - av.pos.y) * k;
            av.pos.z += (g.z - av.pos.z) * k;
            av.yaw = g.yaw; av.pitch = g.pitch;
        }
    }
    this.netAcc += t;
    if (this.netAcc >= .05) {
        this.netAcc = 0;
        if (this.netStats) this.applyNetStats(this.netStats); // 权威 stats 重写，覆盖晚创建的远程化身
        // 优化：只发「变化过」的实体（静止/死亡的 bot 不再每 tick 重发）；服务器再聚合成 world 按 tick 下发。
        this._kf = (this._kf || 0) + 1;
        let keyframe = this._kf % 20 === 0;
        let ents = [];
        for (let a of mine) if (a.netId != null) {
            let sn = this.netSnap(a);
            if (keyframe || this._snapDiff(a._ps, sn)) { ents.push(sn); a._ps = sn; }
        }
        if (ents.length) this.netSend({ t: "state", ents });
    }
}
_snapDiff(p, s) {
    if (!p) return true;
    if (p.al !== s.al || p.hp !== s.hp || p.w !== s.w || p.cr !== s.cr || p.og !== s.og || p.tm !== s.tm) return true;
    let dx = p.x - s.x, dy = p.y - s.y, dz = p.z - s.z;
    if (dx * dx + dy * dy + dz * dz > 9e-4) return true; // 位移 > ~0.03m
    let da = p.yaw - s.yaw, db = p.pitch - s.pitch;
    return da * da + db * db > 1e-4; // 转向 > ~0.01rad
}
applyNetState(m) {
    if (!m.ents || !this.playing) return;
    for (let s of m.ents) {
        if (s.id === this.netId) continue;
        if (s.id >= 1000) {
            let owned = null;
            for (let q of this.actors) if (q.netId === s.id && q instanceof Fa && !q.isRemote) { owned = q; break; }
            if (owned) continue;               // 我正在模拟这个 bot，忽略服务器回显
            if (this.isHost) {                 // 我是房主却还没接管它 → 收编为本地 bot 续算（补齐迁移遗漏）
                let rav = this.remotes[s.id];
                if (!rav) rav = this.addRemote(s);
                if (rav) { rav.isRemote = !1; delete this.remotes[s.id]; }
                continue;
            }
        }
        let av = this.remotes[s.id];
        if (!av) av = this.addRemote(s);
        if (!av) continue;
        av._nt = { x: s.x, y: s.y, z: s.z, yaw: s.yaw, pitch: s.pitch };
        av.speed = s.sp; av.crouch = !!s.cr; av.onGround = !!s.og; av.pitch = s.pitch;
        let wasAlive = av.alive;
        av.alive = !!s.al; av.hp = s.hp; av.protectT = 0;
        if (av.alive && !wasAlive) { av.deadT = 0; av._pk = 0; av._ph = null; if (av.soldier && av.soldier.reset) { try { av.soldier.reset(); } catch (e) {} } }
        else if (!av.alive && wasAlive && av.soldier && av.soldier.die) { try { av.soldier.die(av.pos.x, av.pos.z, "chest"); } catch (e) {} }
        // 兜底：快照说活着但 soldier 还卡在死亡趴地姿势（滑铲后死亡再生、丢包错序等）→ 强制起身。
        // 远程化身永远不走 spawnActor→spawn→soldier.reset()，只能在这里手动复位，否则永久躺地。
        if (av.alive && av.soldier && av.soldier.deadT >= 0 && av.soldier.reset) { try { av.soldier.reset(); } catch (e) {} }
    }
}
addRemote(s) {
    if (!this.playing) return null;
    let av;
    // 本地 Fa.id 用单调自增（5000+），与 netId 解耦——避免「真人 netId」与「host bot netId=1000+id」
    // 取模后撞成同一个 Fa.id（3+ 人/多 bot 时会重叠），路由始终用 netId + remotes 表。
    this._rseq = (this._rseq || 0) + 1;
    try { av = new Fa(this, { id: 5000 + this._rseq, name: s.nm || ("玩家" + s.id), team: s.tm || "GR", diff: "normal" }); }
    catch (e) { return null; }
    av.isRemote = !0; av.netId = s.id;
    av.pos.set(s.x, s.y != null ? s.y : .02, s.z); av.yaw = s.yaw || 0; av.pitch = s.pitch || 0;
    av.alive = !!s.al; av.hp = s.hp != null ? s.hp : 100; av.protectT = 0;
    av._nt = { x: s.x, y: s.y != null ? s.y : .02, z: s.z, yaw: s.yaw || 0, pitch: s.pitch || 0 };
    this.actors.push(av); this.remotes[s.id] = av;
    try { this.addTag(av); } catch (e) {}
    return av;
}
removeRemote(id) {
    let av = this.remotes[id];
    if (!av) return;
    try { this.renderer.scene.remove(av.soldier.root); } catch (e) {}
    let ix = this.actors.indexOf(av); if (ix >= 0) this.actors.splice(ix, 1);
    for (let j = this.tags.length - 1; j >= 0; j--) if (this.tags[j].actor === av) {
        try { this.renderer.scene.remove(this.tags[j].sprite); } catch (e) {}
        this.tags.splice(j, 1);
    }
    delete this.remotes[id];
}
netFire(origin, dir, w) {
    this.netSend({ t: "fire", ox: +origin.x.toFixed(2), oy: +origin.y.toFixed(2), oz: +origin.z.toFixed(2),
        dx: +dir.x.toFixed(3), dy: +dir.y.toFixed(3), dz: +dir.z.toFixed(3), w: w });
}
netShowFire(m) {
    try {
        let from = new R(m.ox, m.oy, m.oz);
        if (this.fx && this.fx.light) this.fx.light(from, 14, .05, 16758512, 8);
        if (mi[m.w] && Jt.playShot) Jt.playShot(mi[m.w].sound, from);
    } catch (e) {}
}
netHit(victim, attacker, dmg, region, w) {
    if (attacker.netId == null && attacker instanceof Fa) attacker.netId = 1000 + attacker.id;
    this.netSend({ t: "hit", target: victim.netId, dmg: dmg, region: region, w: w,
        killer: attacker.netId || 0, killerName: attacker.name || "", from: this.netId,
        pos: { x: +attacker.pos.x.toFixed(1), y: +attacker.pos.y.toFixed(1), z: +attacker.pos.z.toFixed(1) } });
}
netTakeHit(m) {
    let victim = null;
    if (this.player && this.player.netId === m.target) victim = this.player;
    else if (this.isHost) for (let a of this.actors) if (a instanceof Fa && !a.isRemote && a.netId === m.target) { victim = a; break; }
    if (!victim || !victim.alive) return;
    let atk = { team: victim.team === "BL" ? "GR" : "BL", name: m.killerName || ("玩家" + m.killer),
        netId: m.killer, isRemote: !0, stats: { hits: 0 },
        pos: m.pos ? new R(m.pos.x, m.pos.y, m.pos.z) : victim.pos.clone() };
    try { this.damage(victim, atk, m.dmg, m.region || "chest", m.w || "ak47", new R(0, 0, 0), !1); } catch (e) {}
}
netFindByNet(id) {
    // 按网络身份 netId 找本地 actor（自己 / host bot / 远程化身都带 netId）。每个客户端对每个联机实体
    // 都持有一个 actor（自己拥有的或远程化身），故据 kill 广播在所有端一致累加统计，计分板才人人对齐。
    if (id == null) return null;
    if (this.player && this.player.netId === id) return this.player;
    for (let a of this.actors) if (a.netId === id) return a;
    return null;
}
applyNetStats(map) {
    // 服务器权威 stats 表 → 写进各本地 actor（自己 / host bot / 远程化身都据 netId 可查）。
    // 幂等覆盖：晚创建的远程化身会在后续 tick 被补写，故计分板在所有端一致（根治「只有一个人有击杀数据」）。
    if (!map) return;
    for (let id in map) {
        let a = this.netFindByNet(+id);
        if (a && a.stats) { a.stats.k = map[id].k; a.stats.d = map[id].d; a.stats.hs = map[id].hs; }
    }
}
adoptBots() {
    // 成为房主：把手里所有 bot 远程化身翻成本地拥有 → 引擎主循环开始为其跑 AI，不再冻结（根治换房主 bot 冻结）。
    for (let a of this.actors) if (a instanceof Fa && a.isRemote && a.netId >= 1000) {
        a.isRemote = !1; delete this.remotes[a.netId];
    }
}
releaseBots() {
    // 被降级：把本地拥有的 bot 交还为远程化身 → 停止本地 AI，改由新房主的 world 快照驱动（避免两端同时模拟同一 bot）。
    for (let a of this.actors) if (a instanceof Fa && !a.isRemote && a.netId >= 1000) {
        a.isRemote = !0; this.remotes[a.netId] = a;
        a._nt = a._nt || { x: a.pos.x, y: a.pos.y, z: a.pos.z, yaw: a.yaw, pitch: a.pitch || 0 };
    }
}
_predKill(victim, hs, w) {
    // 本地击杀预测：命中把远程化身预测血量打到 <=0 时**立刻**给击杀横幅 + 音效，消除等服务器 frag 回传的
    // 「几秒延迟」感。计分仍以服务器权威 stats 为准；服务器 frag 回来时若已预测过就跳过重复横幅（见 netShowKill）。
    this._nkN = (this.time - (this._nkT == null ? -99 : this._nkT) < 5) ? (this._nkN || 1) + 1 : 1;
    this._nkT = this.time;
    let l = Math.min(this._nkN, 8), c, h = "击杀 " + (victim.name || "敌人");
    if (l >= 2 && typeof Kf !== "undefined") {
        c = Kf[l]; h = Ay[l] + " \xB7 " + h;
        setTimeout(() => { try { Jt.announce(Kf[l].toLowerCase().replace(/\b\w/g, u => u.toUpperCase()) + "!"); } catch (e) {} }, 120);
    } else if (hs) { c = "HEADSHOT"; h = "爆头 \xB7 " + h; setTimeout(() => { try { Jt.announce("Headshot!"); } catch (e) {} }, 120); }
    else if (w === "knife") c = "KNIFE KILL";
    else if (w === "he") c = "GRENADE KILL";
    else c = "KILL";
    try { this.hud.badge(c, h, hs); Jt.playKillConfirm(hs); } catch (e) {}
}
netShowKill(m) {
    // feature3: 联机击杀反馈——复用原版 killFeed / badge / 击杀播报音（Kf/Ay/playKillConfirm/announce）。
    let killer = m.killerName ? { name: m.killerName, team: m.killerTeam || "GR" } : null;
    let victim = { name: m.victimName || ("玩家" + m.victim), team: m.victimTeam || "BL" };
    let hs = !!m.hs, w = m.w || "ak47";
    let involves = m.killer === this.netId || m.victim === this.netId;
    // 计分完全走服务器权威 stats 表（applyNetStats），此处只负责视听展示：killFeed / 多杀横幅 / 播报音。
    try { if (this.hud && this.hud.killFeed) this.hud.killFeed(killer, victim, w, hs, !1, involves); } catch (e) {}
    // 服务器权威 frag 一到就地放倒受害者化身，不等它自己上报 al:0——受害者端卡顿/浏览器后台节流时
    // 快照会滞后好几秒，模型就会「人死了还站着」。frag 是服务器唯一击杀事件，据它放倒最及时。
    let _vv = this.netFindByNet(m.victim);
    if (_vv && _vv !== this.player && _vv.alive) {
        _vv.alive = !1; _vv.hp = 0; _vv._pk = 0; _vv._ph = null;
        if (_vv.soldier && _vv.soldier.die) { try { _vv.soldier.die(_vv.pos.x, _vv.pos.z, hs ? "head" : "chest"); } catch (e) {} }
    }
    if (m.killer === this.netId) {
        let _va = this.netFindByNet(m.victim);
        if (_va && _va._pk) { _va._pk = 0; _va._ph = null; } // 已本地预测击杀，跳过重复横幅（去抖）
        else {
        // 我击杀：本地维护一个简单多杀计数（5s 窗口），复用原版横幅 + 语音播报
        this._nkN = (this.time - (this._nkT == null ? -99 : this._nkT) < 5) ? (this._nkN || 1) + 1 : 1;
        this._nkT = this.time;
        let l = Math.min(this._nkN, 8), c, h = "击杀 " + victim.name;
        if (l >= 2 && typeof Kf !== "undefined") {
            c = Kf[l]; h = Ay[l] + " \xB7 " + h;
            setTimeout(() => { try { Jt.announce(Kf[l].toLowerCase().replace(/\b\w/g, u => u.toUpperCase()) + "!"); } catch (e) {} }, 150);
        } else if (hs) {
            c = "HEADSHOT"; h = "爆头 \xB7 " + h;
            setTimeout(() => { try { Jt.announce("Headshot!"); } catch (e) {} }, 150);
        } else if (w === "knife") c = "KNIFE KILL";
        else if (w === "he") c = "GRENADE KILL";
        else c = "KILL";
        try { this.hud.badge(c, h, hs); Jt.playKillConfirm(hs); } catch (e) {}
        }
    }
}
enterLobby() {
    if (this.playing) return;
    this.mp = !0;
    this.roomCfg = this.roomCfg || { size: 5, diff: "normal", goal: 50, tod: "day" };
    this.netConnect();
    this.netShowLobby();
}
netHumanCounts() {
    let m = { BL: 0, GR: 0 }, r = this.netRoster || [];
    for (let p of r) if (p.team === "BL" || p.team === "GR") m[p.team]++;
    if (!r.length && this.player && this.player.team) m[this.player.team] = 1;
    return m;
}
applyRoomCfg() {
    let c = this.roomCfg; if (!c) return;
    if (c.size) this.opts.size = c.size;
    if (c.diff) this.opts.diff = c.diff;
    if (c.goal) this.opts.goal = c.goal;
    if (c.tod) this.opts.tod = c.tod;
}
netStartHost() {
    this.applyRoomCfg();
    this.netSend({ t: "start" });
    this.roomState = "playing"; this.pendingStart = null;
    this.netHideLobby();
    this.startMatch();
}
netEnterMatch() {
    this.applyRoomCfg();
    this.roomState = "playing"; this.pendingStart = null;
    this.netHideLobby();
    this.startMatch();
}
netEndMatch() {
    if (!this.mp) return;
    if (this.isHost) this.netSend({ t: "end" });
    this.roomState = "lobby"; this.pendingStart = null;
}
netToLobby() {
    try { navigator.keyboard && navigator.keyboard.unlock && navigator.keyboard.unlock(); } catch (e) {}
    try { document.fullscreenElement && document.exitFullscreen && document.exitFullscreen().catch(() => {}); } catch (e) {}
    try { document.pointerLockElement && document.exitPointerLock(); } catch (e) {}
    this.playing = !1; this.ended = !1;
    // feature3: 回大厅前把上一局的网格从场景移除，否则下一局 startMatch 时 this.actors 已被清空、
    // 清理循环无从下手，旧的士兵/名牌/手雷/虎蹲炮网格会残留在场景里影响新对局。
    try {
        let sc = this.renderer && this.renderer.scene;
        if (sc) {
            for (let a of (this.actors || [])) { try { sc.remove(a.soldier.root); } catch (e) {} }
            for (let g of (this.tags || [])) { try { sc.remove(g.sprite); } catch (e) {} }
            for (let g of (this.nades || [])) { try { sc.remove(g.mesh); } catch (e) {} }
            for (let g of (this.mortars || [])) { try { sc.remove(g.mesh); } catch (e) {} }
        }
    } catch (e) {}
    this.actors = []; this.tags = []; this.nades = []; this.mortars = []; this.player = null; this.remotes = {};
    try { this.vm && this.vm.setVisible(!1); } catch (e) {}
    this.hud.show("menu");
    this.netShowLobby();
}
netShowLobby() {
    let box = document.getElementById("mpLobby");
    if (!box) {
        box = document.createElement("div");
        box.id = "mpLobby";
        box.style.cssText = "position:fixed;inset:0;z-index:200;background:rgba(8,12,18,.92);color:#e8eef4;font:14px/1.5 system-ui,sans-serif;display:flex;align-items:center;justify-content:center";
        box.innerHTML = '<div style="width:min(720px,94vw);background:#121a24;border:1px solid #2a3b4d;border-radius:12px;padding:22px 24px;box-shadow:0 12px 40px #000a"><div style="font-size:20px;font-weight:700;letter-spacing:1px">联机房间</div><div id="mpSub" style="color:#8fa6bd;margin:4px 0 14px"></div><div id="mpTeams" style="display:flex;gap:14px"></div><div id="mpCfg" style="margin-top:16px"></div><div id="mpAct" style="margin-top:18px;display:flex;gap:10px;align-items:center;flex-wrap:wrap"></div></div>';
        document.body.appendChild(box);
    }
    box.style.display = "flex";
    this.renderLobby();
}
netHideLobby() { let b = document.getElementById("mpLobby"); if (b) b.style.display = "none"; }
renderLobby() {
    let box = document.getElementById("mpLobby");
    if (!box || box.style.display === "none") return;
    let cfg = this.roomCfg || { size: 5, diff: "normal", goal: 50, tod: "day" };
    let roster = this.netRoster || [], me = this.netId, host = this.isHost;
    document.getElementById("mpSub").textContent = "你是 玩家" + (me || "?") + (host ? "（房主）" : "")
        + " \xB7 " + cfg.size + "v" + cfg.size + (this.roomState === "playing" ? " \xB7 对局进行中" : "");
    let teamsEl = document.getElementById("mpTeams");
    let mk = (tm, label) => {
        let players = roster.filter(p => p.team === tm), bots = Math.max(0, cfg.size - players.length);
        let mine = roster.find(p => p.slot === me), on = mine && mine.team === tm;
        let rows = players.map(p => '<div style="padding:4px 8px;border-radius:6px;background:#1b2836;margin:4px 0">'
            + (p.slot === me ? "▶ " : "") + "玩家" + p.slot + (p.host ? " \u{1F451}" : "") + "</div>").join("");
        for (let i = 0; i < bots; i++) rows += '<div style="padding:4px 8px;border-radius:6px;background:#141d28;margin:4px 0;color:#6d8199">人机</div>';
        return '<div style="flex:1"><button data-team="' + tm + '" class="mpJoin" style="width:100%;padding:8px;border-radius:8px;border:1px solid '
            + (on ? "#4a90d9" : "#2a3b4d") + ';background:' + (on ? "#1d3550" : "#16212e") + ';color:#e8eef4;cursor:pointer;font-weight:600">'
            + label + (on ? "（我方）" : "") + "</button>" + rows + "</div>";
    };
    teamsEl.innerHTML = mk("BL", "潜伏者 BL") + mk("GR", "保卫者 GR");
    for (let b of teamsEl.querySelectorAll(".mpJoin")) b.addEventListener("click", () => {
        let tm = b.dataset.team; this.opts.team = tm; this.netSend({ t: "join", team: tm }); this.renderLobby();
    });
    let cfgEl = document.getElementById("mpCfg");
    if (host && this.roomState !== "playing") {
        let seg = (key, label, vals) => {
            let btns = vals.map(v => '<button data-ck="' + key + '" data-cv="' + v[0] + '" style="padding:6px 10px;border-radius:6px;border:1px solid '
                + (String(cfg[key]) === String(v[0]) ? "#4a90d9" : "#2a3b4d") + ';background:' + (String(cfg[key]) === String(v[0]) ? "#1d3550" : "#16212e")
                + ';color:#e8eef4;cursor:pointer;margin:0 4px 6px 0">' + v[1] + "</button>").join("");
            return '<div style="margin:6px 0"><span style="color:#8fa6bd;display:inline-block;width:88px">' + label + "</span>" + btns + "</div>";
        };
        cfgEl.innerHTML = seg("size", "每队人数", [[4, "4v4"], [5, "5v5"], [6, "6v6"], [8, "8v8"]])
            + seg("diff", "人机难度", [["easy", "简单"], ["normal", "普通"], ["hard", "困难"], ["hell", "地狱"]])
            + seg("goal", "胜利分数", [[30, "30"], [50, "50"], [100, "100"]])
            + seg("tod", "时间", [["day", "白天"], ["dusk", "黄昏"]]);
        for (let b of cfgEl.querySelectorAll("button")) b.addEventListener("click", () => {
            let k = b.dataset.ck, v = b.dataset.cv; v = isNaN(+v) ? v : +v;
            this.roomCfg[k] = v; this.netSend({ t: "config", cfg: this.roomCfg }); this.renderLobby();
        });
    } else {
        cfgEl.innerHTML = '<div style="color:#8fa6bd">配置：' + cfg.size + "v" + cfg.size + " \xB7 难度 " + cfg.diff
            + " \xB7 目标 " + cfg.goal + " \xB7 " + (cfg.tod === "dusk" ? "黄昏" : "白天") + (host ? "" : "（仅房主可改）") + "</div>";
    }
    let actEl = document.getElementById("mpAct");
    actEl.innerHTML = "";
    let btn = (txt, cb) => { let e = document.createElement("button"); e.textContent = txt; e.style.cssText = "padding:10px 20px;border-radius:8px;border:none;background:#4a90d9;color:#fff;font-weight:700;cursor:pointer;font-size:15px"; e.addEventListener("click", cb); actEl.appendChild(e); };
    let note = t => { let e = document.createElement("span"); e.textContent = t; e.style.color = "#8fa6bd"; actEl.appendChild(e); };
    if (this.roomState === "playing") { btn("加入战场", () => this.netEnterMatch()); if (host) note("按 F2 终止当前对局"); } // 热加入：对局进行中也可直接进入
    else if (host) btn("开始对局", () => this.netStartHost());
    else note("等待房主开始…");
    let back = document.createElement("button");
    back.textContent = "退出联机";
    back.style.cssText = "padding:10px 16px;border-radius:8px;border:1px solid #2a3b4d;background:#16212e;color:#cbd6e2;cursor:pointer";
    back.addEventListener("click", () => { try { this._ws && this._ws.close(); } catch (e) {} this._ws = null; this.mp = !1; this.netHideLobby(); });
    actEl.appendChild(back);
}
'''

# 1) init：不再用 ?mp=1 直接置 mp；改由菜单「联机」按钮进大厅。但保留 ?mp=1 作为「自动进大厅」
#    的快捷方式（服务器 / 会把玩家重定向到 ?mp=1，一进来就直接是联机流程）。setTimeout 让 init 跑完再进。
net_init_old = "this.hud=new oc(this),this.opts=this.hud.opts,"
net_init_new = "this.hud=new oc(this),this.opts=this.hud.opts,this.mp=!1,this.qs.has(\"mp\")&&setTimeout(()=>this.enterLobby(),0),"
assert html.count(net_init_old) == 1, "net init marker"
html = html.replace(net_init_old, net_init_new, 1)

# 2) startMatch：用所选阵营重新 join，给本地玩家挂 netId 和「玩家N」名字
net_start_old = "this.actors.push(this.player);"
net_start_new = ("this.actors.push(this.player),this.mp&&(this.netSend({t:\"join\",team:e}),"
                 "this.player.netId=this.netId,this.netId&&(this.player.name=\"\\u73a9\\u5bb6\"+this.netId),this.remotes={});")
assert html.count(net_start_old) == 1, "net startMatch marker"
html = html.replace(net_start_old, net_start_new, 1)

# 3) 非 host（或 host 未知）在联机时不生成本地 bot 花名册——bot 只由 host 生成并作为远程化身广播
net_bot_old = 'for(let h=0;h<c;h++){let u=new Fa(this,{id:s++,name:n.pop()||"Bot"+s,team:l,diff:t.diff});'
net_bot_new = 'for(let h=0;h<c&&(!this.mp||this.isHost);h++){let u=new Fa(this,{id:s++,name:n.pop()||"Bot"+s,team:l,diff:t.diff});'
assert html.count(net_bot_old) == 1, "net bot-gate marker"
html = html.replace(net_bot_old, net_bot_new, 1)

# 3b) 联机时按房间人数补齐 bot：每队 bot 数 = size - 该队真人数（真人含本地玩家，从 roster 统计）。
#     单机时保持原逻辑（本队 a-1、敌队 a）。只有 host 真正生成 bot（见 3 的门控）。
net_count_old = 'for(let l of[e,i]){let c=l===e?a-1:a;'
net_count_new = 'let __hm=this.mp?this.netHumanCounts():null;for(let l of[e,i]){let c=__hm?Math.max(0,a-(__hm[l]||0)):(l===e?a-1:a);'
assert html.count(net_count_old) == 1, "net bot-count marker"
html = html.replace(net_count_old, net_count_new, 1)

# 3c) endMatch：联机时通知服务器本局结束（房主发 end→全体回大厅）
net_end_old = "endMatch(){this.ended=!0,this.playing=!1;"
net_end_new = "endMatch(){this.mp&&this.netEndMatch();this.ended=!0,this.playing=!1;"
assert html.count(net_end_old) == 1, "net endMatch marker"
html = html.replace(net_end_old, net_end_new, 1)

# 3d) 菜单加「联机对战」按钮（单机仍走原 btnStart）；再把按钮接到 enterLobby
menu_btn_old = 'id="btnStart">\\u5F00 \\u59CB \\u6E38 \\u620F</button>'
menu_btn_new = ('id="btnStart">\\u5F00 \\u59CB \\u6E38 \\u620F</button>'
                '<button class="go" id="btnMulti" style="margin-top:10px;background:#2f6fb3">'
                '\\u8054\\u673A\\u5BF9\\u6218</button>')
assert html.count(menu_btn_old) == 1, "menu btnMulti marker"
html = html.replace(menu_btn_old, menu_btn_new, 1)

net_wire_old = 'Yn("#btnStart").addEventListener("click",()=>this.g.startMatch()),'
net_wire_new = ('Yn("#btnStart").addEventListener("click",()=>this.g.startMatch()),'
                'Yn("#btnMulti")&&Yn("#btnMulti").addEventListener("click",()=>this.g.enterLobby()),')
assert html.count(net_wire_old) == 1, "net btnMulti wire marker"
html = html.replace(net_wire_old, net_wire_new, 1)

# 4) 主循环：远程化身不跑 AI；每帧驱动联机（发本地快照 / 插值远程 / 判死播报）
net_loop_old = "for(let i of this.actors)i.isPlayer||i.update(t);"
net_loop_new = "for(let i of this.actors)i.isPlayer||i.isRemote||i.update(t);this.mp&&this.netUpdate(t);"
assert html.count(net_loop_old) == 1, "net mainloop marker"
html = html.replace(net_loop_old, net_loop_new, 1)

# 5) damage：打到「远程化身」时本地不扣血，改成把命中发给该化身的属主（属主本地权威扣血）
net_dmg_old = "damage(t,e,i,n,s,a,o,l){if(!t.alive"
net_dmg_new = ("damage(t,e,i,n,s,a,o,l){if(this.mp&&t.isRemote){"
               "let _ok=t.alive&&t.protectT<=0&&e&&e.team!==t.team;"
               "this.netOwns(e)&&_ok&&this.netHit(t,e,i,n,s);"
               "if(e===this.player&&_ok){this.hud.hitmarker(n===\"head\",!1),Jt.playHitmarker(n===\"head\");"
               "t._ph=(t._ph==null?t.hp:t._ph)-i;if(t._ph<=0&&!t._pk){t._pk=1,this._predKill(t,n===\"head\",s)}}"
               "return}if(!t.alive")
assert html.count(net_dmg_old) == 1, "net damage marker"
html = html.replace(net_dmg_old, net_dmg_new, 1)

# 6) feature3: 记录受害者最后一次被打的武器/部位，供联机击杀播报复用
#    （本地命中与网络命中 netTakeHit 最终都会经过 damage，所以在这里存最稳）
dmg_cap_old = "t.lastAttacker=e,t.lastHurt=this.time;"
dmg_cap_new = "t.lastAttacker=e,t.lastHurt=this.time,t._lastW=s,t._lastN=n;"
assert html.count(dmg_cap_old) == 1, "damage capture marker"
html = html.replace(dmg_cap_old, dmg_cap_new, 1)

# 7) feature1: 联机时 kill() 的本地统计/计分/击杀播报全部屏蔽（改由服务器 kill 广播 → netShowKill
#    在每个客户端一致累加，见 netFindByNet）。否则只有「本地权威那一方」的 actor 有击杀数、其余为 0，
#    且会与 netShowKill 的播报/killfeed 双份触发（表现为死亡瞬间「闪」几下）。单机路径 this.mp 假，全不受影响。
kill_death_old = "t.respawnT=4,t.stats.d++,"
kill_death_new = "t.respawnT=4,this.mp||t.stats.d++,"
assert html.count(kill_death_old) == 1, "kill death-count marker"
html = html.replace(kill_death_old, kill_death_new, 1)

kill_score_old = "if(e&&e!==t&&(e.stats.k++,n&&e.stats.hs++,this.score[e.team]++,"
kill_score_new = "if(e&&e!==t&&!this.mp&&(e.stats.k++,n&&e.stats.hs++,this.score[e.team]++,"
assert html.count(kill_score_old) == 1, "kill scoring marker"
html = html.replace(kill_score_old, kill_score_new, 1)

kill_feed_old = "this.hud.killFeed(e&&e!==t?e:null,t,i,n,s,e===o||t===o),e===o&&t!==o){"
kill_feed_new = "this.mp||this.hud.killFeed(e&&e!==t?e:null,t,i,n,s,e===o||t===o),!this.mp&&e===o&&t!==o){"
assert html.count(kill_feed_old) == 1, "kill feed/badge marker"
html = html.replace(kill_feed_old, kill_feed_new, 1)

# 8) feature3: startMatch 重置时清理虎蹲炮网格（原版只清 actors/tags/nades，漏了 this.mortars）+ 复位
#    remotes/mortars 数组，避免上一局的炮身/在飞炮弹/远程化身残留到下一局（单机重开同样受益）。
start_reset_old = "this.actors=[],this.nades=[],this.tags=[],this.timers=[]"
start_reset_new = ("(this.mortars||[]).forEach(x=>{try{this.renderer.scene.remove(x.mesh)}catch(e){}}),"
                   "this.actors=[],this.nades=[],this.tags=[],this.mortars=[],this.remotes={},this.timers=[]")
assert html.count(start_reset_old) == 1, "startMatch reset marker"
html = html.replace(start_reset_old, start_reset_new, 1)

html = html.replace(old_trace, lock_method + skill_method + cannon_method + net_method + old_trace, 1)

hint = "点击开始后鼠标将被锁定，按 Esc 暂停。画质切换会重新加载页面。".encode("unicode_escape").decode("ascii")
hint = re.sub(r"\\u([0-9a-f]{4})", lambda m: "\\u" + m[1].upper(), hint)
assert hint in html
html = html.replace(hint, hint + " 持步枪/冲锋枪/手枪时按住右键开镜，散布更小、移动更慢。按 Ctrl 滑铲（有冷却），按 V 向前喷气冲刺（可空中使用）。按 G 在脚下架设虎蹲炮，朝准星方向抛射 6 发炮弹覆盖落点（冷却 20 秒，注意别站在自己落点里）。", 1)

target.write_text(html, encoding="utf-8")
print(target)
