#!/usr/bin/env python3
"""Import the uploaded local WAV library into TS3AudioBot queue storage.

This tool deliberately writes local Track records directly. It never calls the
web queue API, so no resolver or yt-dlp process is involved.
"""

import argparse
import json
import os
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote


PLAYLISTS = ("seed", "FinalFantasy", "Nier")
NUMBER_PREFIX = re.compile(r"^\d+\s+")


def playlist_for(path: Path) -> str | None:
    parts = path.parts
    if not parts:
        return None
    if parts[0] == "Gundam S.E.E.D. Music":
        return "seed"
    if "No Promises to Keep" in path.name:
        return "FinalFantasy"
    if parts[0] == "SQUARE ENIX MUSIC":
        return "Nier"
    return None


def stream_url(relative_path: Path) -> str:
    return "http://127.0.0.1:18080/" + "/".join(quote(part, safe="") for part in relative_path.parts)


def load_state(queue_path: Path) -> dict:
    if not queue_path.exists():
        return {"queues": {}, "activePlaylists": {}, "playlistPositions": {}}
    with queue_path.open(encoding="utf-8") as source:
        return json.load(source)


def local_track(bot_id: str, playlist_id: str, relative_path: Path) -> dict:
    title = NUMBER_PREFIX.sub("", relative_path.stem)
    artist = relative_path.parent.name if relative_path.parent != Path(".") else ""
    return {
        "id": str(uuid.uuid4()),
        "botId": bot_id,
        "playlistId": playlist_id,
        "track": {
            "id": str(uuid.uuid4()),
            "title": title,
            "sourceType": "local",
            "sourceId": relative_path.as_posix(),
            "streamUrl": stream_url(relative_path),
            "durationMs": 0,
            "coverUrl": "",
            "artist": artist,
            "playCount": None,
        },
        "addedAt": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "addedBy": "local-library-import",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--queue-file", type=Path, required=True)
    parser.add_argument("--bot", required=True)
    parser.add_argument("--write", action="store_true", help="Write the prepared queue state atomically.")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Media root does not exist: {root}")
    state = load_state(args.queue_file)
    queues = state.setdefault("queues", {})
    bot_queues = queues.setdefault(args.bot, {})
    positions = state.setdefault("playlistPositions", {}).setdefault(args.bot, {})
    state.setdefault("activePlaylists", {}).setdefault(args.bot, "FinalFantasy")

    added = {playlist: 0 for playlist in PLAYLISTS}
    skipped = {playlist: 0 for playlist in PLAYLISTS}
    existing = set()
    for playlist in PLAYLISTS:
        entries = bot_queues.setdefault(playlist, [])
        positions.setdefault(playlist, 0)
        for entry in entries:
            source_id = entry.get("track", {}).get("sourceId")
            if isinstance(source_id, str):
                existing.add((playlist, source_id))

    for absolute_path in sorted(root.rglob("*.wav")):
        if absolute_path.is_symlink() or not absolute_path.is_file():
            continue
        relative_path = absolute_path.relative_to(root)
        playlist = playlist_for(relative_path)
        if playlist is None:
            continue
        key = (playlist, relative_path.as_posix())
        if key in existing:
            skipped[playlist] += 1
            continue
        bot_queues[playlist].append(local_track(args.bot, playlist, relative_path))
        existing.add(key)
        added[playlist] += 1

    print(json.dumps({"added": added, "skippedExisting": skipped, "write": args.write}, ensure_ascii=False))
    if not args.write:
        return 0

    args.queue_file.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=args.queue_file.name + ".", dir=args.queue_file.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            json.dump(state, target, ensure_ascii=False, separators=(",", ":"))
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary_name, args.queue_file)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
