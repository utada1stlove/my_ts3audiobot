#!/usr/bin/env python3
"""Interactive, resolver-free importer for the local TS3AudioBot music library."""

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote


AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}
NUMBER_PREFIX = re.compile(r"^\d+\s+")
GHOST_BOT_SECTIONS = ("queues", "activePlaylists", "playlistPositions")


def prompt_one(title: str, choices: list[str], allow_new: bool = False) -> str:
    while True:
        print(f"\n{title}")
        for index, choice in enumerate(choices, start=1):
            print(f"  {index}. {choice}")
        if allow_new:
            print("  n. 新建歌单")
        answer = input("输入编号（q 退出）：").strip()
        if answer.lower() == "q":
            raise SystemExit("已取消，不会修改队列。")
        if allow_new and answer.lower() == "n":
            name = input("新歌单名称：").strip()
            if name and "/" not in name and "\\" not in name:
                return name
            print("歌单名称不能为空，且不能包含 / 或 \\。")
            continue
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]
        print("请输入列表中的有效编号。")


def parse_indices(raw: str, limit: int) -> list[int]:
    result: set[int] = set()
    for chunk in raw.split(","):
        part = chunk.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            if not start_text.strip().isdigit() or not end_text.strip().isdigit():
                raise ValueError
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError
            result.update(range(start, end + 1))
        elif part.isdigit():
            result.add(int(part))
        else:
            raise ValueError
    if not result or any(index < 1 or index > limit for index in result):
        raise ValueError
    return sorted(result)


def choose_many(title: str, choices: list[str]) -> list[int]:
    print(f"\n{title}")
    for index, choice in enumerate(choices, start=1):
        print(f"  {index:>3}. {choice}")
    while True:
        raw = input("输入编号（逗号或范围，例如 1,3-5；q 退出）：").strip()
        if raw.lower() == "q":
            raise SystemExit("已取消，不会修改队列。")
        try:
            return parse_indices(raw, len(choices))
        except ValueError:
            print("选择无效，请重新输入。")


def list_audio_files(root: Path) -> list[Path]:
    return sorted(
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path.suffix.lower() in AUDIO_EXTENSIONS
    )


def choose_files(audio_files: list[Path]) -> list[Path]:
    top_level = sorted({path.parts[0] for path in audio_files if path.parts})
    leaf_folders = sorted({path.parent.as_posix() for path in audio_files})
    while True:
        print("\n选择导入范围")
        print("  1. 按顶层文件夹")
        print("  2. 按专辑/艺人子文件夹")
        print("  3. 逐首选择")
        print("  4. 导入全部音频")
        mode = input("输入编号（q 退出）：").strip().lower()
        if mode == "q":
            raise SystemExit("已取消，不会修改队列。")
        if mode == "1":
            selected = {top_level[index - 1] for index in choose_many("顶层文件夹", top_level)}
            return [path for path in audio_files if path.parts[0] in selected]
        if mode == "2":
            selected = {leaf_folders[index - 1] for index in choose_many("专辑/艺人子文件夹", leaf_folders)}
            return [path for path in audio_files if path.parent.as_posix() in selected]
        if mode == "3":
            labels = [path.as_posix() for path in audio_files]
            return [audio_files[index - 1] for index in choose_many("音频文件", labels)]
        if mode == "4":
            return audio_files
        print("请输入 1 到 4。")


def stream_url(media_url: str, relative_path: Path) -> str:
    return media_url.rstrip("/") + "/" + "/".join(quote(part, safe="") for part in relative_path.parts)


def track_item(bot_id: str, playlist_id: str, path: Path, media_url: str) -> dict:
    title = NUMBER_PREFIX.sub("", path.stem)
    artist = path.parent.name if path.parent != Path(".") else ""
    return {
        "id": str(uuid.uuid4()),
        "botId": bot_id,
        "playlistId": playlist_id,
        "track": {
            "id": str(uuid.uuid4()),
            "title": title,
            "sourceType": "local",
            "sourceId": path.as_posix(),
            "streamUrl": stream_url(media_url, path),
            "durationMs": 0,
            "coverUrl": "",
            "artist": artist,
            "playCount": None,
        },
        "addedAt": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "addedBy": "local-library-menu",
    }


def load_state(queue_file: Path) -> dict:
    with queue_file.open(encoding="utf-8") as source:
        return json.load(source)


def load_real_bot_names(db_file: Path) -> set[str] | None:
    if not db_file.is_file():
        print(f"警告：未找到数据库 {db_file}，跳过幽灵机器人清理。")
        return None
    try:
        with sqlite3.connect(f"file:{db_file.as_posix()}?mode=ro", uri=True) as connection:
            rows = connection.execute("SELECT name FROM bots").fetchall()
        return {row[0] for row in rows if isinstance(row[0], str)}
    except (sqlite3.Error, OSError, ValueError) as exc:
        print(f"警告：无法读取数据库 {db_file}，跳过幽灵机器人清理：{exc}")
        return None


def find_ghost_bot_keys(state: dict, real_bots: set[str]) -> list[str]:
    ghosts: set[str] = set()
    for section in GHOST_BOT_SECTIONS:
        mapping = state.get(section)
        if isinstance(mapping, dict):
            ghosts.update(key for key in mapping if isinstance(key, str) and key not in real_bots)
    return sorted(ghosts)


def remove_ghost_bots(state: dict, real_bots: set[str]) -> list[str]:
    ghost_keys = find_ghost_bot_keys(state, real_bots)
    ghost_set = set(ghost_keys)
    for section in GHOST_BOT_SECTIONS:
        mapping = state.get(section)
        if isinstance(mapping, dict):
            for key in ghost_set:
                mapping.pop(key, None)
    return ghost_keys


def print_ghost_bots(ghost_keys: list[str]) -> None:
    if not ghost_keys:
        return
    print("\n检测到幽灵机器人，IMPORT 时会从队列文件中删除：")
    for key in ghost_keys:
        print(f"  - {key}")
    print("删除范围：queues、activePlaylists、playlistPositions。")


def write_atomically(queue_file: Path, state: dict, owner: os.stat_result) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=queue_file.name + ".", dir=queue_file.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            json.dump(state, target, ensure_ascii=False, separators=(",", ":"))
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.chmod(temporary_name, owner.st_mode)
        os.chown(temporary_name, owner.st_uid, owner.st_gid)
        os.replace(temporary_name, queue_file)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/opt/ts3audiobot/media/upload"))
    parser.add_argument("--queue-file", type=Path, default=Path("/opt/ts3audiobot/app/data/queues.json"))
    parser.add_argument("--db-file", type=Path, default=Path("/opt/ts3audiobot/app/data/ts3audiobot.db"))
    parser.add_argument("--service", default="ts3audiobot.service")
    parser.add_argument("--media-url", default="http://127.0.0.1:18080/")
    parser.add_argument("--dry-run", action="store_true", help="Show the selection preview without writing or stopping the service.")
    args = parser.parse_args()

    root = args.root.resolve()
    queue_file = args.queue_file.resolve()
    if not root.is_dir() or not queue_file.is_file():
        raise SystemExit("找不到音乐目录或队列文件。")
    state = load_state(queue_file)
    queues = state.setdefault("queues", {})
    ghost_keys: list[str] = []
    real_bots = load_real_bot_names(args.db_file.resolve())
    if real_bots is None:
        bots = sorted(queues)
    else:
        ghost_keys = find_ghost_bot_keys(state, real_bots)
        print_ghost_bots(ghost_keys)
        if not real_bots:
            raise SystemExit("ts3audiobot.db 中没有机器人。请先在网页创建机器人。")
        bots = sorted(real_bots)
    if not bots:
        raise SystemExit("队列文件中没有机器人。请先在网页创建机器人。")
    bot_id = prompt_one("选择机器人", bots)
    bot_queues = queues.setdefault(bot_id, {})
    playlist_id = prompt_one("选择导入目标歌单", sorted(bot_queues), allow_new=True)
    audio_files = list_audio_files(root)
    if not audio_files:
        raise SystemExit("上传目录中没有支持的音频文件。")
    selected = choose_files(audio_files)
    destination = bot_queues.setdefault(playlist_id, [])
    positions = state.setdefault("playlistPositions", {}).setdefault(bot_id, {})
    positions.setdefault(playlist_id, 0)
    state.setdefault("activePlaylists", {}).setdefault(bot_id, playlist_id)
    existing = {
        item.get("track", {}).get("sourceId")
        for item in destination
        if isinstance(item.get("track", {}).get("sourceId"), str)
    }
    additions = [path for path in selected if path.as_posix() not in existing]
    duplicates = len(selected) - len(additions)

    print(f"\n目标：{bot_id} / {playlist_id}")
    print(f"选择：{len(selected)} 首；新增：{len(additions)} 首；已存在跳过：{duplicates} 首")
    for path in additions[:10]:
        print(f"  + {path}")
    if len(additions) > 10:
        print(f"  ... 另有 {len(additions) - 10} 首")
    if args.dry_run:
        print("预演结束，未修改队列。")
        return 0
    if not additions and not ghost_keys:
        print("没有新增，未修改队列。")
        return 0
    if os.geteuid() != 0:
        raise SystemExit("实际导入需要 root 权限。请使用 sudo 运行此脚本。")
    if ghost_keys:
        print(f"本次写入还会删除 {len(ghost_keys)} 个幽灵机器人。")
        confirm_text = "输入 IMPORT 确认写入并短暂停止机器人服务（将删除幽灵机器人）："
    else:
        confirm_text = "输入 IMPORT 确认写入并短暂停止机器人服务："
    if input(confirm_text).strip() != "IMPORT":
        raise SystemExit("未确认，未修改队列。")

    if ghost_keys:
        remove_ghost_bots(state, real_bots)
    for path in additions:
        destination.append(track_item(bot_id, playlist_id, path, args.media_url))
    original_metadata = queue_file.stat()
    backup = queue_file.with_name(queue_file.name + ".before-menu-import-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    service_stopped = False
    try:
        subprocess.run(["systemctl", "stop", args.service], check=True)
        service_stopped = True
        shutil.copy2(queue_file, backup)
        write_atomically(queue_file, state, original_metadata)
        subprocess.run(["python3", "-m", "json.tool", str(queue_file)], check=True, stdout=subprocess.DEVNULL)
    finally:
        if service_stopped:
            subprocess.run(["systemctl", "start", args.service], check=False)
    subprocess.run(["systemctl", "is-active", "--quiet", args.service], check=True)
    if ghost_keys:
        print(f"导入完成：新增 {len(additions)} 首，删除幽灵机器人 {len(ghost_keys)} 个。备份：{backup}")
    else:
        print(f"导入完成：新增 {len(additions)} 首。备份：{backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
