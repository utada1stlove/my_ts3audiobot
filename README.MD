# TS3AudioBot 部署与本地音乐管理

这是一个面向个人 TeamSpeak 3 服务器的部署与运维仓库。它固定使用 [ArthurZhu1992/TS3AudioBot](https://github.com/ArthurZhu1992/TS3AudioBot) `v0.1.0`，提供自动安装、Web 控制说明，以及不经过 `yt-dlp` 的本地音乐批量导入工具。

详细安装、升级和排障步骤见 [INSTALL_GUIDE_CN.md](INSTALL_GUIDE_CN.md)。本文是日常使用的入口。

## 当前能力

- 固定上游版本：`v0.1.0`，不使用 `latest` 下载链接。
- systemd 托管的 TS3AudioBot 服务与本地媒体服务。
- Web 控制台可管理机器人、播放列表、播放模式和队列。
- 上传的本地音乐由仅监听 VPS 回环地址的媒体服务提供。
- 交互式终端菜单可按机器人、歌单、文件夹或单曲批量导入音乐。
- 本地导入直接生成 `sourceType: local` 的队列记录，不调用 Web 入队接口、解析器或 `yt-dlp`。

## 项目选择

本仓库只针对 ArthurZhu1992 的 Java 版本，不兼容以下原版项目的二进制、配置或插件：

- [ArthurZhu1992/TS3AudioBot](https://github.com/ArthurZhu1992/TS3AudioBot)：本项目采用的上游，含 Web 控制台、多机器人与队列。
- [Splamy/TS3AudioBot](https://github.com/Splamy/TS3AudioBot)：另一套 .NET 项目，不能与本项目混用。

## 快速开始

在新的 Debian/Ubuntu VPS 上克隆本仓库后执行自动安装脚本：

```bash
git clone git@github.com:utada1stlove/my_ts3audiobot.git
cd my_ts3audiobot
sudo ./scripts/install-ts3audiobot.sh
```

脚本会安装 Java 21、校验固定版本发布包、创建 `ts3audiobot` 系统账号，并安装两个 systemd 服务：

```bash
systemctl status ts3audiobot.service
systemctl status ts3audiobot-media.service
```

应用数据位于 `/opt/ts3audiobot/app/data/`：

- `ts3audiobot.db`：管理员账号与机器人配置。
- `queues.json`：播放列表和队列。

这两个文件包含运行数据，不应提交到 Git。

## Web 控制台

默认自动安装配置将 Web 服务绑定为 `127.0.0.1:58913`，适合通过 SSH 隧道访问：

```bash
ssh -L 58913:127.0.0.1:58913 your-user@your-server
```

然后在浏览器访问 `http://localhost:58913`。首次使用会进入 `/setup` 创建管理员账号；之后在“机器人管理”创建机器人，在“播放中心”管理歌单和播放。

当前已部署的 VPS 已按管理员要求改为公网监听，因此可直接访问：

```text
http://106.55.94.249:58913
```

公网 `IP:端口` 访问是明文 HTTP。它会暴露登录请求和会话流量，必须使用强且唯一的管理员密码，并只在确认腾讯云安全组规则符合预期时使用。媒体端口 `18080` 保持 `127.0.0.1` 监听，不能从公网直接下载音乐文件。

## 上传本地音乐

VPS 音乐目录为：

```text
/opt/ts3audiobot/media/upload
```

从本机上传时，使用可恢复的 `rsync`：

```bash
rsync -a --partial --info=progress2 \
  -e 'ssh -F /home/aerith/.ssh/config' \
  '/path/to/music-folder/' \
  tx:/opt/ts3audiobot/media/upload/
```

上传完成后可核对文件数：

```bash
ssh -F /home/aerith/.ssh/config tx \
  'find /opt/ts3audiobot/media/upload -type f | wc -l'
```

不要在确认 VPS 文件完整前删除本地音乐。

## 交互式本地导入

已安装的菜单工具位于 VPS：

```bash
ssh -F /home/aerith/.ssh/config tx \
  '/opt/ts3audiobot/tools/local-music-import-menu.sh'
```

它依次提供以下选择：

1. 目标机器人。
2. 既有歌单，或新建歌单。
3. 顶层文件夹、专辑/艺人子文件夹、逐首选择，或全部支持的音频。

编号支持逗号和范围，例如 `1,3-5`。菜单会先显示选择数量、新增数量和已存在跳过数量；只有输入 `IMPORT` 才会执行实际导入。

实际导入会自动执行以下安全步骤：备份 `queues.json`、短暂停止 `ts3audiobot.service`、原子写入队列、保留原有文件所有权并重新启动服务。相同歌单中已存在的相对路径会跳过，因此可以安全地重复运行以导入新文件。

支持的格式：AAC、FLAC、M4A、MP3、OGG、OPUS、WAV。

### 当前音乐库

2026-09-07 已导入到 `LacusClyne` 的本地曲目：

| 歌单 | 曲目数 | 来源 |
| --- | ---: | --- |
| `seed` | 26 | `Gundam S.E.E.D. Music/` |
| `FinalFantasy` | 1 | `No Promises to Keep` |
| `Nier` | 156 | `SQUARE ENIX MUSIC/` 的 NieR 音乐 |

总计 183 首 WAV。上传目录中的歌词 `.lrc` 和说明 `.txt` 文件不会作为歌曲导入。

## 常用维护命令

```bash
ssh -F /home/aerith/.ssh/config tx 'systemctl status ts3audiobot.service'
ssh -F /home/aerith/.ssh/config tx 'systemctl status ts3audiobot-media.service'
ssh -F /home/aerith/.ssh/config tx 'journalctl -u ts3audiobot.service -n 100 --no-pager'
ssh -F /home/aerith/.ssh/config tx 'find /opt/ts3audiobot/media/upload -type f | wc -l'
```

队列导入前会自动产生类似以下名称的备份：

```text
/opt/ts3audiobot/app/data/queues.json.before-menu-import-YYYYMMDDTHHMMSSZ
```

恢复前先停止服务，再将对应备份复制回 `queues.json`，恢复文件所有权并启动服务。不要在服务运行期间手动编辑队列文件。

## 仓库结构

```text
scripts/install-ts3audiobot.sh         固定版本自动安装脚本
scripts/import-local-music-queues.py   按预设目录批量导入脚本
scripts/local-music-import-menu.sh     交互式导入菜单启动器
scripts/local-music-import-menu.py     交互式导入菜单实现
INSTALL_GUIDE_CN.md                    完整安装、配置与排障指南
planning/                              部署与功能实施记录
```

## 版本与备份

安装脚本固定使用 `v0.1.0` 和对应 SHA-256，不会自动升级。升级前必须备份 `ts3audiobot.db`、`queues.json` 与 systemd 单元文件，阅读目标版本的发布说明后再单独执行升级。

本仓库不保存管理员密码、数据库、队列快照、上传音乐或 VPS 私钥。
