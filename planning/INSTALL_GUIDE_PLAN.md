# TS3AudioBot 安装指南计划

- 状态：完成
- 范围：根据本仓库 README 指向的两个 TS3AudioBot 上游仓库，整理一份可在 Linux 服务器执行的中文安装与 Web 控制指南。
- 事实来源：README.MD；Splamy/TS3AudioBot 与 ArthurZhu1992/TS3AudioBot 的官方 GitHub README、发行页及文档（检索日期：2026-09-06）。
- 交付物：`INSTALL_GUIDE_CN.md`。
- 验收：命令与上游文档一致；清楚标示选择分支、前置条件、Web 控制、配置和安全注意事项；链接有效；运行工作区检查与 `git diff --check`（若当前目录可识别为 Git 仓库）。
- 清理：不生成构建产物或临时安装文件。

## 已完成

1. 已读取两个上游仓库的官方安装、配置与 Web 控制资料。
2. 已编写中文安装与控制指南，推荐具有原生 Web 控制台的 ArthurZhu1992 发行包。

## 验证结果

3. `basic-validation` 工作区检查通过（退出码 0）。
4. `INSTALL_GUIDE_CN.md` 的 14 个代码围栏成对闭合；已人工核对官方来源链接、下载 URL 与 Linux x86_64 SHA-256。
5. 未生成 TeX/PDF 或其他构建中间文件。
6. 未运行 `git diff --check`：当前目录不是 Git 工作树（`git diff --check` 返回 “Not a git repository”），因此该项不适用。
