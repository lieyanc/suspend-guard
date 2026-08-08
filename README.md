# suspend-guard

在 **claude / codex / opencode 等 CLI agent 正在干活**(纯空闲不算)或**有 RDP 连接**时,阻止 Linux 桌面自动挂起;条件消失并冷却一段时间后,自动恢复允许挂起。附带一个 GNOME 托盘图标用于查看状态和开关。

写这个的动机:桌面开了"无操作自动挂起",但 RDP 挂着看东西、或者 claude code / codex / opencode 在后台跑长任务时,对系统来说都是"无操作",任务经常被挂起打断。

## 工作原理

一个用户级 systemd 服务,每 15 秒采样一次,满足任一条件就通过 `systemd-inhibit --what=sleep:idle --mode=block` 持有 logind 抑制锁:

| 条件 | 判定方式 |
| --- | --- |
| agent 忙碌(主信号) | 任一 `claude` / `codex` / `opencode` 根进程(comm 全词匹配)及其**全部后代**名下的 established TCP 连接,窗口内 `bytes_sent+bytes_received` 增量合计 ≥ 5KB(`ss -ti` 每连接统计) |
| agent 忙碌(兜底) | 任一独立进程树窗口内 CPU 累计 ≥ 4s,覆盖编译/测试等没有网络的纯本地重活 |
| RDP 连接 | RDP 端口(默认 3389)存在 established TCP 连接 |
| 手动常亮 | 存在 `$XDG_RUNTIME_DIR/suspend-guard.force`(托盘"常亮"开关) |

细节:

- **以真实网络流量为主**:agent 干活的本质是和 API 有来往流量。按连接统计真实字节(tcp_info),不用 rchar/wchar 这类含 tty 重绘、磁盘读写的粗代理——后者噪声大到空闲 agent 也会被误判忙碌,导致锁一直不放。
- **纯空闲不触发**:挂在提示符的 agent 即使有少量 TUI 后台 CPU,只要单棵进程树未达到阈值就不会触发。
- **会话间不累加**:每个 agent 根进程树独立比较阈值,避免同时挂着多个空闲 TUI 时,后台 CPU 或心跳流量合计后误判忙碌。
- **回环流量也计入**:API 走本地代理(clash/mitmproxy 等)时流量对端是 127.0.0.1,照样统计。
- **cutime/cstime 计入 CPU**,窗口内已退出的短命子进程(如编译器)不漏算。
- **冷却释放**:条件消失后需连续空闲 12 个窗口(180s)才放锁,容忍请求间隙和长思考静默。
- **全程无需 root**:活动图形会话下,用户服务就能拿到 logind 的 block 锁(polkit `allow_active`);`ss -tip` 看本用户进程的连接也不需要特权。

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

- 🔒 `changes-prevent`:正在阻止挂起(菜单里能看到原因和当窗口单进程树 net/CPU 峰值)
- 🔓 `changes-allow`:空闲,允许挂起
- ⊘ `action-unavailable`:守护服务未运行

菜单提供「启用守护服务」「常亮(无条件保持唤醒)」两个开关;退出托盘不影响服务本身。

## 配置

写 `~/.config/suspend-guard.conf`(shell 语法)覆盖默认值,改完 `systemctl --user restart suspend-guard`:

| 变量 | 默认 | 含义 |
| --- | --- | --- |
| `INTERVAL` | `15` | 采样窗口(秒) |
| `BUSY_NET_KB` | `5` | 任一独立进程树窗口内网络收发 ≥ 该值(KB)视为忙碌(主信号) |
| `BUSY_CPU_SECS` | `4` | 任一独立进程树窗口内 CPU ≥ 该秒数视为忙碌(兜底信号) |
| `IDLE_WINDOWS_TO_RELEASE` | `12` | 连续空闲窗口数,达到才释放锁(12×15s=180s) |
| `AGENT_RE` | `claude\|codex\|opencode` | 进程名 ERE,comm 全词匹配 |
| `RDP_PORTS` | `3389` | RDP 端口,空格分隔 |

## 查看状态 / 排错

```bash
systemd-inhibit --list | grep suspend-guard      # 锁是否持有及原因
journalctl --user -u suspend-guard -f            # acquire/release 日志(含当窗口指标)
cat "$XDG_RUNTIME_DIR/suspend-guard.state"       # held|原因|指标(托盘数据源)
```

## 卸载

```bash
./uninstall.sh
```

## 已知局限

- 网络按 **连接快照的增量** 统计:窗口内建立又关闭的短命连接不计入。agent 对 API 用的是长连接,不受影响;极端情况下密集短连接的流量会被低估,可靠 CPU 兜底补偿。
- agent 处于**纯静默等待**(零流量、近零 CPU,比如 `sleep 600` 式工具调用,或模型长思考期间心跳恰好极小)超过冷却时长会被视为空闲;桌面端通常还有几十分钟的"无操作"阈值兜着,实际很难恰好撞上。
- 持锁期间手动挂起也会被拦;确要挂起用 `systemctl suspend -i`。
- 只管登录后的用户会话;GDM 登录界面自己的自动挂起不归它管。

## License

MIT
