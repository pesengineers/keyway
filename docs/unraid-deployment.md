# Unraid 7.2 NVIDIA deployment

## Host paths

Create writable directories owned by the container user (`10001:10001`) or set equivalent ACLs:

- `/mnt/user/appdata/keyway/models` → `/models`
- `/mnt/cache/keyway/tmp` → `/tmp/keyway`
- a durable artifact directory → `/output`
- the approved video library → `/media` read-only

Keep models and temporary WAV files out of the container layer. Model files download on first use and persist in `/models`.

## Configuration

Use these initial values:

```dotenv
WHISPER_MODEL=small.en
WHISPER_DEVICE=auto
WHISPER_COMPUTE_TYPE=auto
MODEL_CACHE_DIR=/models
TEMP_DIR=/tmp/keyway
OUTPUT_DIR=/output
LOCAL_SOURCE_ROOTS=["/media"]
MAX_CONCURRENT_JOBS=1
```

Inject `ANALYSIS_API_KEY` as a secret. Do not store it in the image or repository.

## CPU run

The CUDA runtime image also supports CPU execution without exposing a GPU:

```console
docker run --rm \
  --env-file .env \
  -e WHISPER_DEVICE=cpu \
  -e WHISPER_COMPUTE_TYPE=int8 \
  -v /path/to/media:/media:ro \
  -v /path/to/models:/models \
  -v /path/to/output:/output \
  -v /path/to/tmp:/tmp/keyway \
  -p 127.0.0.1:8000:8000 \
  ghcr.io/pesengineers/keyway:latest
```

## NVIDIA run

Find stable GPU UUIDs with `nvidia-smi -L`. Select the Quadro P2000 by UUID rather than assuming index 0; indices can change across boots. Unraid's container template can set the NVIDIA runtime and `NVIDIA_VISIBLE_DEVICES` to that P2000 UUID. Equivalent CLI:

```console
docker run --rm --gpus '"device=GPU-REPLACE_WITH_P2000_UUID"' \
  --env-file .env \
  -v /mnt/user/training-videos:/media:ro \
  -v /mnt/user/appdata/keyway/models:/models \
  -v /mnt/cache/keyway/tmp:/tmp/keyway \
  -v /mnt/user/appdata/keyway/output:/output \
  ghcr.io/pesengineers/keyway:latest
```

Leave `WHISPER_DEVICE=auto` and `WHISPER_COMPUTE_TYPE=auto`; the expected selected values are `cuda` and `float16`. The P620 should not be exposed to this container. GPU selection remains deployment configuration, not application logic.

The NVIDIA 580.159.03 driver is new enough for the container's CUDA 12 runtime. The image includes cuBLAS and cuDNN 9 required by current CTranslate2.

## Private n8n connection

Prefer a user-defined Docker network shared only with n8n. Do not publish port 8000. n8n can call `http://keyway:8000/v1/process/local` after both containers mount the same video path. If a host port is needed for diagnostics, bind only `127.0.0.1:8000`.

## Validation after storm recovery

1. Confirm `/health` and `/ready` return 200.
2. Process one known short file and confirm `transcription.device` is `cuda`.
3. Benchmark the representative video on the P2000 and record processing time, realtime factor, peak VRAM, driver, and image digest.
4. Confirm temporary job directories disappear after both successful and deliberately failed processing.
