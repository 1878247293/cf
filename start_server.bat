@echo off
REM 启动 CF 网页小游戏联机中继服务器
REM 用法：双击本文件，或在命令行 set PORT=80 后运行
REM 默认端口 8080；玩家打开 http://<本机IP或域名>:端口/ 即可加入
cd /d "%~dp0"
if "%PORT%"=="" set PORT=8080
echo 启动联机服务器，端口 %PORT% ...
echo 玩家访问：http://本机IP:%PORT%/
node mp_server.js
pause
