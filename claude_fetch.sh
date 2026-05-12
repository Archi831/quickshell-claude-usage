#!/usr/bin/env bash
set -euo pipefail

CACHE_FILE="/tmp/waybar_claude_cache.json"
CACHE_TTL=180
COOKIE_DB="$HOME/.config/chromium/Default/Cookies"
COOKIE_TMP="/tmp/qs_claude_cookies.sqlite"
LOCK_FILE="/tmp/qs_claude_fetch.lock"

get_aes_key() {
    local secret
    secret=$(secret-tool lookup application chromium 2>/dev/null) || { echo ""; return; }
    python3 -c "
import hashlib, binascii, sys
secret = sys.argv[1].encode()
key = hashlib.pbkdf2_hmac('sha1', secret, b'saltysalt', 1, 16)
print(binascii.hexlify(key).decode())
" "$secret"
}

fetch_usage() {
    cp "$COOKIE_DB" "$COOKIE_TMP" 2>/dev/null || return 1
    local key_hex
    key_hex=$(get_aes_key) || return 1
    [ -z "$key_hex" ] && return 1

    local session_key org_id
    session_key=$(python3 -c "
import sqlite3, subprocess, hashlib, binascii, sys

key_hex = sys.argv[1]
conn = sqlite3.connect(sys.argv[2])
rows = dict(conn.execute(\"SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%claude.ai%' AND name IN ('sessionKey','lastActiveOrg')\").fetchall())
conn.close()

for name, enc in rows.items():
    enc = bytes(enc)[3:]
    with open('/tmp/qs_claude_enc.bin', 'wb') as f:
        f.write(enc)
    import subprocess as sp
    r = sp.run(['openssl','enc','-aes-128-cbc','-d','-nopad','-K',key_hex,'-iv','20'*16,'-in','/tmp/qs_claude_enc.bin'], capture_output=True)
    if r.returncode == 0:
        raw = r.stdout
        content = raw[32:]
        pad = content[-1]
        if 1 <= pad <= 16: content = content[:-pad]
        print(name + '=' + content.decode('utf-8','replace').strip())
" "$key_hex" "$COOKIE_TMP" 2>/dev/null) || return 1

    local sk org
    sk=$(echo "$session_key" | grep '^sessionKey=' | cut -d= -f2-)
    org=$(echo "$session_key" | grep '^lastActiveOrg=' | cut -d= -f2-)
    [ -z "$sk" ] || [ -z "$org" ] && return 1

    local cookie_hdr
    cookie_hdr=$(python3 -c "
import sqlite3, subprocess, hashlib, binascii, sys

key_hex = sys.argv[1]
conn = sqlite3.connect(sys.argv[2])
rows = conn.execute(\"SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%claude.ai%'\").fetchall()
conn.close()
parts = []
for name, enc in rows:
    enc = bytes(enc)[3:]
    with open('/tmp/qs_claude_enc.bin', 'wb') as f:
        f.write(enc)
    import subprocess as sp
    r = sp.run(['openssl','enc','-aes-128-cbc','-d','-nopad','-K',key_hex,'-iv','20'*16,'-in','/tmp/qs_claude_enc.bin'], capture_output=True)
    if r.returncode == 0:
        raw = r.stdout
        content = raw[32:]
        pad = content[-1]
        if 1 <= pad <= 16: content = content[:-pad]
        val = content.decode('utf-8','replace').strip()
        if val: parts.append(f'{name}={val}')
print('; '.join(parts))
" "$key_hex" "$COOKIE_TMP" 2>/dev/null)

    curl -s --max-time 8 \
        "https://claude.ai/api/organizations/$org/usage" \
        -H "Cookie: $cookie_hdr" \
        -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36" \
        -H "Accept: application/json" \
        -H "Referer: https://claude.ai/"
}

read_cache() {
    python3 -c "
import json
d = json.load(open('$CACHE_FILE'))['data']
fh = d.get('five_hour') or {}
sd = d.get('seven_day') or {}
print(json.dumps({
    'fiveHour': fh.get('utilization', 0),
    'sevenDay': sd.get('utilization', 0),
    'fiveHourResetsAt': fh.get('resets_at', ''),
    'sevenDayResetsAt': sd.get('resets_at', '')
}))
" 2>/dev/null
}

cache_age() {
    python3 -c "import time,json; d=json.load(open('$CACHE_FILE')); print(int(time.time()-d.get('ts',0)))" 2>/dev/null || echo 9999
}

# Fast path: serve from cache without a lock
if [ -f "$CACHE_FILE" ]; then
    if [ "$(cache_age)" -lt "$CACHE_TTL" ]; then
        read_cache && exit 0
    fi
fi

# Cache is stale; acquire lock so only one instance fetches at a time
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    # Another instance is already fetching — wait for it to finish, then read its result
    flock 200
    if [ -f "$CACHE_FILE" ] && [ "$(cache_age)" -lt "$CACHE_TTL" ]; then
        read_cache && exit 0
    fi
    exit 1
fi

# Got the lock; fetch fresh data
raw=$(fetch_usage 2>/dev/null) || exit 1

python3 -c "
import json, time
raw = '''$raw'''
d = json.loads(raw)
if 'type' in d and d.get('type') == 'error':
    import sys; sys.exit(1)
fh = d.get('five_hour') or {}
sd = d.get('seven_day') or {}
result = {
    'fiveHour': fh.get('utilization', 0),
    'sevenDay': sd.get('utilization', 0),
    'fiveHourResetsAt': fh.get('resets_at', ''),
    'sevenDayResetsAt': sd.get('resets_at', '')
}
with open('$CACHE_FILE', 'w') as f:
    json.dump({'ts': time.time(), 'data': d}, f)
print(json.dumps(result))
" 2>/dev/null || exit 1
