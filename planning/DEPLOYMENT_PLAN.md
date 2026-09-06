# TS3AudioBot 部署计划

- 状态：已完成安装，等待 Web 初始管理员与 TeamSpeak 机器人信息
- 目标：在用户指定的 `ssh tx` Linux 主机上安装 ArthurZhu1992/TS3AudioBot，验证本机 Web 控制台可用，并在用户提供 TeamSpeak 3 连接信息后创建机器人。
- 已授权范围：安装与运行 TS3AudioBot；未暴露管理端口到公网、未修改防火墙规则、未创建 TeamSpeak 管理员权限。
- 来源：`INSTALL_GUIDE_CN.md`，检索日期 2026-09-06。
- 验收：发行包 SHA-256 匹配；服务运行；服务器本机的 Web 控制台在 58913 端口响应；Web 初始管理员和 TeamSpeak 机器人由用户或用户提供的信息完成配置。

## 完成记录

1. 已确认目标为腾讯云 Debian 13 x86_64 VPS，经 `ssh tx` 以 root 管理；根文件系统可用空间约 37 GB。
2. 由于原 Nanjing University APT 镜像下载 OpenJDK 过慢，已备份 `/etc/apt/sources.list` 为 `/etc/apt/sources.list.bak-20260906`，并切换 Debian 与安全更新源至腾讯云镜像；`apt-get update` 后安装 OpenJDK 21 headless 与 `unzip`。
3. 通过 GitHub Release API 下载并核验 `TS3AudioBot-0.1.0-linux-x64.zip`：大小 `190549150` 字节，SHA-256 为 `c85d4374f00a91e3bc5aeb4f6b5fe298f08bce3dc5d61d5267cdd63c5867b7c1`。上传后在 VPS 再次核验相同哈希。
4. 已创建不可登录的系统账号 `ts3audiobot`，应用安装到 `/opt/ts3audiobot/app`，系统服务定义为 `/etc/systemd/system/ts3audiobot.service`。
5. 已生成随机 `search.auth_secret`（未记录明文），将 `web.hosts` 限为本机 Host，并将 `media.audio_cache_enabled` 设为 `false`。
6. systemd 使用 `TS3AB_WEB_ADDRESS=127.0.0.1`，因此 Web 控制台未对公网监听。最终检查：服务 `enabled`、`active`；`127.0.0.1:58913` 监听；`GET /setup` 返回 HTTP 200。
7. 已删除本地与 VPS 的临时发行 ZIP 文件；未生成编译中间文件。
8. 当前部署固定为 `v0.1.0`：发行资产 URL、文件名和 SHA-256 都为该版本；服务启动 `/opt/ts3audiobot/app/TS3AudioBot-0.1.0.jar`，不自动升级。

## 后续操作

1. 在本机建立 SSH 隧道：`ssh -L 58913:127.0.0.1:58913 tx`，然后访问 `http://localhost:58913/setup` 创建 Web 管理员。
2. 在 Web 控制台的“机器人管理”中，使用 TeamSpeak 3 服务器地址、频道、昵称和必要密码创建机器人。
3. 需要排障时使用：`ssh tx 'journalctl -u ts3audiobot.service -f'`；管理服务：`systemctl restart ts3audiobot.service`。

## 修复记录

- 2026-09-06 诊断：`v0.1.0` 发布 JAR 的 `templates/fragments/deps.html` 未加载 jQuery、Bootstrap 或其自带的 `cdn-loader.js`，但机器人管理页 `static/js/pages/index.js` 使用 `$` 与 `bootstrap.Modal`。因此编辑按钮的前端事件无法注册。
- 已修复：原始 JAR 已保存为 `/opt/ts3audiobot/app/TS3AudioBot-0.1.0.jar.before-web-fix-20260906`，SHA-256 为 `9e8a36a56f850564674f584e3928b44dfcbd5ee8e1af137a0413696b3609f093`。
- 已在运行 JAR 内加入本地 `jQuery 3.7.1`、`Bootstrap 5.3.3 CSS` 和 `Bootstrap 5.3.3 bundle JS`，并将公共模板改为在页面脚本前加载这些资源；不依赖浏览器访问外部 CDN。
- 最终 JAR SHA-256 为 `63805cb9cfadc6ab70814742b4126a0a88a776326b4c34a5963e96a6125b7fff`；ZIP 完整性检查通过，`ts3audiobot.service` 重启后为 `enabled`、`active`，重启后日志无错误或异常。
- 数据库与机器人记录未修改。若需回退，停止服务，将备份 JAR 覆盖回 `TS3AudioBot-0.1.0.jar` 后启动服务。

## 本地媒体上传

- 2026-09-06：已安装 `python3`，修复内置 `yt-dlp` 的运行时前提（此前该脚本报 `env: python3: No such file or directory`）。
- 已创建 `/opt/ts3audiobot/media/upload`，所有者为 `ts3audiobot`，并启用 `ts3audiobot-media.service`。该服务只监听 `127.0.0.1:18080`，不新增公网端口。
- 已使用临时 MP3 验证完整路径：本地 HTTP 服务返回 `audio/mpeg`，`yt-dlp` 成功解析 `http://127.0.0.1:18080/ts3ab-local-test.mp3`；测试文件已删除。
- 上传方式：`scp ./song.mp3 tx:/opt/ts3audiobot/media/upload/song.mp3`；在播放中心添加 `http://127.0.0.1:18080/song.mp3` 入队。
