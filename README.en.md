# PS5MM

[![中文](https://img.shields.io/badge/%E8%AF%AD%E8%A8%80-%E4%B8%AD%E6%96%87-4f8cff)](README.md)
[![English](https://img.shields.io/badge/lang-English-6b7280)](README.en.md)

**A full-modality AI server on a PlayStation 5.** One native title, one process, one
12 GB memory pool, six capabilities at once — text, image, video, voice cloning, 3D,
frame interpolation — all running on the console's own GPU through Vulkan/RADV, no CUDA.

```
8001  text    llama.cpp              OpenAI + Anthropic dialects
8002  image   stable-diffusion.cpp   A1111 compatible + RIFE interpolation
8003  voice   VoxCPM.cpp             OpenAI TTS + 3-second reference cloning
8004  video   stable-diffusion.cpp   Wan, shares the sd context with 8002
8005  3D      trellis.cpp            image-to-GLB with UV textures
8099  ctrl    /alive /quit
```

## Five engines

| # | Engine | Port | Capability | Notes |
|---|---|---|---|---|
| 1 | llama.cpp | 8001 | text | OpenAI and Anthropic dialects; drop a `mmproj*.gguf` next to the model to see images |
| 2 | stable-diffusion.cpp | 8002 | image · interpolation | SD/SDXL/Flux/Qwen-Image; RIFE at `/media/v1/interpolate` |
| 3 | VoxCPM.cpp | 8003 | voice | 0.5B GGUF, single file, stateless, 3-second reference cloning |
| 4 | stable-diffusion.cpp | 8004 | video | Wan family, swaps weights with the image set |
| 5 | trellis.cpp | 8005 | 3D | TRELLIS.2, one image to GLB |

Image and video share one sd.cpp engine (mutually exclusive weight sets), so this is
**five inference engines, six capability endpoints**. Ports follow slots
(`text_slot / picture_slot / speech_slot / video_slot`), not hard-coded.

## Measured on hardware (PS5 Pro, firmware 13.42, 12 GB pool)

| Capability | Test | Result |
|---|---|---|
| Text | Qwen3 0.6B Q8_0 | 255.6 t/s generation |
| Image | 256×256 / 4 steps | 3.25 s |
| Video | 320×192 / 5 frames / 4 steps | 30.5 s |
| Voice | VoxCPM 0.5B q8_0, 10 consecutive sentences | 2.6–4.1 s/sentence, no degradation |
| 3D | 512 / decim=64 | 281.8 s, 10.5 MB GLB |
| Interpolation | RIFE 256×256 | 92 ms |

Voice was the focus of this round: the old Qwen3-TTS dropped from 5 s to 72–98 s per
sentence after the first one and only a process restart recovered it. VoxCPM stays at
~3 s across 10 consecutive sentences in the same process. The eboot is 305 MB with all
five engines linked in.

## API

```bash
# text (OpenAI compatible)
curl http://<IP>:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"local","messages":[{"role":"user","content":"hello"}]}'

# text (Anthropic compatible, Claude Code can talk to it directly)
curl http://<IP>:8001/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"model":"local","max_tokens":256,"messages":[{"role":"user","content":"hello"}]}'

# image
curl http://<IP>:8002/sdapi/v1/txt2img \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"a lighthouse at dusk","width":832,"height":480,"steps":20}'

# video (minimal: 5 frames)
curl http://<IP>:8004/sdapi/v1/txt2vid \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"a cat walking","width":320,"height":192,"frames":5,"steps":4}' \
  --output out.avi

# voice (reference: /data/PS5MM/voices/<name>.wav plus <name>.txt with its transcript)
curl http://<IP>:8003/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"input":"Hello from the console","voice":"taiyi.wav"}' \
  --output hello.wav

# image to 3D
curl http://<IP>:8005/v1/images/to3d \
  -H 'Content-Type: application/json' \
  -d '{"image":"<base64 png>","resolution":512,"decim":64}' \
  --output model.glb

# frame interpolation
curl http://<IP>:8002/media/v1/interpolate \
  -H 'Content-Type: application/json' \
  -d '{"frame0":"<base64>","frame1":"<base64>","timestep":0.5}'

# unload a model without restarting the app
curl -X POST http://<IP>:8002/unload
curl -X POST http://<IP>:8003/unload
```

## Quick start

Requires a PS5 that can run homebrew (firmware 13.x) with TacHen + ShadowMountPlus +
ftpsrv (port 2121) already injected.

1. Copy the whole `PPSA99577/` folder to `/data/homebrew/`
2. Trigger a scan: `POST http://<IP>:10101/api/v1/scan` with body `{"reset_attempts":true}`
3. The PS5MM icon appears on the home screen
4. Put models under `/data/PS5MM/models/` (text), `/data/PS5MM/sd/` (image/video),
   `/data/PS5MM/tts/` (voice), `/data/PS5MM/trellis/` (3D), or download them from
   HuggingFace inside the app (Models → Search)
5. For voice, also add a reference clip: `/data/PS5MM/voices/<name>.wav` plus `<name>.txt`
6. Set slots and model paths in Settings, then restart the app

## Known limits

- An 11–12 GB pool cannot hold three large models: text + voice (~2.1 GB) can run
  together; add any one of image/video/3D and you should stop
- One model at a time; call `POST /unload` before switching
- Voice output is 16 kHz (VoxCPM native rate)
- No authentication — never expose the ports to the public internet
- Requires a jailbroken console; the jailbreak does not persist across reboots
- A native title owns the display plane, so the PS button cannot reach the home screen
  (press Options twice to exit)

## License

GPL-3.0-or-later. Derived from [cobanov/PS5LM](https://github.com/cobanov/PS5LM) (GPL-3.0).

## Credits

llama.cpp (ggml / llama-server / mtmd), stable-diffusion.cpp, VoxCPM.cpp (bluryar) and
VoxCPM (OpenBMB), trellis.cpp (TRELLIS.2), ps5-homebrew-ui, Noto Sans SC,
PS5_Vulkan / PS5_Mesa (RADV), ps5-payload-sdk, TacHen, ShadowMountPlus, ftpsrv.
Without these projects, inference on a PS5 would still be "someone tried it once".
