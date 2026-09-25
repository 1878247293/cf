#!/usr/bin/env bash
# setup.sh — 在 Ubuntu/Debian VPS 上一键部署 CF 联机中继
# 用法:  sudo bash setup.sh
# 说明:  脚本只做安装与配置，不会改动服务器上已有的其他站点数据。
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="/opt/cf"
SERVICE_USER="cfmp"
PORT="${PORT:-8080}"
ENABLE_AUTH="${ENABLE_AUTH:-no}"     # 设为 yes 并配合 AUTH_USER/AUTH_PASS 开启口令门禁
AUTH_USER="${AUTH_USER:-player}"
AUTH_PASS="${AUTH_PASS:-}"

say() { printf '\033[1;36m[cf]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[cf:错误]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" = 0 ] || die "请用 sudo 运行本脚本"
command -v node >/dev/null 2>&1 || die "未找到 node，请先安装 Node.js 18+"

say "1/6 安装依赖: nginx"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx apache2-utils >/dev/null

say "2/6 创建运行用户 $SERVICE_USER"
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

say "3/6 部署代码到 $APP_DIR"
mkdir -p "$APP_DIR"
# 只拷贝运行必需文件，构建脚本与源文件不带上线
install -m 0644 "$SRC_DIR/mp_server.js"                "$APP_DIR/mp_server.js"
[ -f "$SRC_DIR/transport-ship-lockon.html" ] || die "缺少构建产物 transport-ship-lockon.html，请先运行: python build_lockon_copy.py"
install -m 0644 "$SRC_DIR/transport-ship-lockon.html"  "$APP_DIR/transport-ship-lockon.html"
install -m 0644 "$SRC_DIR/README.md"                   "$APP_DIR/README.md"
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"
chmod 0755 "$APP_DIR"

say "4/6 安装 systemd 服务 (端口 $PORT，仅监听回环)"
sed "s|^Environment=PORT=.*|Environment=PORT=$PORT|" \
    "$SRC_DIR/deploy/cf-mp.service" > "/etc/systemd/system/cf-mp.service"
systemctl daemon-reload
systemctl enable --now cf-mp
sleep 1
systemctl is-active --quiet cf-mp || { journalctl -u cf-mp -n 30 --no-pager; die "服务启动失败，日志见上"; }

say "5/6 配置 Nginx 反向代理 (含 WebSocket 升级)"
cp "$SRC_DIR/deploy/nginx-cf.conf" /etc/nginx/sites-available/cf-mp
ln -sf /etc/nginx/sites-available/cf-mp /etc/nginx/sites-enabled/cf-mp
rm -f /etc/nginx/sites-enabled/default

if [ "$ENABLE_AUTH" = "yes" ]; then
  if [ -z "$AUTH_PASS" ]; then
    AUTH_PASS="$(head -c 9 /dev/urandom | base64 | tr -d '/+=' | head -c 10)"
    GENERATED=1
  else
    GENERATED=0
  fi
  printf '%s:%s\n' "$AUTH_USER" "$(openssl passwd -apr1 "$AUTH_PASS")" > /etc/nginx/.cfmp_htpasswd
  chmod 0640 /etc/nginx/.cfmp_htpasswd
  chown root:www-data /etc/nginx/.cfmp_htpasswd
  # 两行必须同时解注释：只开 auth_basic 而没有 user_file，nginx -t 会报错
  sed -i -e 's|^[[:space:]]*#[[:space:]]*auth_basic |    auth_basic |' \
         -e 's|^[[:space:]]*#[[:space:]]*auth_basic_user_file |    auth_basic_user_file |' \
         /etc/nginx/sites-available/cf-mp
  grep -q '^[[:space:]]*auth_basic_user_file' /etc/nginx/sites-available/cf-mp \
    || die "门禁配置写入失败，请检查 nginx-cf.conf"
  if [ "$GENERATED" = 1 ]; then
    say "     已开启口令门禁 -> 用户名: $AUTH_USER  密码: $AUTH_PASS"
  fi
fi

# 配置校验失败要撤销站点启用，否则 Nginx 整体起不来、连已有站点一起挂
if ! nginx -t; then
  rm -f /etc/nginx/sites-enabled/cf-mp
  die "Nginx 配置校验失败，已撤销本次站点启用，现有站点不受影响"
fi
systemctl enable --now nginx
systemctl reload nginx

say "6/6 自检"
HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/transport-ship-lockon.html?mp=1" || echo 000)"
[ "$HTTP_CODE" = "200" ] || die "本地自检失败，HTTP $HTTP_CODE"
# WebSocket 握手自检
WS_OK="$(curl -s -o /dev/null -w '%{http_code}' \
  -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
  -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
  "http://127.0.0.1:$PORT/" || echo 000)"
[ "$WS_OK" = "101" ] || die "WebSocket 握手自检失败，HTTP $WS_OK"

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
cat <<EOF

$(printf '\033[1;32m')部署完成$(printf '\033[0m')

  游戏地址:  http://${IP:-你的服务器IP}/
  服务管理:  systemctl status|restart|stop cf-mp
  实时日志:  journalctl -u cf-mp -f
  下线:      sudo bash $(dirname "$SRC_DIR")/deploy/teardown.sh

  别忘了在云厂商安全组放行 TCP 80（如需 HTTPS 还要 443）。
  联机中继本身无鉴权，建议开启上面的口令门禁，或用完即关。
EOF
