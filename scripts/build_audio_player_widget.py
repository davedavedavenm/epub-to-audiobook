from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "evaluations" / "new-engines" / "output"
KOKORO_DIR = OUTPUT_DIR / "kokoro_variations"
ARTIFACT_DIR = Path(r"C:\Users\Dave\.gemini\antigravity\brain\e7f9f1a0-6096-4e36-a931-750eafb29d67")
TARGET_HTML = ARTIFACT_DIR / "candidate_audio_player.html"

def to_b64(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("ascii")

def main():
    # 1. Free CPU Candidates (Breakneck Ch.1 456 words)
    pocket_peter_b64 = to_b64(OUTPUT_DIR / "pocket_breakneck_ch1_peter.mp3")
    kitten_rosie_b64 = to_b64(OUTPUT_DIR / "kitten_breakneck_ch1_rosie.mp3")
    kitten_jasper_b64 = to_b64(OUTPUT_DIR / "kitten_breakneck_ch1_jasper.mp3")
    neutts_jo_b64 = to_b64(OUTPUT_DIR / "neutts_breakneck_ch1_jo.mp3")
    neutts_jo_v2_b64 = to_b64(OUTPUT_DIR / "neutts_breakneck_ch1_jo_v2.mp3")

    # 2. GPU Candidates (Breakneck Ch.1 456 words)
    breeze_design_b64 = to_b64(OUTPUT_DIR / "breeze_voice_design_uk_male.mp3")
    breeze_arthur_b64 = to_b64(OUTPUT_DIR / "breeze_voice_direction_arthur.mp3")
    qwen3_arthur_b64 = to_b64(OUTPUT_DIR / "qwen3_breakneck_ch1_arthur.mp3")
    
    # 3. Kokoro variations
    kokoro_blend1_b64 = to_b64(KOKORO_DIR / "kokoro_blend_george_lewis.mp3")
    kokoro_blend2_b64 = to_b64(KOKORO_DIR / "kokoro_blend_lewis_george.mp3")
    kokoro_george_rel_b64 = to_b64(KOKORO_DIR / "kokoro_george_relaxed.mp3")
    kokoro_fable_b64 = to_b64(KOKORO_DIR / "kokoro_fable_storyteller.mp3")

    # 4. Qwen3 CustomVoice Previews
    QWEN3_DIR = OUTPUT_DIR / "qwen3_previews" / "out"
    qwen3_ryan_b64 = to_b64(QWEN3_DIR / "qwen3_customvoice_ryan.mp3")
    qwen3_aiden_b64 = to_b64(QWEN3_DIR / "qwen3_customvoice_aiden.mp3")
    qwen3_uncle_fu_b64 = to_b64(QWEN3_DIR / "qwen3_customvoice_uncle_fu.mp3")
    qwen3_vivian_b64 = to_b64(QWEN3_DIR / "qwen3_customvoice_vivian.mp3")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
</head>
<body class="bg-transparent text-[var(--foreground)] antialiased p-2">
  <div class="bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] rounded-xl p-4 shadow-sm space-y-4 max-w-xl mx-auto">
    <div class="border-b border-[var(--border)] pb-2 flex items-center justify-between">
      <div>
        <h3 class="font-semibold text-base">Breakneck Ch.1 Audition Suite</h3>
        <p class="text-xs text-[var(--muted-foreground)]">Compare Free CPU Candidates vs GPU Front-Runners (456 Words)</p>
      </div>
      <span class="text-xs px-2 py-0.5 rounded bg-[var(--accent)] text-[var(--accent-foreground)] font-mono">Verified Audio</span>
    </div>

    <!-- Section: Free CPU Candidates -->
    <div class="space-y-2">
      <div class="flex items-center justify-between">
        <h4 class="text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">⚡ Free Local CPU Candidates (Breakneck Ch. 1)</h4>
        <span class="text-[10px] text-[var(--muted-foreground)] font-mono">Normalized • Natural Pacing</span>
      </div>

      <!-- Pocket TTS: Peter Yearsley -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">🎙️ Pocket TTS 2.1 — Peter Yearsley</span>
          <span class="text-[var(--muted-foreground)] font-mono">2:36 • CPU RTF 0.53x</span>
        </div>
        <p class="text-[10px] text-[var(--muted-foreground)]">Fast streaming Kyutai transformer. Brisk, articulate British public-domain narrator.</p>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{pocket_peter_b64}"></audio>
      </div>

      <!-- KittenTTS: Rosie -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">🎙️ KittenTTS 0.8.1 — Rosie</span>
          <span class="text-[var(--muted-foreground)] font-mono">3:19 • CPU RTF 1.02x</span>
        </div>
        <p class="text-[10px] text-[var(--muted-foreground)]">StyleTTS2 mini. Warm, measured, natural cadence British female narrator.</p>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{kitten_rosie_b64}"></audio>
      </div>

      <!-- KittenTTS: Jasper -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">🎙️ KittenTTS 0.8.1 — Jasper</span>
          <span class="text-[var(--muted-foreground)] font-mono">3:02 • CPU RTF 1.07x</span>
        </div>
        <p class="text-[10px] text-[var(--muted-foreground)]">StyleTTS2 mini. Clear, engaging British male voice (scratchy start mitigated).</p>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{kitten_jasper_b64}"></audio>
      </div>

      <!-- NeuTTS Air: Jo v2 Repaired -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border-2 border-emerald-500/30">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">✨ 🎙️ NeuTTS Air 1.4.1 — Jo (v2 Repaired)</span>
          <span class="text-emerald-500 font-mono font-semibold">3:02 • CPU RTF 2.25x</span>
        </div>
        <p class="text-[10px] text-[var(--muted-foreground)]">Fixed: phoneme patch replaces 'ðɪʲ' with neutral 'ðə' (curing "the 'e' airport" / "the 'e' order") + sentence packing stabilizes pitch & tone.</p>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{neutts_jo_v2_b64}"></audio>
      </div>

      <!-- NeuTTS Air: Jo v1 Baseline -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)] opacity-80">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">🎙️ NeuTTS Air 1.4.1 — Jo (v1 Baseline)</span>
          <span class="text-[var(--muted-foreground)] font-mono">3:12 • CPU RTF 5.90x</span>
        </div>
        <p class="text-[10px] text-[var(--muted-foreground)]">Initial baseline: isolated single sentences (contained "the 'e' airport" palatal glide glitch).</p>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{neutts_jo_b64}"></audio>
      </div>
    </div>

    <!-- Section: GPU 2-Page Excerpts -->
    <div class="space-y-2 pt-2 border-t border-[var(--border)]">
      <h4 class="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">GPU Long-Form Excerpts (456 Words)</h4>
      
      <!-- 1. Breeze Voice Design -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">🌟 Breeze TTS 2 — Voice Design (UK Male Narrator)</span>
          <span class="text-[var(--muted-foreground)] font-mono">3:04 • T4 GPU • 5.6% WER</span>
        </div>
        <p class="text-[10px] text-[var(--muted-foreground)]">Reference-free natural language voice design (no Arthur cloning)</p>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{breeze_design_b64}"></audio>
      </div>

      <!-- 2. Breeze Voice Direction -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">Breeze TTS 2 — Voice Direction (Arthur Clone)</span>
          <span class="text-[var(--muted-foreground)] font-mono">3:20 • T4 GPU • 6.0% WER</span>
        </div>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{breeze_arthur_b64}"></audio>
      </div>

      <!-- 3. Qwen3-TTS Arthur -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">Qwen3-TTS 1.7B Base (Arthur Clone)</span>
          <span class="text-[var(--muted-foreground)] font-mono">2:54 • T4 GPU • 6.0% WER</span>
        </div>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{qwen3_arthur_b64}"></audio>
      </div>
    </div>

    <!-- Section: Kokoro Best-Practice Voice Blends & Cadence -->
    <div class="space-y-2 pt-2 border-t border-[var(--border)]">
      <h4 class="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">Kokoro CPU Best-Practice Blends (Opening Excerpt)</h4>
      
      <!-- Blend 1 -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">Blend: 67% George + 33% Lewis (0.95x speed)</span>
          <span class="text-[var(--muted-foreground)] font-mono">Smoother prosody</span>
        </div>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{kokoro_blend1_b64}"></audio>
      </div>

      <!-- Blend 2 -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">Blend: 67% Lewis + 33% George (0.95x speed)</span>
          <span class="text-[var(--muted-foreground)] font-mono">Warmer British timbre</span>
        </div>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{kokoro_blend2_b64}"></audio>
      </div>

      <!-- George Relaxed -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">George Alone (Relaxed 0.92x speed)</span>
          <span class="text-[var(--muted-foreground)] font-mono">Unrushed pacing</span>
        </div>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{kokoro_george_rel_b64}"></audio>
      </div>

      <!-- Fable Storyteller -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">Fable (British Narrative Storyteller 0.92x)</span>
          <span class="text-[var(--muted-foreground)] font-mono">Expressive baseline</span>
        </div>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{kokoro_fable_b64}"></audio>
      </div>
    </div>

    <!-- Section: Qwen3-TTS 1.7B CustomVoice Studio Narrators -->
    <div class="space-y-2 pt-2 border-t border-[var(--border)]">
      <div class="flex items-center justify-between">
        <h4 class="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">Qwen3-TTS 1.7B CustomVoice Studio Narrators</h4>
        <span class="text-[10px] text-[var(--muted-foreground)] font-mono">Instruction-Steered</span>
      </div>

      <!-- Ryan -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">🎙️ Ryan (Dynamic Studio Narrator)</span>
          <span class="text-[var(--muted-foreground)] font-mono">Qwen3 CustomVoice</span>
        </div>
        <p class="text-[10px] text-[var(--muted-foreground)]">Prompt instruction: Read in a calm, authoritative, engaging non-fiction audiobook narrator style</p>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{qwen3_ryan_b64}"></audio>
      </div>

      <!-- Aiden -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">🎙️ Aiden (Clear Male Narrator)</span>
          <span class="text-[var(--muted-foreground)] font-mono">Qwen3 CustomVoice</span>
        </div>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{qwen3_aiden_b64}"></audio>
      </div>

      <!-- Uncle Fu -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">🎙️ Uncle Fu (Mature Resonant Male)</span>
          <span class="text-[var(--muted-foreground)] font-mono">Qwen3 CustomVoice</span>
        </div>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{qwen3_uncle_fu_b64}"></audio>
      </div>

      <!-- Vivian -->
      <div class="space-y-1 p-2 rounded-lg bg-[var(--background)] border border-[var(--border)]">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-[var(--foreground)]">🎙️ Vivian (Articulate Female Narrator)</span>
          <span class="text-[var(--muted-foreground)] font-mono">Qwen3 CustomVoice</span>
        </div>
        <audio controls preload="metadata" class="w-full h-8" src="data:audio/mp3;base64,{qwen3_vivian_b64}"></audio>
      </div>
    </div>
  </div>
</body>
</html>
"""
    TARGET_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote updated player widget to {TARGET_HTML} ({len(html):,} bytes)")

if __name__ == "__main__":
    main()
