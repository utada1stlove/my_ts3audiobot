# TS3AudioBot 安装与 Web 控制指南

> 适用对象：要在 Linux 服务器上运行 TeamSpeak 3 音频机器人的管理员。
>
> 本文检索日期为 **2026-09-06**。命令以 Ubuntu/Debian 的 x86_64 服务器为例；请勿以 root 身份长期运行机器人。

## 先选版本

本仓库 README 给出了两个不同的项目，不能将它们的二进制文件、配置文件或教程混用。

| 项目 | 适合情形 | 状态与建议 |
| --- | --- | --- |
| [ArthurZhu1992/TS3AudioBot](https://github.com/ArthurZhu1992/TS3AudioBot) | 需要开箱即用的 Web 控制台、多机器人和播放队列 | **推荐**。其最新发行版为 `v0.1.0`（2026-05-15），Linux ZIP 含 JAR、FFmpeg、yt-dlp、配置模板和启动脚本。 |
| [Splamy/TS3AudioBot](https://github.com/Splamy/TS3AudioBot) | 已在使用原版 TS3AudioBot，或需要原版命令/插件生态 | 其 GitHub “latest release”为 `0.12.0`（2021-04-02），README 的手动构建依赖 .NET Core 3.1。新部署不建议从它开始。 |

下面的所有具体步骤都针对推荐的 **ArthurZhu1992** 版本。

## 安装前检查

准备一台可访问 TeamSpeak 3 服务器的 Linux 主机，以及该服务器上的普通用户账号。确认系统架构：

```bash
uname -m
```

- 输出 `x86_64`：下载 `linux-x64` 包。
- 输出 `aarch64`：下载 `linux-arm64` 包。

安装 Java 运行环境、下载工具和解压工具。项目启动脚本会检测 Java；发行包自带 FFmpeg 和 yt-dlp。

```bash
sudo apt update
sudo apt install -y default-jre curl unzip
java -version
```

## 安装并首次启动

以下命令固定使用当前已核对的 `v0.1.0` x86_64 发布包。先在自己的家目录建立专用目录：

```bash
mkdir -p "$HOME/opt/ts3audiobot"
cd "$HOME/opt/ts3audiobot"
curl -fL -O https://github.com/ArthurZhu1992/TS3AudioBot/releases/download/v0.1.0/TS3AudioBot-0.1.0-linux-x64.zip
echo 'c85d4374f00a91e3bc5aeb4f6b5fe298f08bce3dc5d61d5267cdd63c5867b7c1  TS3AudioBot-0.1.0-linux-x64.zip' | sha256sum -c -
unzip TS3AudioBot-0.1.0-linux-x64.zip -d app
cd app
chmod u+x start.sh
./start.sh
```

校验命令应显示 `OK`；若不是，删除该 ZIP 并重新从 Releases 页面下载，切勿启动它。ARM64 主机只需将文件名和 URL 中的 `linux-x64` 改为 `linux-arm64`，并使用 Releases 页面给出的对应 SHA-256。

首次启动后，让进程保持运行并查看输出是否有报错。数据默认写入应用目录下的 `data/`，包括：

- `data/ts3audiobot.db`：管理员与机器人配置；应定期备份。
- `data/queues.json`：播放队列。

不要把数据库或管理员密码提交到 Git 仓库。

## 自动安装脚本

仓库提供 [install-ts3audiobot.sh](scripts/install-ts3audiobot.sh)，用于在新的 Debian/Ubuntu 主机上自动安装**固定的 `v0.1.0`**。脚本会安装 Java 21、校验官方 SHA-256、创建 `ts3audiobot` 系统账号和 systemd 服务，并将 Web 绑定至 `127.0.0.1:58913`。它不会开放防火墙端口，也会在 `/opt/ts3audiobot` 已存在时停止，避免覆盖已有数据。

在仓库目录执行：

```bash
chmod u+x scripts/install-ts3audiobot.sh
sudo ./scripts/install-ts3audiobot.sh
```

网络较慢时，可先下载官方固定版本 ZIP，在目标主机上将其作为参数传入；脚本仍会验证 SHA-256：

```bash
sudo ./scripts/install-ts3audiobot.sh --archive /path/to/TS3AudioBot-0.1.0-linux-x64.zip
```

脚本目前支持 `x86_64` 和 `aarch64`，并只接受对应 `v0.1.0` 官方资产。完成后用 SSH 隧道访问 Web 控制台，具体方法见下一节。

## 上传本地音乐到 VPS 播放

当前 `v0.1.0` 页面没有文件上传按钮，但已部署的自动安装方案会创建仅供机器人本机使用的媒体目录和服务：

- 上传目录：`/opt/ts3audiobot/media/upload`
- 本地媒体 URL：`http://127.0.0.1:18080/文件名`
- 监听范围：仅 VPS 的 `127.0.0.1`，不会暴露为公网下载站。

在自己的电脑上传一个 MP3，例如：

```bash
scp "./my-song.mp3" tx:/opt/ts3audiobot/media/upload/my-song.mp3
```

文件名建议使用英文、数字、连字符或下划线，避免 URL 转义问题。然后在 Web 控制台的“播放中心”选择目标机器人，在“添加歌曲 URL”输入：

```text
http://127.0.0.1:18080/my-song.mp3
```

点击“添加”后，选择该机器人并连接，它会播放该文件。支持的实际格式取决于内置 FFmpeg，通常可使用 MP3、M4A、AAC、OGG、WAV 与 FLAC。上传后若权限被改变，可执行：

```bash
ssh tx 'chown ts3audiobot:ts3audiobot /opt/ts3audiobot/media/upload/my-song.mp3'
```

### 按目录批量导入 WAV

仓库包含 [import-local-music-queues.py](scripts/import-local-music-queues.py)，用于直接把本地 WAV 文件写入指定机器人的既有歌单。它**不会调用 Web 入队接口、解析器或 `yt-dlp`**；轨道会直接指向 VPS 回环地址的媒体服务。

### 交互式导入菜单

日常导入推荐使用 [local-music-import-menu.sh](scripts/local-music-import-menu.sh)。它已安装在 VPS 的 `/opt/ts3audiobot/tools/`，直接执行：

```bash
ssh -F /home/aerith/.ssh/config tx '/opt/ts3audiobot/tools/local-music-import-menu.sh'
```

菜单会依次询问：目标机器人、已有歌单或新歌单、导入范围。导入范围可选择顶层文件夹、专辑/艺人子文件夹、逐首选择或全部支持的音频文件。编号支持逗号与范围，例如 `1,3-5`。

菜单还会从 `/opt/ts3audiobot/app/data/ts3audiobot.db` 读取真实机器人名单。`queues.json` 中存在但数据库里不存在的 bot key 会被识别为幽灵 bot；脚本不会把它们列为导入目标，并在最终 `IMPORT` 写入时从 `queues`、`activePlaylists`、`playlistPositions` 中删除。若数据库不可读，会跳过清理并按 `queues.json` 旧行为继续。

脚本先显示将新增和因重复跳过的数量；只有输入 `IMPORT` 才会备份 `queues.json`、短暂停止服务、原子写入本地轨道、清理幽灵 bot 并重新启动服务。默认媒体目录为 `/opt/ts3audiobot/media/upload`，支持 AAC、FLAC、M4A、MP3、OGG、OPUS 与 WAV；整个流程不经过 `yt-dlp`。

脚本当前的分类规则适用于本次音乐库：`Gundam S.E.E.D. Music/` 进入 `seed`，`No Promises to Keep` 进入 `FinalFantasy`，其余 `SQUARE ENIX MUSIC/` WAV 进入 `Nier`。先上传并预演：

```bash
scp -F /home/aerith/.ssh/config scripts/import-local-music-queues.py tx:/tmp/import-local-music-queues.py
ssh -F /home/aerith/.ssh/config tx 'python3 /tmp/import-local-music-queues.py \
  --root /opt/ts3audiobot/media/upload \
  --queue-file /opt/ts3audiobot/app/data/queues.json \
  --bot LacusClyne'
```

预演结果正确后，必须先备份并停止服务，避免运行中的程序覆盖队列文件；导入期间服务会短暂停止：

```bash
ssh -F /home/aerith/.ssh/config tx 'set -euo pipefail
queue=/opt/ts3audiobot/app/data/queues.json
systemctl stop ts3audiobot.service
cp --preserve=mode,ownership,timestamps "$queue" "$queue.before-local-import-$(date +%Y%m%dT%H%M%SZ)"
python3 /tmp/import-local-music-queues.py --root /opt/ts3audiobot/media/upload --queue-file "$queue" --bot LacusClyne --write
python3 -m json.tool "$queue" >/dev/null
chown ts3audiobot:ts3audiobot "$queue"
systemctl start ts3audiobot.service'
```

重复运行会跳过相同歌单中、相同相对路径的文件；不要在服务运行期间手动编辑 `queues.json`。

常用维护命令：

```bash
ssh tx 'systemctl status ts3audiobot-media.service'
ssh tx 'find /opt/ts3audiobot/media/upload -maxdepth 1 -type f -printf "%f %s bytes\n"'
ssh tx 'rm /opt/ts3audiobot/media/upload/old-song.mp3'
```

删除歌曲前，先确保它不在任何播放队列中；删除操作不能恢复。

## 用网页完成初始设置

在机器人服务器本机浏览器访问：

```text
http://localhost:58913
```

第一次访问会转到 `/setup`，创建管理员账号和密码。完成后登录控制台，按此顺序操作：

1. 打开“机器人管理”，新建机器人。
2. 填写 TeamSpeak 3 服务器地址、目标频道和机器人昵称。
3. 保存后启动该机器人，无须重启 Web 服务。
4. 在“播放中心”选择内容，在“队列”中调整播放顺序。

机器人能否加入频道还取决于 TeamSpeak 服务器的权限、频道密码和网络连通性；这些值由你在机器人配置中提供，不能从 Web 控制台替代 TeamSpeak 权限配置。

## 从自己的电脑安全访问 Web 控制台

`localhost` 只代表机器人服务器自身。最稳妥的初次远程访问方式是 SSH 隧道，不要先把管理端口暴露到公网：

```bash
ssh -L 58913:127.0.0.1:58913 your-user@your-server
```

保持该 SSH 会话打开，然后在自己的电脑浏览器访问 `http://localhost:58913`。这会把本机 58913 端口加密转发到服务器的 Web 控制台。

需要长期对外提供访问时，先确认应用实际监听地址和配置文件中的 `web.port`，再使用反向代理、HTTPS、强密码和访问控制。不要仅因端口是 58913 就直接在防火墙中向全网开放；该端口提供管理员控制能力。

## 常用配置与排障

已确认故障、日志判读和安全恢复流程见
[TROUBLESHOOTING_CN.md](TROUBLESHOOTING_CN.md)。特别是后台显示播放但频道
无声时，应先检查日志是否包含 `too many clones already connected`、
`noConn` 或 `opusBytes=0`，不要只查看 TOML。

发行包的配置模板支持以下常用项：

| 配置项 | 用途 |
| --- | --- |
| `web.port` | Web 控制台端口，默认 `58913`。 |
| `tools.ffmpeg_path` | FFmpeg 路径；`auto` 或 `ffmpeg` 会尝试自动解析。 |
| `resolvers.external.*` | 外部解析器命令路径。 |
| `media.cache_enabled` | 媒体缓存总开关。 |
| `media.audio_cache_enabled` | 音频落盘缓存开关。启用前应确认内容授权与当地法律、平台条款。 |
| `media.max_size_gb` | 缓存容量上限；超限时按最近最少使用清理未引用内容。 |

遇到问题时按以下顺序检查：

1. `java -version` 是否可执行；不能执行时先安装 Java。
2. 在应用目录执行 `./start.sh`，直接阅读控制台错误信息。
3. FFmpeg/yt-dlp 找不到时，确认发行包内文件未被删除；必要时把可执行文件放入 PATH，或在配置中给出绝对路径。
4. 无法打开网页时，先在服务器运行 `curl -I http://127.0.0.1:58913`，再检查 SSH 隧道而非立即开放防火墙。
5. 机器人无法进频道时，检查 TeamSpeak 地址、端口、频道路径/密码与服务器权限。
6. 后台正在播放但频道无声时，按 [TROUBLESHOOTING_CN.md](TROUBLESHOOTING_CN.md)
   检查重复客户端克隆和 `noConn`。

## 持续运行

先在前台确认一切正常，再交给你的服务管理器运行。最小的 systemd 用户服务示例如下；将 `YOUR_USER` 和路径替换成实际值：

```ini
# ~/.config/systemd/user/ts3audiobot.service
[Unit]
Description=TS3AudioBot
After=network-online.target

[Service]
WorkingDirectory=/home/YOUR_USER/opt/ts3audiobot/app
ExecStart=/home/YOUR_USER/opt/ts3audiobot/app/start.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

保存后执行：

```bash
systemctl --user daemon-reload
systemctl --user enable --now ts3audiobot.service
systemctl --user status ts3audiobot.service
journalctl --user -u ts3audiobot.service -f
```

远程主机若希望用户退出 SSH 后服务仍继续运行，管理员还需要为该账号启用 systemd linger：`sudo loginctl enable-linger YOUR_USER`。

## 版本固定与升级

本文的安装命令**固定在 `v0.1.0`**，而不是使用 `latest` 或未指定分支的下载链接：

- 下载 URL 中包含 `/v0.1.0/`。
- 文件名包含 `TS3AudioBot-0.1.0-linux-x64.zip`。
- 下载后必须匹配该版本官方 Release 公布的 SHA-256。

因此，未来再次按本文安装时，得到的仍是同一版本；已经运行的服务也不会自行升级。升级应作为一次独立操作：先阅读目标 Release 的说明，下载其明确版本号的资产，核对该资产的 SHA-256，备份 `data/ts3audiobot.db` 和 `data/queues.json`，然后在维护窗口替换程序并验证。不要把“升级”简化为重新下载 `latest`。

## 官方来源

- [本地项目 README](README.MD)：说明本项目的目标与两个候选上游仓库。
- [ArthurZhu1992 README](https://github.com/ArthurZhu1992/TS3AudioBot)：发行包内容、启动方式、首次登录、Web 控制流程、配置项和数据路径。
- [ArthurZhu1992 v0.1.0 Release](https://github.com/ArthurZhu1992/TS3AudioBot/releases/tag/v0.1.0)：平台包名、发布日期与 Linux x86_64 SHA-256。
- [Splamy README](https://github.com/Splamy/TS3AudioBot)：原版依赖、安装和手动构建说明。
- [Splamy 0.12.0 Release](https://github.com/Splamy/TS3AudioBot/releases/tag/0.12.0)：原版最后 GitHub 稳定发行版的日期与资产。
