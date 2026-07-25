# suspend-guard

在 **claude / codex 等 CLI agent 正在干活**(纯空闲不算)或**有 RDP 连接**时,阻止 Linux 桌面自动挂起;两个条件都消失并冷却一段时间后,自动恢复允许挂起。附带一个 GNOME 托盘图标用于查看状态和开关。

写这个的动机:桌面开了"无操作 1 小时自动挂起",但 RDP 挂着看东西、或者 claude code / codex 在后台跑长任务时,对系统来说都是"无操作",任务经常被挂起打断。

## 工作原理

一个用户级 systemd 服务,每 30 秒采样一次,满足任一条件就通过 `systemd-inhibit --what=sleep:idle --mode=block` 持有 logind 抑制锁:

| 条件 | 判定方式 |
| --- | --- |
| agent 忙碌 | `claude` / `codex` 进程(comm 全词匹配)及其**全部后代进程**,窗口内 CPU 累计 ≥ 2s,**或** `rchar+wchar` 读写字节增量 ≥ 200KB |
| RDP 连接 | RDP 端口(默认 3389)存在 established TCP 连接 |
| 手动常亮 | 存在 `$XDG_RUNTIME_DIR/suspend-guard.force`(托盘"常亮"开关) |

细节:

- **纯空闲不触发**:挂在提示符不动的 claude/codex 几乎没有 CPU 和流量,不会持锁。
- **IO 增量是网络活动的代理**:`/proc/<pid>/io` 的 rchar/wchar 包含 socket 收发,能抓到"低 CPU 但正在等 API 流式返回"的场景;每进程真正的纯网络计数需要 root/eBPF,这里刻意不用。
- **cutime/cstime 一并计入**,窗口内已退出的短命子进程(如编译)不会漏算。
- **冷却释放**:条件消失后需连续空闲 6 个窗口(180s)才放锁,容忍等待长响应的间隙。
- **全程无需 root**:活动图形会话下,用户服务就能拿到 logind 的 block 锁(polkit `allow_active`)。

## 依赖

- systemd(logind)、`ss`(iproute2)、`pgrep`/`ps`(procps)—— 常规发行版都有
- 托盘(可选):`python3-gi`、AppIndicator3 typelib、GNOME 需启用 AppIndicator 扩展(Ubuntu 默认的 `ubuntu-appindicators` 即可)

在 Ubuntu GNOME(systemd 259、Wayland)上开发验证;判定逻辑本身与桌面环境无关,无托盘也可只用服务。

## 安装

```bash
git clone https://github.com/lieyanc/suspend-guard.git
cd suspend-guard
./install.sh
```

落点:

| 文件 | 位置 |
| --- | --- |
| 守护脚本 | `~/.local/bin/suspend-guard` |
| systemd 用户服务 | `~/.config/systemd/user/suspend-guard.service`(enable 到 default.target) |
| 托盘 | `~/.local/bin/suspend-guard-indicator.py` |
| 托盘自启 | `~/.config/autostart/suspend-guard-indicator.desktop` |

## 托盘

- 🔒 `changes-prevent`:正在阻止挂起(菜单里能看到原因和当窗口 CPU/IO 数值)
- 🔓 `changes-allow`:空闲,允许挂起
- ⊘ `action-unavailable`:守护服务未运行

菜单提供「启用守护服务」「常亮(无条件保持唤醒)」两个开关;退出托盘不影响服务本身。

## 配置

写 `~/.config/suspend-guard.conf`(shell 语法)覆盖默认值,改完 `systemctl --user restart suspend-guard`:

| 变量 | 默认 | 含义 |
| --- | --- | --- |
| `INTERVAL` | `30` | 采样窗口(秒) |
| `BUSY_CPU_SECS` | `2` | 窗口内进程树 CPU ≥ 该秒数视为忙碌 |
| `BUSY_IO_KB` | `200` | 窗口内进程树读写增量 ≥ 该值(KB)视为忙碌 |
| `IDLE_WINDOWS_TO_RELEASE` | `6` | 连续空闲窗口数,达到才释放锁 |
| `AGENT_RE` | `claude\|codex` | 进程名 ERE,comm 全词匹配 |
| `RDP_PORTS` | `3389` | RDP 端口,空格分隔 |

## 查看状态 / 排错

```bash
systemd-inhibit --list | grep suspend-guard      # 锁是否持有及原因
journalctl --user -u suspend-guard -f            # acquire/release 日志
cat "$XDG_RUNTIME_DIR/suspend-guard.state"       # held|原因|指标(托盘数据源)
```

## 卸载

```bash
./uninstall.sh
```

## 已知局限

- agent 卡在**纯等待型**操作(近零 CPU、零流量,如 `sleep 600` 式工具调用)超过冷却时长会被视为空闲。
- 持锁期间手动挂起也会被拦;确要挂起用 `systemctl suspend -i`。
- 只管登录后的用户会话;GDM 登录界面自己的自动挂起不归它管。
- 若空闲的 agent 后台遥测频繁触发 `BUSY_IO_KB`,把该值调大即可。

## License

MIT
