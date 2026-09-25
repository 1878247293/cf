#!/usr/bin/env bash
# 一键启动联机服务器（Linux 远程服务器版；服务器权威记账 + world 聚合下发）
# 用法:  ./start_server.sh            前台运行（关终端即停）
#        ./start_server.sh -d         后台常驻（nohup，日志写 server.log）
#        PORT=80 ./start_server.sh    指定端口（默认 8080；80/443 需 root 或 setcap）
#        ./start_server.sh stop       停止后台进程
set -euo pipefail

# 切到脚本所在目录（无论从哪里调用）
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PORT="${PORT:-8080}"
PIDFILE=".mp_server.pid"
LOGFILE="server.log"

# stop 子命令：停掉后台进程
if [ "${1:-}" = "stop" ]; then
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    kill "$(cat "$PIDFILE")" && rm -f "$PIDFILE"
    echo "已停止后台服务器。"
  else
    echo "没有正在运行的后台服务器（或 $PIDFILE 已失效）。"
    rm -f "$PIDFILE" 2>/dev/null || true
  fi
  exit 0
fi

# 检查 node
if ! command -v node >/dev/null 2>&1; then
  echo "[错误] 未找到 node，请先安装 Node.js。"
  echo "        Debian/Ubuntu: sudo apt install -y nodejs"
  echo "        CentOS/RHEL:   sudo yum install -y nodejs"
  exit 1
fi

# 检查已编译的游戏页；缺失则尝试用 build_lockon_copy.py 重建
if [ ! -f "transport-ship-lockon.html" ]; then
  echo "[提示] 未找到 transport-ship-lockon.html，尝试用 build_lockon_copy.py 重建..."
  if command -v python3 >/dev/null 2>&1; then
    python3 build_lockon_copy.py
  elif command -v python >/dev/null 2>&1; then
    python build_lockon_copy.py
  else
    echo "[错误] 未找到 python，无法自动重建。请先在本地 build 后上传该 HTML。"
    exit 1
  fi
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "============================================"
echo "  CF 联机服务器  端口 ${PORT}"
echo "  本机测试:   http://127.0.0.1:${PORT}/"
[ -n "${IP:-}" ] && echo "  局域网/公网: http://${IP}:${PORT}/"
echo "  （公网访问需在云控制台/防火墙放行该端口）"
echo "============================================"

# 后台常驻模式
if [ "${1:-}" = "-d" ] || [ "${1:-}" = "--daemon" ]; then
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "[提示] 已有后台进程在运行（PID $(cat "$PIDFILE")）。先 ./start_server.sh stop 再启。"
    exit 1
  fi
  PORT="$PORT" nohup node mp_server.js >"$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  echo "后台启动完成，PID $(cat "$PIDFILE")，日志: $LOGFILE"
  echo "停止: ./start_server.sh stop"
  exit 0
fi

# 前台模式
exec env PORT="$PORT" node mp_server.js
