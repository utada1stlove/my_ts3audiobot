# TS3AudioBot 故障排查

本文记录已经遇到的典型故障、判断依据和安全恢复流程。命令中的
`datawave_hk` 是 SSH 别名示例，可按实际配置替换。

## 后台正在播放，但频道里没有声音

### 症状

- Web 控制台显示机器人已启动，播放队列也在推进。
- 日志中的音频统计持续增长，例如 `frames`、`pcmBytes`、`opusBytes`。
- TeamSpeak 频道里听不到声音。
- 同一时间可能出现 `too many clones already connected` 和
  `ping timeout, triggering disconnect`。
- 音频统计同时显示 `noConn` 非零，连接恢复前通常还会有
  `opusBytes=0` 或大量 `dropped`。

音频帧增长只说明 FFmpeg 或编码器仍在产出数据，不代表这些数据已经送到
TeamSpeak。`noConn` 表示机器人没有可用连接，音频会在发送前被丢弃。

### 配置边界

不要只看 `ts3Audio-config.toml`：

- `/opt/ts3audiobot/app/ts3Audio-config.toml` 保存 Web、工具路径、
  解析器和缓存等应用配置。
- `/opt/ts3audiobot/app/data/ts3audiobot.db` 保存管理员和机器人配置，
  包括 TeamSpeak 地址、身份和频道。
- `/opt/ts3audiobot/app/data/queues.json` 保存播放列表和队列。

因此，TOML 中没有频道字段是正常的。频道应通过 Web 机器人配置查看或
修改，不要为了“让 TOML 出现频道”而手写未知配置项。

### 已确认的根因

修改机器人频道后，旧 TeamSpeak 客户端仍以原身份在线，新客户端又使用
同一 UID 连接，服务器会把它识别为额外克隆。达到服务器的克隆上限后，
新连接会收到：

```text
[TS3] error ... too many clones already connected
```

连接随后超时，音频统计快速进入 `noConn`。日志中新增的
`connected with client id ...` 和 `login complete` 只应在新连接真正成功
后出现。如果只有连接尝试，没有这两条记录，不能把服务状态 `active`
当作机器人已经在线。

### 安全恢复

先完整停止服务，让 TeamSpeak 服务器回收旧身份，再启动：

```bash
ssh datawave_hk 'systemctl stop ts3audiobot.service'
ssh datawave_hk "pgrep -af '[j]ava.*[Tt][Ss]3[Aa]udio[Bb]ot' || true"
sleep 20
ssh datawave_hk 'systemctl start ts3audiobot.service'
```

不要只反复重启 Web 控制台或立即连续重启 systemd 服务。旧连接尚未被
服务器清除时，很快重启会再次触发相同的克隆冲突。

如果 20 秒后仍然出现 `too many clones already connected`：

1. 检查 VPS 上是否还存在第二个 TS3AudioBot Java 进程。
2. 在 TeamSpeak 客户端中确认同一身份没有残留在线客户端。
3. 再等待一段时间，或在服务器端踢掉该身份的残留连接后重新启动。
4. 确认只有一个 `ts3audiobot.service` 在管理该机器人。

### 验收标准

启动后观察日志：

```bash
ssh datawave_hk 'journalctl -u ts3audiobot.service -n 120 --no-pager'
```

健康状态应同时满足：

- 出现 `connected with client id ...`。
- 出现 `login complete`。
- 没有新的 `too many clones already connected`。
- `[Audio] stats` 中的 `opusBytes` 大于 0。
- `dropped=0`、`noConn=0`、`encodeFail=0`。

重启后的连接验证通过，只代表协议层和编码输出正常。最终仍要在
TeamSpeak 中确认机器人所在频道、机器人音量、频道权限和你的客户端播放
设备没有静音。

### 后续修改频道的规则

1. 先在 Web 控制台停止或断开该机器人。
2. 确认 TeamSpeak 中旧客户端已经消失。
3. 再修改频道并启动机器人。
4. 如果面板操作后仍发生克隆冲突，使用本文的 systemd 停止、等待、启动
   流程，而不是连续点击重连。

## “幽灵 Bot”和“重复连接克隆”不是同一个问题

仓库现有文档中的“幽灵 Bot”指 `queues.json` 中仍残留、但
`ts3audiobot.db` 已不存在的旧 bot key。它属于队列数据清理问题，可能让
导入菜单看到无效目标或遗留队列。本地导入脚本会在确认导入后删除这些
残留 key。

本文记录的无声故障属于 TeamSpeak 重复客户端克隆：数据库中的机器人仍然
有效，问题是同一身份同时存在多个连接。恢复它不需要删除机器人，也不应
清理 `queues.json`。

两种问题的判断方法：

| 现象 | 队列幽灵 Bot | 重复连接克隆 |
| --- | --- | --- |
| 数据库中没有对应机器人 | 是 | 否 |
| 日志出现 `too many clones` | 通常没有 | 是 |
| 音频出现 `noConn` 且无声 | 不是直接原因 | 是常见结果 |
| 恢复方式 | 清理无效队列 key | 停止、等待旧连接失效、再启动 |

之前若看到旧机器人名称残留在面板或队列中，不能仅凭“像幽灵”就判定为
同一问题。应以数据库、`queues.json` 和 TeamSpeak 实时日志分别确认。
