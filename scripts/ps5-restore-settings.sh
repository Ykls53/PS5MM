#!/usr/bin/env bash
# Confirm the CPU pinning survived, and put the speech model paths back in the
# console's settings (they were pointed at audio.cpp during the experiment).
set -uo pipefail
echo "==== tts_server CPU pinning ===="
grep -n 'n_gpu_layers' /home/yk/PS5MM/ps5/app/tts_server.cpp
grep -n 'mp.use_gpu' /home/yk/PS5MM/ps5/app/tts_server.cpp
echo "==== settings on the console ===="
python3 - <<'PY'
import ftplib, io, json
f = ftplib.FTP(); f.connect("192.168.5.50", 2121, timeout=20); f.login(); f.sock.settimeout(120)
buf = io.BytesIO(); f.retrbinary("RETR /data/PS5MM/settings.json", buf.write)
s = json.loads(buf.getvalue().decode("utf-8"))
s["tts_backbone"] = "/data/PS5MM/tts/backbone.gguf"
s["tts_mmproj"]   = "/data/PS5MM/tts/mmproj.gguf"
s["voices_dir"]   = "/data/PS5MM/voices"
s["audio_model"]  = "/data/PS5MM/audio/model.gguf"
s["audio_dir"]    = "/data/PS5MM/audio"
f.storbinary("STOR /data/PS5MM/settings.json",
             io.BytesIO(json.dumps(s, indent=4, ensure_ascii=False).encode("utf-8")))
print("  tts_backbone =", s["tts_backbone"])
print("  tts_mmproj   =", s["tts_mmproj"])
print("  audio_model  =", s["audio_model"])
print("  sd_diffusion =", s["sd_diffusion"])
print("  sd_video     =", s["sd_video"])
print("  sd_video_t5xxl =", s["sd_video_t5xxl"])
f.quit()
PY
