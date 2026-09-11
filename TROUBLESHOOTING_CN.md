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

## 进度条到头了，声音却还在继续

### 症状

- 播放队列里加入的是 YouTube Music 歌单链接
  （`https://music.youtube.com/playlist?list=...`）。
- Web 面板的进度条走到这首歌的末尾后不再前进，歌名也一直停留在第一首。
- 频道里的声音没有停，听起来像 YouTube 的“自动播放”接着放了下一首。
- 日志被这类内容刷屏：

```text
Application provided invalid, non monotonically increasing dts to muxer in stream 0
[in#0/matroska,webm @ ...] Unknown element 18538067 at pos. ... considered as invalid data
```

同时 `[Audio] stats` 里 `dropped=0 noConn=0 encodeFail=0`，说明音频链路本身是
健康的，这不属于上一节的“无声故障”。

### 已确认的根因

不是 YouTube 网页的自动播放，是我们自己把整张歌单灌进了同一条管道。

播放器的取流命令形如：

```text
yt-dlp -q --no-warnings --no-playlist -f bestaudio -o - <sourceId>
```

`--no-playlist` 只对“同时带视频和歌单”的 watch 链接生效。当 `sourceId` 本身就
是 `.../playlist?list=...` 时，这个参数不起作用，yt-dlp 会把歌单里每一首歌依次
下载并**串行写入同一个 stdout**。可以直接验证：

```bash
/opt/ts3audiobot/app/yt-dlp -q --no-playlist -f bestaudio --simulate -v <playlist-url> \
  | grep -c 'Downloading 1 format'
```

歌单有 9 首就会输出 9。

FFmpeg 只在管道开头读到一次容器头，因此日志里的 `Duration: 00:06:53.28` 永远
是第一首的长度；后续歌曲的字节流继续涌入，触发 `non monotonically increasing dts`
和 `Unknown element ... invalid data`。进度条按第一首的 413 秒计数，走完就停住，
而声音来自管道里剩下的八首，于是就形同“自动播放”。

伴生现象：

- `queues.json` 中该条目的 `title`、`durationMs`、`coverUrl` 全为空，因为加入歌单
  链接时没有可对应的单曲元数据。
- 队列的 `playlistPosition` 不会推进，播放器没有单曲结束事件可依。
- 面板上的 seek 会对整条拼接流生效，一次拖拽可能直接跳进第 2、3 首歌中间。

### 恢复办法

把队列内容换成单曲链接，即 `https://music.youtube.com/watch?v=<videoId>`，每首歌
一条。展开方法：

```bash
/opt/ts3audiobot/app/yt-dlp --no-warnings --flat-playlist -J <playlist-url>
```

取 `entries[].id` 逐个拼成 watch 链接。改完必须重启服务，队列只在启动时读取一次：

```bash
ssh datawave_hk systemctl stop ts3audiobot.service
ssh datawave_hk "cp -a /opt/ts3audiobot/app/data/queues.json /opt/ts3audiobot/app/data/queues.json.bak-$(date +%Y%m%d-%H%M%S)"
# 编辑 queues.json
ssh datawave_hk systemctl start ts3audiobot.service
```

`ts3audiobot-media.service` 只是本地上传目录的静态 HTTP 服务，改队列不需要重启它。

### 手改 queues.json 的硬规则

`QueueService` 的快照加载对字段是严格模式，一条脏数据会毁掉整个队列：

- `QueueItem` 只认 6 个字段：`botId`、`addedAt`、`addedBy`、`id`、`playlistId`、
  `track`。多出任何键都会抛 `UnrecognizedPropertyException`，例如自行加一个
  `order` 用于排序。
- 加载失败后应用不会退出，而是**以空队列启动并把文件覆写成**
  `{"queues":{},"activePlaylists":{"<bot>":"default"},"playlistPositions":{}}`，
  原队列内容就此丢失，且只留下一条 WARN。日志关键字：
  `Failed to load queue snapshot from data/queues.json`。
- 因此改文件前先 `cp -a` 备份，改完启动后立刻回读文件确认条目还在。
- 写入前先停服务。应用在关闭时会回写快照，边跑边改会被覆盖。
- `title`、`durationMs`、`coverUrl` 由解析器在播放时填，持久化时会被写回空值，
  这是正常行为，不是数据丢失。
- 队列的 bot key 必须与 `ts3audiobot.db` 的 `bots.name` 一致，否则就是上一节的
  队列幽灵 key。

### 验收标准

```bash
ssh datawave_hk 'journalctl -u ts3audiobot.service --since -15m --no-pager --output cat | grep -E "Audio. play track=|Input. started pid|Duration: |non monotonically"'
```

- `[Input] started` 的命令末尾是 `/watch?v=`，不是 `/playlist?list=`。
- 一首歌唱完时出现新的 `[Audio] play track=` 且歌名发生变化。
- `playlistPosition` 随切歌递增。
- 不再出现 `non monotonically increasing dts`。

### 待上游修复

当前只能靠“不要往队列里放歌单链接”规避，代码侧还需要两件事：

1. 入队时识别歌单链接，展开成单曲条目后再写队列。
2. 取流时只允许单曲标识，必要时给 yt-dlp 加 `--playlist-items 1`，杜绝一条管道
   承载多首歌。
