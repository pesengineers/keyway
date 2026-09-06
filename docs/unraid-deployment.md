# Unraid 7.2 NVIDIA deployment

## SSH access to the host

Established 2026-09-06 for `pes-dev.pes.local` (`192.168.76.42`). Recorded here because it took several attempts and the failure modes are non-obvious.

### Where Unraid keeps root's keys

- Live file: `/root/.ssh/authorized_keys` (mode 600, directory 700).
- Persistent copy: `/boot/config/ssh/root/authorized_keys` on the flash drive. Unraid copies this into `/root/.ssh` at every boot; edit both or the change is lost on reboot.
- The web GUI field (Users > root > "SSH authorized keys") writes to the same place, but only after clicking **Change**. It also writes the key **without a trailing newline**, so a later `echo >> authorized_keys` glues the next key onto the same line and silently invalidates both. Always write with `printf '%s\n' ...` or check with `cat -A`.
- `sshd -T | grep -Ei "pubkey|passwordauth|permitroot|strictmodes"` shows the effective config. Defaults on this host: pubkey yes, password yes, PermitRootLogin yes, StrictModes yes.
- `/var/log/syslog | grep sshd` shows the exact fingerprint sshd rejected. That is the fastest way to tell "wrong key offered" from "key not authorized".

### Two keys are authorized

| Comment | Fingerprint | Where the private key lives |
|---|---|---|
| `pes-dev` | `SHA256:4u7fD7/hMUMz5yNOGh4L+ZcD1KVLDdvea+sDP76/Fg0` | 1Password SSH agent only |
| `me@dailen.net` | `SHA256:TBb1nZipGfzX/f+vneIpQWXiOfmW1PD7VpzY2b4B1Fg` | `~/.ssh/id_ed25519` on the workstation |

### Why both exist: 1Password agent limitations

The 1Password agent answers `ssh-add -L`, but `ssh` itself frequently reports `get_agent_identities: ssh_get_authentication_socket: No such file or directory` and never offers the `pes-dev` key. This happens for processes outside the interactive desktop session (automation tooling, agents, some terminals), and the `op` CLI hits the same wall (`cannot connect to 1Password app`). Exporting the key with `op read` produced PKCS#8 (`BEGIN PRIVATE KEY`), which Windows OpenSSH rejects for ed25519. The on-disk `id_ed25519` key was authorized so automation can log in regardless of agent state.

### Workstation config

`~/.ssh/config` has an alias so `ssh pes-dev` works from any shell:

```
Host pes-dev pes-dev.pes.local
   HostName pes-dev.pes.local
   User root
   IdentityFile ~/.ssh/id_ed25519
   IdentitiesOnly yes
```

### Adding another key safely (non-destructive)

Run from any shell that can already log in. Backs up first, appends only if absent, guarantees a newline:

```sh
KEY='ssh-ed25519 AAAA... comment'
for f in /root/.ssh/authorized_keys /boot/config/ssh/root/authorized_keys; do
  cp -p "$f" "$f.bak.$(date +%Y%m%d%H%M%S)"
  [ -n "$(tail -c1 "$f")" ] && echo >> "$f"
  grep -qF "$KEY" "$f" || echo "$KEY" >> "$f"
  chmod 600 "$f"
done
ssh-keygen -lf /root/.ssh/authorized_keys
```

Never paste multi-line commands into PowerShell to run remotely: here-strings emit CRLF and long lines wrap at the console width, both of which corrupted `authorized_keys` during setup. Keep remote commands on one line or run them from an interactive Unraid terminal.

### Verify

```
ssh -o BatchMode=yes pes-dev "uname -a"
```

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

Find stable GPU UUIDs with `nvidia-smi -L`. Select the Quadro P2000 by UUID rather than index; on `pes-dev` the P2000 is **index 1** (the P620 is index 0), so an index-based selection would pick the wrong card. Unraid's container template can set the NVIDIA runtime and `NVIDIA_VISIBLE_DEVICES` to that P2000 UUID. Equivalent CLI:

On `pes-dev` the UUIDs are:

| GPU | Index | VRAM | UUID |
|---|---|---|---|
| Quadro P2000 (target) | 1 | 5120 MiB | `GPU-a16c6467-c3d8-cf56-6944-a53de59dcd6b` |
| Quadro P620 (do not expose) | 0 | 2048 MiB | `GPU-588d1004-5969-03a5-2096-6fc9c4091e9a` |

```console
docker run --rm --gpus '"device=GPU-a16c6467-c3d8-cf56-6944-a53de59dcd6b"' \
  --env-file .env \
  -v /mnt/user/training-videos:/media:ro \
  -v /mnt/user/appdata/keyway/models:/models \
  -v /mnt/cache/keyway/tmp:/tmp/keyway \
  -v /mnt/user/appdata/keyway/output:/output \
  ghcr.io/pesengineers/keyway:latest
```

Leave `WHISPER_DEVICE=auto` and `WHISPER_COMPUTE_TYPE=auto`. The P2000 is a Pascal part (compute capability 6.1) and CTranslate2 reports only `float32`, `int8`, and `int8_float32` for it; there is no `float16`. `auto` therefore resolves to `cuda` / `float32` on this host (the app queries `ctranslate2.get_supported_compute_types("cuda")` and picks the first of `float16`, `int8_float16`, `float32`). The P620 should not be exposed to this container. GPU selection remains deployment configuration, not application logic.

The NVIDIA 580.159.03 driver is new enough for the container's CUDA 12 runtime. The image includes cuBLAS and cuDNN 9 required by current CTranslate2.

## Private n8n connection

Prefer a user-defined Docker network shared only with n8n. Do not publish port 8000. n8n can call `http://keyway:8000/v1/process/local` after both containers mount the same video path. If a host port is needed for diagnostics, bind only `127.0.0.1:8000`.

## Benchmark results (2026-09-06, Issue #3)

Host `pes-dev`, driver 580.159.03, image `keyway:local` built from commit `094867f`, model `small.en`, sample `2021-08-19 12.01 P_T (SCS).mp4` (3393.8 s of media, ~7 min of speech after VAD). Each run is a full `keyway process` including model load; "transcribe" is the faster-whisper phase only.

| Config | Device | Compute type | Transcribe (s) | RTF | Total (s) | Peak VRAM (MiB) | Notes |
|---|---|---|---|---|---|---|---|
| auto (cold) | cuda | float32 | 48.6 | 0.0143 | 56.7 | 1575 | includes first model download |
| float32 | cuda | float32 | 40.1 | 0.0118 | 47.8 | 1543 | |
| int8_float32 | cuda | int8_float32 | 36.4 | 0.0107 | 43.9 | 743 | |
| int8 | cuda | int8 | 36.6 | 0.0108 | 44.9 | 743 | |
| CPU baseline | cpu | int8 | 93.8 | 0.0276 | 102.8 | n/a | 2x E5-2670 v3, default threads |
| Dev laptop (reference) | cpu | int8 | 294.0 | 0.0866 | 306.7 | n/a | Core Ultra 7 155H, earlier session |

Transcript agreement: float32 vs int8 differed by a handful of punctuation/word tokens (1005 vs 1004 words); GPU vs CPU differed slightly more (135 word-level diff lines) but all were semantically equivalent.

**Recommendation:** keep `WHISPER_COMPUTE_TYPE=auto` (float32) for maximum fidelity; VRAM headroom is ample (1.5 of 5 GB). Set `WHISPER_COMPUTE_TYPE=int8_float32` if the P2000 must be shared with other workloads (halves VRAM, ~10 percent faster, negligible accuracy cost). The GPU is roughly 2.5x faster than the host's 24 Xeon cores and 8x faster than the dev laptop. Larger models (`medium.en`, ~1.5 GB fp32 weights) would fit in VRAM if accuracy needs increase.

## Local analysis with Ollama (installed 2026-09-06; fallback since ADR 006)

**Not the production path.** The Keyway template points at OpenRouter (runbook 1.8). Ollama stays installed, GPU-pinned, and ready; switch three variables to use it offline. Models present: `llama3.2:3b`, `llama3.1:8b`.

Keyway is one container. Analysis runs in a second, separately managed container installed from **Community Apps** (`ollama/ollama`, official image) so transcripts never leave the host. Both containers share the P2000 sequentially: Whisper releases VRAM when a job ends and Ollama unloads its model after `OLLAMA_KEEP_ALIVE`.

Template values used on `pes-dev` (Community Apps > Ollama):

| Setting | Value | Reason |
|---|---|---|
| Name | `ollama` | Keyway reaches it as `http://ollama:11434` |
| Network Type | `keyway-net` (custom bridge, created with `docker network create keyway-net`) | private to Keyway and n8n |
| `NVIDIA_VISIBLE_DEVICES` | `GPU-a16c6467-c3d8-cf56-6944-a53de59dcd6b` | P2000 only |
| `NVIDIA_DRIVER_CAPABILITIES` | `compute,utility` | |
| Extra Parameters (Advanced View) | `--runtime=nvidia` | required for the NVIDIA variables to take effect |
| `OLLAMA_KEEP_ALIVE` | `2m` | frees VRAM promptly between jobs |
| Appdata | `/mnt/user/appdata/ollama` → `/root/.ollama` | model store (~2 GB for llama3.2:3b) |
| Port | remove the "API Interface Port" row so Ollama is reachable only from `keyway-net` (done on `pes-dev`). Keep `OLLAMA_HOST=0.0.0.0:11434`; `127.0.0.1` would block other containers |

Keyway environment for this backend:

```dotenv
ANALYSIS_BACKEND=ollama
ANALYSIS_BASE_URL=http://ollama:11434
ANALYSIS_MODEL=llama3.2:3b
ANALYSIS_TIMEOUT_SECONDS=600
```

Pull the model once from the host: `docker exec ollama ollama pull llama3.2:3b`.

### Validated result on the sample video

End-to-end on the P2000 with `llama3.2:3b`: 41.1 s transcription, 13.0 s analysis, **62.3 s total** for 56.5 min of media. Peak VRAM 4.1 GB with both Whisper (float32) and the 3B model resident, so the 5 GB card has headroom but not enough for a 7B/8B model at the same time. The model produced a correct `safe` classification with a grounded reason and a usable title and synopsis for a Revit/Dynamo training session.

If a larger model is wanted later: set `WHISPER_COMPUTE_TYPE=int8_float32` (Whisper drops to ~0.75 GB) and keep `OLLAMA_KEEP_ALIVE` short, or run Ollama on CPU.

### Ollama-specific gotcha

Ollama compiles the JSON schema in `format` into a llama.cpp grammar. `minLength`/`maxLength` on strings expand to one grammar rule per character and fail with HTTP 400 `failed to parse grammar`. Keyway therefore sends Ollama a schema without length bounds (`_OLLAMA_SCHEMA` in `app/analysis.py`); Pydantic still enforces every bound on the response.

## Validation after storm recovery

1. Confirm `/health` and `/ready` return 200.
2. Process one known short file and confirm `transcription.device` is `cuda`.
3. Benchmark the representative video on the P2000 and record processing time, realtime factor, peak VRAM, driver, and image digest. Done 2026-09-06; see table above.
4. Confirm temporary job directories disappear after both successful and deliberately failed processing. Verified: `/mnt/cache/keyway/tmp/keyway/` was empty after all five runs.
