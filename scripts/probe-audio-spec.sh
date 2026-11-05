#!/usr/bin/env bash
set -uo pipefail
cd /home/yk/ext/audio.cpp || exit 1
echo "==== qwen3_tts spec (runtime/options/required files) ===="
python3 - <<'PY'
import json
d = json.load(open('model_specs/qwen3_tts.json'))
for k in ('family','display_name','tasks','languages','runtime','resources','files','assets','options'):
    if k in d:
        v = d[k]
        print(k, '=', json.dumps(v, ensure_ascii=False)[:600])
PY
echo "==== espeak present? ===="
ldconfig -p 2>/dev/null | grep -i espeak | head -3
ls /usr/lib/x86_64-linux-gnu/libespeak* 2>/dev/null | head -3
echo "==== c api doc head ===="
sed -n '1,40p' docs/c_api.md
