#!/bin/bash
# Book-pipeline healthcheck — alerts on Telegram ONLY when something is wrong.
# The whole stack failed silently for weeks (sync host-key, bridge parse bug);
# this exists so silent rot becomes a ping. Cron: daily 09:00.
set -u
source /home/dave/scripts/wanted_monitor.env 2>/dev/null
CFG=/home/dave/docker-apps/lazylibrarian/config/config.ini
PROBLEMS=()

# 1. LazyLibrarian API
LLKEY=$(grep "^api_key" "$CFG" | awk "{print \$3}")
curl -sf -m 10 "http://192.168.1.113:5299/api?cmd=getVersion&apikey=$LLKEY" | grep -q Success || PROBLEMS+=("LazyLibrarian API not responding")

# 2. SABnzbd API (with LL stored key)
SABKEY=$(grep "^sab_api" "$CFG" | awk "{print \$3}")
curl -sf -m 10 "http://192.168.1.113:8082/api?mode=queue&output=json&apikey=$SABKEY" | grep -q queue || PROBLEMS+=("SABnzbd API failing (key/whitelist?)")

# 3. OpenBooks websocket handshake
python3 - << PY >/dev/null 2>&1 || PROBLEMS+=("OpenBooks websocket handshake failing")
import asyncio, websockets, json, sys
async def t():
    async with websockets.connect("ws://192.168.1.248:6081/ws", open_timeout=8) as ws:
        await ws.send(json.dumps({"type":1,"payload":{}}))
        for _ in range(3):
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if m.get("type") == 1: return
            except asyncio.TimeoutError: pass
        sys.exit(1)
asyncio.run(t())
PY

# 4. Library sync freshness (last rsync run on homelab-pi succeeded)
LAST=$(ssh -o BatchMode=yes -o ConnectTimeout=8 dave@192.168.1.248 "tail -1 ~/scripts/sync.log" 2>/dev/null)
echo "$LAST" | grep -q "speedup" || PROBLEMS+=("Library sync last run FAILED: ${LAST:0:80}")

# 5. Stale .temp downloads (stuck DCC transfers >2h)
STALE=$(ssh -o BatchMode=yes -o ConnectTimeout=8 dave@192.168.1.248 "find ~/Downloads/openbooks/books -name \"*.temp\" -mmin +120 2>/dev/null" 2>/dev/null)
[ -n "$STALE" ] && PROBLEMS+=("Stale stuck download(s): $(basename "$STALE" 2>/dev/null | head -1)")

# 6. Bridge failure streak in wanted_monitor log (last 24h)
FAILS=$(grep -c "bridge failed\|bridge timeout" <(tail -500 /home/dave/scripts/wanted_monitor.log 2>/dev/null) 2>/dev/null || echo 0)
[ "${FAILS:-0}" -gt 20 ] && PROBLEMS+=("OpenBooks bridge failing repeatedly ($FAILS recent)")

if [ ${#PROBLEMS[@]} -gt 0 ]; then
  MSG="📚 Book pipeline problems:"
  for p in "${PROBLEMS[@]}"; do MSG="$MSG%0A- $p"; done
  curl -sf -m 10 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage?chat_id=${TELEGRAM_CHAT_ID}&text=${MSG}" >/dev/null
  echo "ALERTED: ${#PROBLEMS[@]} problems"; printf "%s\n" "${PROBLEMS[@]}"
  exit 1
fi
echo "all healthy"
