#!/usr/bin/env bash
# Is the console awake, and are the payload ports up? ARP first -- a bare socket
# scan lies while a TUN adapter is up.
set -uo pipefail
IP=${1:-192.168.5.50}
echo "==== arp ===="
ip neigh show 2>/dev/null | grep -i "${IP%.*}." | head -5
echo "==== ping ===="
ping -c 2 -W 2 "$IP" 2>&1 | tail -3
echo "==== ports (curl, bound to the LAN interface) ===="
for p in 8780 2121 10101 9021; do
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 3 "http://$IP:$p/" 2>/dev/null)
    echo "http :$p -> $code"
done
echo "==== ftp welcome (correct way; curl can't judge FTP) ===="
python3 - "$IP" <<'PY'
import sys
from ftplib import FTP
try:
    f = FTP()
    f.connect(sys.argv[1], 2121, timeout=6)
    f.login()
    print("FTP login ok:", f.getwelcome())
    f.voidcmd("NOOP")
    print("NOOP ok")
    f.quit()
except Exception as e:
    print("FTP failed:", type(e).__name__, e)
PY
