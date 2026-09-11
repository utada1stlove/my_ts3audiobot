#!/usr/bin/env bash
# Install the pinned TS3AudioBot release as a local-only systemd service.

set -euo pipefail
IFS=$'\n\t'

VERSION="0.1.0"
SERVICE_USER="ts3audiobot"
INSTALL_ROOT="/opt/ts3audiobot"
APP_DIR="$INSTALL_ROOT/app"
SERVICE_FILE="/etc/systemd/system/ts3audiobot.service"
MEDIA_DIR="$INSTALL_ROOT/media/upload"
MEDIA_SERVICE_FILE="/etc/systemd/system/ts3audiobot-media.service"
ARCHIVE=""

usage() {
  cat <<'EOF'
Usage: sudo ./scripts/install-ts3audiobot.sh [--archive PATH]

Installs the pinned TS3AudioBot v0.1.0 release as user ts3audiobot.

Options:
  --archive PATH  Use a locally downloaded release ZIP instead of downloading it.
  -h, --help      Show this help text.

The script refuses to overwrite /opt/ts3audiobot and does not open firewall ports.
The Web console binds to 127.0.0.1:58913. A local media server binds to
127.0.0.1:18080, so uploaded tracks can be queued by URL.
EOF
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

while (($# > 0)); do
  case "$1" in
    --archive)
      (($# >= 2)) || die "--archive requires a path"
      ARCHIVE=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

((EUID == 0)) || die "Run this script as root, for example: sudo $0"
[[ ! -e "$INSTALL_ROOT" ]] || die "$INSTALL_ROOT already exists; refusing to overwrite an existing installation"

case "$(uname -m)" in
  x86_64)
    RELEASE_ARCH="linux-x64"
    RELEASE_SHA256="c85d4374f00a91e3bc5aeb4f6b5fe298f08bce3dc5d61d5267cdd63c5867b7c1"
    ;;
  aarch64)
    RELEASE_ARCH="linux-arm64"
    RELEASE_SHA256="67fbd973ba08a1cf9682aa57f4000eed8152b4bbe379a519b4b22fe97de83df3"
    ;;
  *)
    die "Unsupported CPU architecture: $(uname -m)"
    ;;
esac

RELEASE_NAME="TS3AudioBot-${VERSION}-${RELEASE_ARCH}.zip"
RELEASE_URL="https://github.com/ArthurZhu1992/TS3AudioBot/releases/download/v${VERSION}/${RELEASE_NAME}"
TEMP_DIR=$(mktemp -d)
ARCHIVE_PATH="$TEMP_DIR/$RELEASE_NAME"

cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

install_java21() {
  if java -version >/dev/null 2>&1; then
    local java_version
    java_version=$(java -version 2>&1 | head -1 | sed -E 's/.*version "([0-9]+).*/\1/')
    if [[ "$java_version" =~ ^(2[1-9]|[3-9][0-9]|[1-9][0-9]{2,})$ ]]; then
      return 0
    fi
  fi

  if apt-cache policy openjdk-21-jre-headless 2>/dev/null | awk '$1 == "Candidate:" && $2 != "(none)" { found=1 } END { exit !found }'; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends openjdk-21-jre-headless
    return 0
  fi

  echo "OpenJDK 21 is not packaged for this Debian release; installing Eclipse Temurin 21 JRE..."
  case "$(uname -m)" in
    x86_64) ADOPTIUM_ARCH="x64" ;;
    aarch64) ADOPTIUM_ARCH="aarch64" ;;
    *) die "Unsupported CPU architecture for Temurin: $(uname -m)" ;;
  esac

  local java_tar="$TEMP_DIR/temurin21-jre.tar.gz"
  local java_meta="$TEMP_DIR/temurin21.json"
  local java_link
  local java_sha
  curl --fail --location --retry 3 --retry-delay 2 --silent --show-error --output "$java_meta" \
    "https://api.adoptium.net/v3/assets/latest/21/hotspot?architecture=${ADOPTIUM_ARCH}&image_type=jre&os=linux&vendor=eclipse"
  java_link=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print([x["binary"]["package"]["link"] for x in d if x["binary"]["package"]["name"].endswith(".tar.gz")][0])' "$java_meta") || die "Failed to resolve Temurin 21 JRE download link"
  java_sha=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print([x["binary"]["package"]["checksum"] for x in d if x["binary"]["package"]["name"].endswith(".tar.gz")][0])' "$java_meta") || die "Failed to resolve Temurin 21 JRE checksum"
  [[ -n "$java_link" && -n "$java_sha" ]] || die "Temurin 21 JRE metadata was incomplete"

  curl --fail --location --retry 3 --retry-delay 2 --output "$java_tar" "$java_link"
  printf '%s  %s\n' "$java_sha" "$java_tar" | sha256sum --check --status || die "Temurin 21 JRE SHA-256 did not match"
  mkdir -p /opt
  [[ ! -e /opt/temurin21 ]] || die "/opt/temurin21 already exists; refusing to overwrite"
  tar -xzf "$java_tar" -C "$TEMP_DIR"
  local extracted_java
  extracted_java=$(find "$TEMP_DIR" -maxdepth 1 -type d -name 'jdk-21*' | head -1)
  [[ -n "$extracted_java" && -x "$extracted_java/bin/java" ]] || die "Temurin 21 JRE extraction failed"
  mv "$extracted_java" /opt/temurin21
  ln -sfn /opt/temurin21/bin/java /usr/local/bin/java
  hash -r 2>/dev/null || true
}

if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends curl python3 unzip ca-certificates
  install_java21
else
  die "Only Debian/Ubuntu systems using apt-get are currently supported"
fi

require_command openssl
require_command sha256sum
require_command unzip
java -version >/dev/null 2>&1 || die "Java 21 installation failed"

if [[ -n "$ARCHIVE" ]]; then
  [[ -f "$ARCHIVE" ]] || die "Archive does not exist: $ARCHIVE"
  cp -- "$ARCHIVE" "$ARCHIVE_PATH"
else
  printf 'Downloading TS3AudioBot v%s for %s...\n' "$VERSION" "$RELEASE_ARCH"
  curl --fail --location --retry 3 --retry-delay 2 --output "$ARCHIVE_PATH" "$RELEASE_URL"
fi

printf '%s  %s\n' "$RELEASE_SHA256" "$ARCHIVE_PATH" | sha256sum --check --status || die "Release SHA-256 did not match"
unzip -tqq "$ARCHIVE_PATH"

while IFS= read -r archive_entry; do
  [[ "$archive_entry" == "TS3AudioBot-${VERSION}/"* ]] || die "Unexpected archive entry: $archive_entry"
  [[ "/$archive_entry/" != *"/../"* ]] || die "Unsafe archive entry: $archive_entry"
done < <(unzip -Z1 "$ARCHIVE_PATH")

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$INSTALL_ROOT" --shell /usr/sbin/nologin --user-group "$SERVICE_USER"
fi

install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$INSTALL_ROOT"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$MEDIA_DIR"
unzip -q "$ARCHIVE_PATH" -d "$INSTALL_ROOT"
mv "$INSTALL_ROOT/TS3AudioBot-${VERSION}" "$APP_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_ROOT"

SEARCH_SECRET=$(openssl rand -hex 32)
sed -i \
  -e 's/hosts = \["\*"\]/hosts = ["localhost", "127.0.0.1"]/' \
  -e "s/auth_secret = \"CHANGE_ME\"/auth_secret = \"$SEARCH_SECRET\"/" \
  -e 's/audio_cache_enabled = true/audio_cache_enabled = false/' \
  "$APP_DIR/ts3Audio-config.toml"
chmod 0640 "$APP_DIR/ts3Audio-config.toml"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=TS3AudioBot web and TeamSpeak audio service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$APP_DIR
Environment=TS3AB_WEB_ADDRESS=127.0.0.1
ExecStart=$APP_DIR/start.sh
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF

cat > "$MEDIA_SERVICE_FILE" <<EOF
[Unit]
Description=TS3AudioBot local media server
After=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$MEDIA_DIR
ExecStart=/usr/bin/python3 -m http.server 18080 --bind 127.0.0.1 --directory $MEDIA_DIR
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadOnlyPaths=$MEDIA_DIR

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now ts3audiobot.service ts3audiobot-media.service
systemctl is-active --quiet ts3audiobot.service || die "Service did not start; inspect: journalctl -u ts3audiobot.service -n 100 --no-pager"
systemctl is-active --quiet ts3audiobot-media.service || die "Local media service did not start; inspect: journalctl -u ts3audiobot-media.service -n 100 --no-pager"

printf 'Installed TS3AudioBot v%s.\n' "$VERSION"
printf 'Create an SSH tunnel: ssh -L 58913:127.0.0.1:58913 user@server\n'
printf 'Then open: http://localhost:58913/setup\n'
printf 'Upload files to: %s\n' "$MEDIA_DIR"
printf 'Queue uploaded files with: http://127.0.0.1:18080/FILENAME.mp3\n'
