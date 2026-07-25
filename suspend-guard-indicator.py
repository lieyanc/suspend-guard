#!/usr/bin/env python3
# suspend-guard 托盘指示器:显示当前是否在阻止挂起,可开关守护服务与"常亮"。
# 图标:🔒 changes-prevent = 正在阻止挂起;🔓 changes-allow = 空闲允许挂起;⊘ = 守护未运行。
import fcntl
import os
import signal
import subprocess
import sys

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AppIndicator3

RUNDIR = os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')
STATE_FILE = os.path.join(RUNDIR, 'suspend-guard.state')
FORCE_FILE = os.path.join(RUNDIR, 'suspend-guard.force')
LOCK_FILE = os.path.join(RUNDIR, 'suspend-guard-indicator.lock')

ICON_HELD = 'changes-prevent-symbolic'
ICON_IDLE = 'changes-allow-symbolic'
ICON_OFF = 'action-unavailable-symbolic'


def sctl(*args):
    return subprocess.run(['systemctl', '--user', *args],
                          capture_output=True, text=True)


class Indicator:
    def __init__(self):
        self.ind = AppIndicator3.Indicator.new(
            'suspend-guard', ICON_OFF,
            AppIndicator3.IndicatorCategory.SYSTEM_SERVICES)
        self.ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.ind.set_title('Suspend Guard')
        self.updating = False

        menu = Gtk.Menu()
        self.status_item = Gtk.MenuItem(label='…')
        self.status_item.set_sensitive(False)
        menu.append(self.status_item)
        menu.append(Gtk.SeparatorMenuItem())
        self.enable_item = Gtk.CheckMenuItem(label='启用守护服务')
        self.enable_item.connect('toggled', self.on_enable)
        menu.append(self.enable_item)
        self.force_item = Gtk.CheckMenuItem(label='常亮(无条件保持唤醒)')
        self.force_item.connect('toggled', self.on_force)
        menu.append(self.force_item)
        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label='退出托盘图标(不影响守护服务)')
        quit_item.connect('activate', Gtk.main_quit)
        menu.append(quit_item)
        menu.show_all()
        self.ind.set_menu(menu)

        self.refresh()
        GLib.timeout_add_seconds(3, self.refresh)

    def on_enable(self, item):
        if self.updating:
            return
        if item.get_active():
            sctl('start', 'suspend-guard')
        else:
            sctl('stop', 'suspend-guard')
        GLib.timeout_add(500, self.refresh_once)

    def on_force(self, item):
        if self.updating:
            return
        if item.get_active():
            open(FORCE_FILE, 'w').close()
            sctl('start', 'suspend-guard')  # 常亮依赖守护服务在跑
        else:
            try:
                os.unlink(FORCE_FILE)
            except FileNotFoundError:
                pass
        GLib.timeout_add(500, self.refresh_once)

    def refresh_once(self):
        self.refresh()
        return False

    def refresh(self):
        active = sctl('is-active', 'suspend-guard').stdout.strip() == 'active'
        state, reason, metrics = 'off', '', ''
        if active:
            try:
                with open(STATE_FILE) as f:
                    parts = f.read().strip().split('|')
                state = parts[0] if parts and parts[0] else 'idle'
                reason = parts[1] if len(parts) > 1 else ''
                metrics = parts[2] if len(parts) > 2 else ''
            except FileNotFoundError:
                state, reason = 'idle', '等待首个采样窗口'
        self.updating = True
        self.enable_item.set_active(active)
        self.force_item.set_active(os.path.exists(FORCE_FILE))
        self.updating = False
        if not active:
            self.ind.set_icon_full(ICON_OFF, 'suspend guard off')
            self.status_item.set_label('守护未运行,不会阻止挂起')
        elif state == 'held':
            self.ind.set_icon_full(ICON_HELD, 'blocking suspend')
            self.status_item.set_label(f'正在阻止挂起:{reason}  {metrics}')
        else:
            self.ind.set_icon_full(ICON_IDLE, 'suspend allowed')
            self.status_item.set_label(f'空闲,允许挂起  {reason} {metrics}'.rstrip())
        return True


def main():
    lock = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)  # 已有实例在跑
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = Indicator()
    Gtk.main()
    del app, lock


if __name__ == '__main__':
    main()
