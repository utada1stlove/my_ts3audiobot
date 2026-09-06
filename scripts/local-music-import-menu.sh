#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ ${EUID} -ne 0 ]]; then
    exec sudo -- "$0" "$@"
fi
exec python3 "$script_dir/local-music-import-menu.py" "$@"
