#!/bin/bash
# Convert EPUB to audiobook using Kokoro TTS
# Usage: ./convert.sh <epub_file> <output_dir> [voice]
#
# Available voices (query http://localhost:8880/v1/audio/voices for full list):
#   af_bella, af_sky   - American female
#   am_adam            - American male
#   bf_emma            - British female
#   bm_george          - British male
# Voice mixing: af_bella+af_sky or weighted af_bella(2)+af_sky(1)

set -e

EPUB_FILE="$1"
OUTPUT_DIR="$2"
VOICE="${3:-af_bella}"

if [ -z "$EPUB_FILE" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "Usage: $0 <epub_file> <output_dir> [voice]"
    echo "Example: $0 /path/to/book.epub /path/to/output af_bella"
    exit 1
fi

if [ ! -f "$EPUB_FILE" ]; then
    echo "Error: EPUB file not found: $EPUB_FILE"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "Converting: $EPUB_FILE"
echo "Output: $OUTPUT_DIR"
echo "Voice: $VOICE"
echo ""

docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  -e OPENAI_API_KEY=not-needed \
  -e OPENAI_API_BASE=http://host.docker.internal:8880/v1 \
  -v "$EPUB_FILE":/input/book.epub:ro \
  -v "$OUTPUT_DIR":/output \
  ghcr.io/p0n1/epub_to_audiobook:latest \
  /input/book.epub /output --tts openai --voice_name "$VOICE" --model_name kokoro --no_prompt

echo ""
echo "Conversion complete! Output in: $OUTPUT_DIR"
