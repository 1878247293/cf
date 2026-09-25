@echo off
REM 一键启动联机服务器（服务器权威记账 + world 聚合下发）
REM 双击本文件即可；玩家用浏览器打开 http://<本机IP>:8080/
cd /d "%~dp0"

REM 端口（如需改动改这里）
if "%PORT%"=="" set PORT=8080

REM 检查 node 是否可用
where node >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 node，请先安装 Node.js 并加入 PATH。
  pause
  exit /b 1
)

REM 检查已编译的游戏页是否存在
if not exist "transport-ship-lockon.html" (
  echo [提示] 未找到 transport-ship-lockon.html，尝试用 build_lockon_copy.py 重建...
  where python >nul 2>nul
  if errorlevel 1 (
    echo [错误] 也未找到 python，无法自动重建。请先运行 python build_lockon_copy.py。
    pause
    exit /b 1
  )
  python build_lockon_copy.py || (echo [错误] 重建失败 & pause & exit /b 1)
)

echo ============================================
echo   CF 联机服务器启动中  端口 %PORT%
echo   本机测试:  http://127.0.0.1:%PORT%/
echo   局域网/公网: http://^<本机IP或域名^>:%PORT%/
echo   关闭本窗口即停止服务器
echo ============================================
node mp_server.js
echo.
echo 服务器已退出。
pause
