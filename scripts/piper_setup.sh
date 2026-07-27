set -eu
cd /home/dave/ai/lab/stacks/epub-to-audiobook

mkdir -p piper/voices piper/config

echo "=== preserve the image's built-in models (the bind mount will shadow them) ==="
for m in en_US-libritts_r-medium en_GB-northern_english_male-medium; do
  for ext in onnx onnx.json; do
    if [ ! -f "piper/voices/$m.$ext" ]; then
      docker cp "piper-tts:/app/voices/$m.$ext" "piper/voices/$m.$ext" 2>/dev/null \
        && echo "  copied $m.$ext" || echo "  (no $m.$ext in image)"
    fi
  done
done

echo
echo "=== download the native VCTK model ==="
BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/vctk/medium
for f in en_GB-vctk-medium.onnx en_GB-vctk-medium.onnx.json; do
  if [ ! -s "piper/voices/$f" ]; then
    curl -fsSL --max-time 600 "$BASE/$f" -o "piper/voices/$f" && echo "  got $f ($(stat -c%s piper/voices/$f) bytes)"
  else
    echo "  already have $f"
  fi
done

cp piper/voice_to_speaker.yaml piper/config/voice_to_speaker.yaml
ls -la piper/voices/ piper/config/
