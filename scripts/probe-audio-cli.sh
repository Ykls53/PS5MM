#!/usr/bin/env bash
set -uo pipefail
cd /home/yk/ext/audio.cpp || exit 1
echo "==== cli help: task options ===="
build-vulkan/bin/audiocpp_cli --help 2>&1 | sed -n '45,130p'
echo "==== c api sources ===="
find . -maxdepth 3 \( -name '*c_api*' -o -name 'audiocpp_c*' \) -not -path './build-*' 2>/dev/null | head -10
echo "==== kitten spec ===="
python3 -c "import json;d=json.load(open('model_specs/kitten_tts2.json'));print(json.dumps(d,indent=1)[:1500])" 2>/dev/null || ls model_specs | grep -i kitten
