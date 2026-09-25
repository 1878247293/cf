# cf

本地网页 FPS 小游戏（Three.js，transport-ship）的**个人自娱增强副本** + **零依赖联机中继服务器**。仅供本人离线娱乐 / 学习编译产物注入技术，非官方、无反作弊、不涉及任何真实联网对战平台。

## 文件

| 文件 | 说明 |
|------|------|
| `page.html` | 原始游戏页（第三方内容，作为构建输入，见下方版权说明） |
| `build_lockon_copy.py` | 构建脚本：对 `page.html` 做字符串标记注入（每处 `assert count==1` 保证唯一命中），产出 `transport-ship-lockon.html`。**相对路径，须在本目录内运行** |
| `transport-ship-lockon.html` | 构建产物（勿手改，改 `build_lockon_copy.py` 后重建） |
| `mp_server.js` | 纯 Node 零依赖联机中继（自实现 RFC6455 WebSocket 握手 + 帧读写） |
| `start_server.bat` | 一键启动服务器 |
| `test_mp_server.js` | 服务器集成测试（真实 WebSocket 双客户端） |

## 增强内容（`build_lockon_copy.py` 注入）

- **锁头**（L 开关）、**开镜 ADS**（右键，含步枪/冲锋枪/手枪）
- **角色技能**：Ctrl 滑铲 / V 向前喷气
- **虎蹲炮**（G 键，部署式覆盖炮）
- **全屏 + Keyboard Lock**（抑制浏览器保留快捷键，Chromium 系）
- **联机对战**（`?mp=1` 门控）：客户端权威 + 哑中继模型，多真人同局，bot 补齐空位，玩家自选阵营

## 构建

```bash
python build_lockon_copy.py    # 在本目录内运行，产出 transport-ship-lockon.html
```

## 联机运行

```bash
node mp_server.js              # 默认端口 8080，可用 PORT 环境变量覆盖
# 玩家打开 http://<服务器IP或域名>:端口/  自动跳到 ?mp=1
node test_mp_server.js         # 跑服务器集成测试
```

> ⚠️ **联机服务器无鉴权**：任何拿到地址的人都能加入，且客户端权威模型可被篡改。仅限熟人自娱，勿部署到业务/敏感服务器；建议用冷门端口、随用随关，并开放对应防火墙/安全组端口。

## 版权说明

`page.html` / `transport-ship-lockon.html` 中的游戏本体为**第三方版权内容**，此处仅作个人学习与离线娱乐留存，不主张任何权利，亦不提供开源许可。请勿用于商业或再分发用途。
