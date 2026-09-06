# 本地音乐库功能计划

- 状态：已完成（改用直接队列导入，未部署网页改造）
- 目标：将 VPS 已上传的本地音乐按目录批量写入既有播放列表，不调用解析器或 `yt-dlp`。
- 交付物：可复用导入脚本、VPS 队列备份与验证记录；本地使用说明。
- 安全边界：只扫描配置的上传目录；拒绝路径回退、符号链接逃逸与非音频文件；Web 服务维持回环绑定；不删除任何音乐、队列或数据库记录。
- 验收：能列出已上传音频；能选择目标机器人和歌单；批量加入请求经后端验证；项目构建与测试通过；部署后 Web 页面/接口和已有服务正常。

## 已完成

1. 获取与已部署 `v0.1.0` 一致的上游源码副本：`/tmp/ts3audiobot-v0.1.0-source`。
2. 实现本地音乐库：只读扫描 `/opt/ts3audiobot/media/upload`，过滤支持的音频格式、拒绝符号链接和目录回退，并按路径段编码回环媒体 URL。
3. 增加认证后的 `GET /internal/library` 与批量入队端点；仅允许已扫描到的文件，单次最多 500 首，并去重。
4. 在播放中心增加“本地音乐库”弹窗，可筛选、全选筛选结果并批量加入当前歌单。
5. 将 jQuery 与 Bootstrap 本地资源纳入构建；资源从当前运行 JAR 提取，避免依赖外部 CDN。
6. 增加服务与控制器单元测试；浏览器脚本语法与源码差异空白检查通过。
7. VPS 已安装 `openjdk-21-jdk-headless`，并成功下载 Gradle 9.3.0；此前仅有 Java 运行时，无法构建。

## 最终结果

- 2026-09-07：VPS 恢复后，确认 `ts3audiobot.service` 与 `ts3audiobot-media.service` 均为 `active`，上传目录保持 208 个文件。
- 使用 `scripts/import-local-music-queues.py` 直接写入 `LacusClyne` 的既有歌单：`seed` 26 首、`FinalFantasy` 1 首、`Nier` 156 首。唯一的 Final Fantasy 曲目为 `No Promises to Keep`。
- 导入前备份：`/opt/ts3audiobot/app/data/queues.json.before-local-import-20260907T022245Z`。
- 导入时短暂停止服务，原子写入队列后恢复服务；所有 183 个条目均为 `sourceType: local`，未调用 Web 入队接口或 `yt-dlp`。日志确认 FFmpeg 已正常输出音频帧。
- 交互式菜单已安装：`/opt/ts3audiobot/tools/local-music-import-menu.sh`。它支持选择机器人、歌单、顶层目录、专辑目录或单曲，并在确认前预演与去重。
- 未部署 `/tmp/ts3audiobot-v0.1.0-source` 中的网页本地音乐库改造，也未替换运行 JAR。

## 复用方式

1. 新增 WAV 文件后运行导入脚本的预演；它会跳过已按相同相对路径导入的条目。
2. 预演数量符合预期后，备份 `queues.json`，停止服务，使用 `--write` 写入，校验 JSON、恢复文件所有权并启动服务。
3. 分类规则：`Gundam S.E.E.D. Music/` 到 `seed`；`No Promises to Keep` 到 `FinalFantasy`；其余 `SQUARE ENIX MUSIC/` WAV 到 `Nier`。
