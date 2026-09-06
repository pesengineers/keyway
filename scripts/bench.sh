#!/bin/bash
# End-to-end benchmark of the Keyway image on the Unraid host.
#
# Runs `keyway process` in a throwaway container against one video, using the
# live Ollama container for analysis, and samples GPU memory while it runs.
# Safe to run on production: it only writes under $BENCH_DIR and the shared
# model cache, and removes its own container.
#
# Usage (on pes-dev, as root):
#   scripts/bench.sh <label> <video-path> [WHISPER_DEVICE] [WHISPER_COMPUTE_TYPE]
# Example:
#   scripts/bench.sh gpu-auto "/mnt/cache/keyway/bench/sample.mp4"
#   scripts/bench.sh cpu-i8  "/mnt/cache/keyway/bench/sample.mp4" cpu int8
set -euo pipefail

label=${1:?label}; video=${2:?video path}; dev=${3:-auto}; ct=${4:-auto}
GPU=${KEYWAY_GPU_UUID:-GPU-a16c6467-c3d8-cf56-6944-a53de59dcd6b}
IMAGE=${KEYWAY_IMAGE:-ghcr.io/pesengineers/keyway:latest}
NET=${KEYWAY_NET:-keyway-net}
MODEL=${ANALYSIS_MODEL:-llama3.2:3b}
BENCH_DIR=${BENCH_DIR:-/mnt/cache/keyway/bench}

video_dir=$(dirname "$video"); video_name=$(basename "$video")
out="$BENCH_DIR/out/$label"
rm -rf "$out"; mkdir -p "$out"; chown 10001:10001 "$out"

nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv,noheader -l 1 -i "$GPU" > "$out/gpu.csv" &
smi=$!
trap 'kill $smi 2>/dev/null || true' EXIT

gpu_args=()
[ "$dev" != "cpu" ] && gpu_args=(--gpus "\"device=$GPU\"")

start=$(date +%s)
eval docker run --rm --name "keyway-bench-$label" --network "$NET" "${gpu_args[@]}" \
  -e ANALYSIS_BACKEND=ollama -e ANALYSIS_BASE_URL=http://ollama:11434 -e ANALYSIS_MODEL="$MODEL" \
  -e ANALYSIS_TIMEOUT_SECONDS=600 -e WHISPER_DEVICE="$dev" -e WHISPER_COMPUTE_TYPE="$ct" \
  -v "\"$video_dir\":/media:ro" \
  -v /mnt/user/appdata/keyway/models:/models \
  -v /mnt/cache/keyway/tmp:/tmp/keyway \
  -v "\"$out\":/output" \
  "$IMAGE" keyway process "\"/media/$video_name\"" --output /output \
  > "$out/run.log" 2>&1 || echo "EXIT $?" >> "$out/run.log"
end=$(date +%s)
kill $smi 2>/dev/null || true; wait $smi 2>/dev/null || true

echo "== $label wall=$((end - start))s"
grep -oE '"(success|device|compute_type|duration_seconds|processing_seconds|realtime_factor|total_processing_seconds|sensitivity)": [^,]+' "$out/result.json" | tr '\n' ' '; echo
awk -F', ' '{gsub(/ MiB/,"",$2); if($2+0>m)m=$2+0} END{print "peak_vram_mib=" m}' "$out/gpu.csv"
grep -E "ERROR|EXIT|Traceback" "$out/run.log" | head -n 5 || true
echo "artifacts: $out"
