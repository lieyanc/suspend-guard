#!/usr/bin/env bash
# 安装 suspend-guard:守护脚本 + systemd 用户服务 + 托盘指示器(含登录自启)。
set -euo pipefail
cd "$(dirname "$0")"

install -Dm755 suspend-guard "$HOME/.local/bin/suspend-guard"
install -Dm755 suspend-guard-indicator.py "$HOME/.local/bin/suspend-guard-indicator.py"
install -Dm644 suspend-guard.service "$HOME/.config/systemd/user/suspend-guard.service"

mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/suspend-guard-indicator.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Suspend Guard Indicator
Comment=托盘显示/管理 suspend-guard(阻止挂起守护)
Exec=/usr/bin/python3 $HOME/.local/bin/suspend-guard-indicator.py
X-GNOME-Autostart-enabled=true
EOF

systemctl --user daemon-reload
systemctl --user enable suspend-guard.service
systemctl --user restart suspend-guard.service

# 有图形环境且托盘未在跑时,立即启动一份
if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] && ! pgrep -f suspend-guard-indicator.py >/dev/null; then
  setsid -f /usr/bin/python3 "$HOME/.local/bin/suspend-guard-indicator.py" >/dev/null 2>&1 || true
fi

echo "安装完成。查看状态:systemctl --user status suspend-guard"
echo "查看抑制锁:systemd-inhibit --list | grep suspend-guard"
