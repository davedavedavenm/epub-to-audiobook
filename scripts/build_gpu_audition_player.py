"""
build_gpu_audition_player.py — Generates the interactive inline audio player for top-tier GPU candidates.

Embeds base64-encoded audio into gpu_top_tier_player.html so that the user can listen directly
within the chat UI or via direct file:/// links.
"""

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "evaluations" / "new-engines" / "output"
PLAYER_HTML = Path(r"C:\Users\Dave\.gemini\antigravity\brain\80b2c9a1-325c-4570-bb9b-ec2788501a75\gpu_top_tier_player.html")

def to_b64(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")

def build_player():
    candidates = [
        {
            "id": "qwen3_aiden_mastered",
            "badge": "NEW WINNER: Qwen3-TTS 1.7B Aiden (Mastered)",
            "sub": "Modal L4 GPU • Broadcast Mastered • 192k MP3",
            "file": OUT_DIR / "breakneck_ch1_qwen3_aiden_mastered.mp3",
            "desc": "<strong>Voice:</strong> Studio speaker <code>aiden</code> with instruction steering.<br/><strong>Mastering:</strong> +2.2 dB Warmth EQ, -3.5 dB De-Esser, EBU R128 (-20 LUFS).",
            "theme": "indigo",
            "icon": "🎙️"
        },
        {
            "id": "qwen3_aiden_raw",
            "badge": "Qwen3-TTS 1.7B Aiden (Pure Raw)",
            "sub": "Modal L4 GPU • Direct Model Output • 192k MP3",
            "file": OUT_DIR / "breakneck_ch1_qwen3_aiden_raw.mp3",
            "desc": "Pure raw audio directly from Qwen3-TTS without any EQ, de-essing, or post-processing.",
            "theme": "indigo",
            "icon": "🔊"
        },
        {
            "id": "breeze_arthur_mastered",
            "badge": "NEW: Breeze TTS 2 (3.5B) Arthur (Mastered)",
            "sub": "Modal L4 GPU • Cloned Arthur + Voice Direction • 192k MP3",
            "file": OUT_DIR / "breakneck_ch1_breeze_arthur_modal_mastered.mp3",
            "desc": "<strong>Voice:</strong> British male narrator Arthur (<code>uk_male_minter.wav</code>) steered with Voice Direction.<br/><strong>Mastering:</strong> Warmth EQ + De-Esser + EBU R128 (-20 LUFS).",
            "theme": "cyan",
            "icon": "✨"
        },
        {
            "id": "breeze_karen_mastered",
            "badge": "NEW UK FEMALE: Breeze TTS 2 Karen Savage (Mastered)",
            "sub": "Modal L4 GPU • Cloned Karen Savage (Jane Austen Narrator) • 192k MP3",
            "file": OUT_DIR / "breakneck_ch1_breeze_karen_modal_mastered.mp3",
            "desc": "<strong>Voice:</strong> Articulate, expressive British female narrator Karen Savage (<code>karen_savage.wav</code>) with pristine wideband studio clarity.<br/><strong>Mastering:</strong> Warmth EQ + De-Esser + EBU R128 (-20 LUFS).",
            "theme": "cyan",
            "icon": "👑"
        },
        {
            "id": "breeze_tadhg_clean_mastered",
            "badge": "NEW IRISH MALE: Breeze TTS 2 Tadhg Hynes (Studio Restored)",
            "sub": "Modal L4 GPU • Denoised Reference + Air & Presence Mastering • 192k MP3",
            "file": OUT_DIR / "breakneck_ch1_breeze_tadhg_clean_modal_mastered.mp3",
            "desc": "<strong>Restoration:</strong> Spectral denoising (<code>afftdn</code>) + 600Hz boxy resonance cut on reference + Air EQ mastering to eliminate telephone effect.<br/><strong>Prosody:</strong> Inquisitive uptalk on rhetorical questions.",
            "theme": "cyan",
            "icon": "🍀"
        },
        {
            "id": "breeze_adrian_mastered",
            "badge": "NEW UK MALE: Breeze TTS 2 Adrian Praetzellis (Mastered)",
            "sub": "Modal L4 GPU • Cloned British Conversational Scholar • 192k MP3",
            "file": OUT_DIR / "breakneck_ch1_breeze_adrian_modal_mastered.mp3",
            "desc": "<strong>Voice:</strong> Warm, scholarly British male narrator Adrian Praetzellis (<code>adrian_praetzellis.wav</code>) with high presence and thoughtful cadence.<br/><strong>Mastering:</strong> Warmth EQ + De-Esser + EBU R128 (-20 LUFS).",
            "theme": "cyan",
            "icon": "🎓"
        },
        {
            "id": "breeze_beatrice_mastered",
            "badge": "Breeze TTS 2 (3.5B) Beatrice (Mastered)",
            "sub": "Modal L4 GPU • Cloned Beatrice + Voice Direction • 192k MP3",
            "file": OUT_DIR / "breakneck_ch1_breeze_beatrice_modal_mastered.mp3",
            "desc": "<strong>Voice:</strong> British female narrator Beatrice (<code>uk_female_samuel.wav</code>) steered with Voice Direction.<br/><strong>Mastering:</strong> Warmth EQ + De-Esser + EBU R128 (-20 LUFS).",
            "theme": "cyan",
            "icon": "✨"
        },
        {
            "id": "breeze_tadhg_mastered",
            "badge": "Breeze TTS 2 (3.5B) Tadhg Hynes (Original LibriVox - Phone Sound)",
            "sub": "Modal L4 GPU • Cloned Original Unfiltered LibriVox WAV • 192k MP3",
            "file": OUT_DIR / "breakneck_ch1_breeze_tadhg_modal_mastered.mp3",
            "desc": "<strong>Comparison:</strong> The original un-denoised reference showing the boxy telephone artifact from LibriVox mic frequency response.",
            "theme": "cyan",
            "icon": "📞"
        },
        {
            "id": "breeze_liam_au_mastered",
            "badge": "NEW: Breeze TTS 2 (3.5B) Liam (Australian Male)",
            "sub": "Modal L4 GPU • Cloned Australian Speaker (VCTK p374) • 192k MP3",
            "file": OUT_DIR / "breakneck_ch1_breeze_liam_au_modal_mastered.mp3",
            "desc": "<strong>Voice:</strong> Authentic Australian male speaker (<code>vctk_australian_m_p374.wav</code>) steered with natural, thoughtful Voice Direction.<br/><strong>Mastering:</strong> Warmth EQ + De-Esser + EBU R128 (-20 LUFS).",
            "theme": "cyan",
            "icon": "🦘"
        },
        {
            "id": "breeze_yearsley_mastered",
            "badge": "NEW: Breeze TTS 2 (3.5B) Yearsley (UK Male Baritone)",
            "sub": "Modal L4 GPU • Cloned British Baritone • 192k MP3",
            "file": OUT_DIR / "breakneck_ch1_breeze_yearsley_modal_mastered.mp3",
            "desc": "<strong>Voice:</strong> Deep, distinguished British gentleman narrator Yearsley (<code>uk_male_yearsley.wav</code>) steered with authoritative cadence.<br/><strong>Mastering:</strong> Warmth EQ + De-Esser + EBU R128 (-20 LUFS).",
            "theme": "cyan",
            "icon": "🎩"
        },
        {
            "id": "breeze_arthur_raw",
            "badge": "Breeze TTS 2 (3.5B) Arthur (Pure Raw)",
            "sub": "Modal L4 GPU • Direct Model Output • 192k MP3",
            "file": OUT_DIR / "breakneck_ch1_breeze_arthur_modal_raw.mp3",
            "desc": "Pure raw audio from Breeze TTS 2 Voice Direction without mastering.",
            "theme": "cyan",
            "icon": "🔊"
        },
        {
            "id": "kokoro_warm_mastered",
            "badge": "Kokoro Production (V2 - Unified Author Thoughts & Uber Fix)",
            "sub": "Modal T4 GPU • am_michael + am_fenrir • Broadcast Mastered",
            "file": OUT_DIR / "breakneck_ch1_warm_mastered.mp3",
            "desc": "<strong>V2 Fixes:</strong> Author thought unified in main narrator <code>am_michael</code>; 'Uber' normalized to 'Oo-ber'; <code>am_fenrir</code> strictly for title & thesis.",
            "theme": "amber",
            "icon": "🏆"
        }
    ]

    cards_html = []
    for c in candidates:
        fpath = c["file"]
        if not fpath.exists():
            continue
        b64_audio = to_b64(fpath)
        size_kb = round(fpath.stat().st_size / 1024, 1)
        theme = c["theme"]
        
        if theme == "indigo":
            border_cls = "border-indigo-500/40 bg-gradient-to-br from-indigo-500/10 via-indigo-500/5 to-transparent"
            text_cls = "text-indigo-600 dark:text-indigo-400"
            badge_cls = "bg-indigo-500/20 text-indigo-700 dark:text-indigo-300"
        elif theme == "cyan":
            border_cls = "border-cyan-500/40 bg-gradient-to-br from-cyan-500/10 via-cyan-500/5 to-transparent"
            text_cls = "text-cyan-600 dark:text-cyan-400"
            badge_cls = "bg-cyan-500/20 text-cyan-700 dark:text-cyan-300"
        else: # amber
            border_cls = "border-amber-500/40 bg-gradient-to-br from-amber-500/10 via-amber-500/5 to-transparent"
            text_cls = "text-amber-600 dark:text-amber-400"
            badge_cls = "bg-amber-500/20 text-amber-700 dark:text-amber-300"

        file_url = f"file:///{str(fpath).replace(chr(92), '/')}"

        card = f"""
    <!-- {c['badge']} -->
    <div class="p-3.5 rounded-xl border-2 {border_cls} space-y-2">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <span class="text-base">{c['icon']}</span>
          <span class="font-bold text-xs uppercase tracking-wider {text_cls}">{c['badge']}</span>
        </div>
        <span class="text-[10px] font-mono font-semibold px-2 py-0.5 rounded {badge_cls}">{size_kb} KB • {c['sub'].split('•')[0].strip()}</span>
      </div>
      <p class="text-xs text-[var(--foreground)] leading-relaxed">
        {c['desc']}
      </p>
      <audio controls preload="metadata" class="w-full h-8 pt-1" src="data:audio/mp3;base64,{b64_audio}"></audio>
      <div class="text-[10px] text-[var(--muted-foreground)] flex justify-between pt-1 border-t border-[var(--border)]/40">
        <span>Path: <a href="{file_url}" class="underline hover:text-[var(--foreground)] font-mono">{fpath.name}</a></span>
        <span class="font-semibold">{c['sub']}</span>
      </div>
    </div>"""
        cards_html.append(card)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
</head>
<body class="bg-transparent text-[var(--foreground)] antialiased p-3 font-sans">
  <div class="bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] rounded-2xl p-5 shadow-lg space-y-5 max-w-xl mx-auto">
    
    <div class="border-b border-[var(--border)] pb-3 flex items-center justify-between">
      <div>
        <h2 class="text-base font-bold tracking-tight text-[var(--foreground)]">Top-Tier Modal GPU Audiobook Auditions</h2>
        <p class="text-xs text-[var(--muted-foreground)]">Breakneck Ch.1 (Full Excerpt) • Modal Cloud GPU Production Runs</p>
      </div>
      <span class="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold border border-emerald-500/20">Modal GPU Live</span>
    </div>

    {''.join(cards_html)}

    <div class="text-center pt-2 text-[10px] text-[var(--muted-foreground)]">
      Synthesized on Modal Cloud GPUs (Nvidia L4 / T4) • Broadcast Mastered via FFmpeg (-20 LUFS)
    </div>
  </div>
</body>
</html>
"""
    PLAYER_HTML.write_text(html_content, encoding="utf-8")
    print(f"Audition player built successfully: {PLAYER_HTML} ({len(html_content):,} bytes)")

if __name__ == "__main__":
    build_player()
