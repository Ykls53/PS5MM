#!/usr/bin/env bash
# The text engine, verified on the PC through llama.cpp's own server: same
# model file, same -ngl 0 / CPU reality as the host build. Not the title's
# embedded server, but the model + sampling path is what we are checking.
set -uo pipefail
L=/home/yk/PS5MM/third_party/llama.cpp/build-pc/bin
M=/data/PS5MM/models/Qwen3-0.6B-Q8_0.gguf
export LD_LIBRARY_PATH="$L:${LD_LIBRARY_PATH:-}"
pkill -f 'llama-server.*8011' 2>/dev/null && sleep 1
nohup "$L/llama-server" -m "$M" --host 127.0.0.1 --port 8011 -c 2048 -ngl 0 \
    -t 8 --no-warmup > /tmp/llama-text.log 2>&1 &
for i in $(seq 1 60); do
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 2 http://127.0.0.1:8011/health 2>/dev/null)
    [ "$code" = "200" ] && break
    sleep 1
done
echo "health=$code after ${i}s"
echo "==== chat completion ===="
curl -s -m 120 http://127.0.0.1:8011/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Say hello in five words."}],"max_tokens":32,"temperature":0.2}' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["choices"][0]["message"]["content"][:200]); print("timings:", d.get("timings",{}).get("predicted_per_second"))'
echo "==== log tail ===="
grep -E 'llama_model_load|server listening|n_ctx|slot' /tmp/llama-text.log | tail -6
pkill -f 'llama-server.*8011' 2>/dev/null
echo done
