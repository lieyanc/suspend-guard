#!/usr/bin/env bash
# 卸载 suspend-guard:停服务、杀托盘、删除已安装文件与运行时状态。
set -uo pipefail

systemctl --user disable --now suspend-guard.service 2>/dev/null
systemctl --user daemon-reload
pkill -f suspend-guard-indicator.py 2>/dev/null

rm -f "$HOME/.local/bin/suspend-guard" \
      "$HOME/.local/bin/suspend-guard-indicator.py" \
      "$HOME/.config/systemd/user/suspend-guard.service" \
      "$HOME/.config/autostart/suspend-guard-indicator.desktop" \
      "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/suspend-guard.state" \
      "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/suspend-guard.force" \
      "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/suspend-guard-indicator.lock"

echo "已卸载(配置文件 ~/.config/suspend-guard.conf 如存在未删除)"
