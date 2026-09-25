#!/usr/bin/env bash
# teardown.sh — 卸载并清理 CF 联机中继（服务下线用）
# 用法:  sudo bash teardown.sh
#
# ⚠️ 本脚本会停止服务、删除 /opt/cf 与 Nginx 站点配置。
#    不会删除系统自带的其他站点数据。执行前请确认。
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "请用 sudo 运行"; exit 1; }

echo "即将停止 cf-mp 服务并删除 /opt/cf 与 Nginx 站点配置。"
read -r -p "确认请输入 yes: " CONFIRM
[ "$CONFIRM" = "yes" ] || { echo "已取消，未做任何改动。"; exit 0; }

systemctl stop cf-mp 2>/dev/null || true
systemctl disable cf-mp 2>/dev/null || true
rm -f /etc/systemd/system/cf-mp.service
systemctl daemon-reload

rm -f /etc/nginx/sites-enabled/cf-mp /etc/nginx/sites-available/cf-mp /etc/nginx/.cfmp_htpasswd
systemctl reload nginx 2>/dev/null || true

rm -rf /opt/cf
id -u cfmp >/dev/null 2>&1 && userdel cfmp 2>/dev/null || true

echo "已下线并清理完毕。"
