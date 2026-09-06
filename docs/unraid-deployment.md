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
