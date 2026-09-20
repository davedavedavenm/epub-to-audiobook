import base64
from pathlib import Path

brain_dir = Path(r"C:\Users\Dave\.gemini\antigravity\brain\80b2c9a1-325c-4570-bb9b-ec2788501a75")
root = Path(__file__).resolve().parents[1]

turbo_mp3 = root / "output" / "cillian_chatterbox.mp3"
nano_mp3 = root / "output" / "cillian_nano_test.mp3"

turbo_b64 = base64.b64encode(turbo_mp3.read_bytes()).decode("ascii")
nano_b64 = base64.b64encode(nano_mp3.read_bytes()).decode("ascii")

# Also copy to brain dir
(brain_dir / "cillian_chatterbox.mp3").write_bytes(turbo_mp3.read_bytes())
(brain_dir / "cillian_nano_test.mp3").write_bytes(nano_mp3.read_bytes())

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Cillian Murphy Lightweight Local Clone Audition</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    max-width: 800px;
    margin: 40px auto;
    padding: 24px;
    line-height: 1.6;
  }}
  h1 {{ color: #38bdf8; font-size: 24px; margin-bottom: 8px; }}
  .subtitle {{ color: #94a3b8; font-size: 14px; margin-bottom: 24px; }}
  .text-box {{
    background: #1e293b;
    border-left: 4px solid #38bdf8;
    padding: 16px;
    border-radius: 6px;
    margin-bottom: 28px;
    font-size: 15px;
    color: #f1f5f9;
  }}
  .card {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
  }}
  .card h2 {{
    margin-top: 0;
    font-size: 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .tag {{
    font-size: 12px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 4px;
    background: #0284c7;
    color: #fff;
  }}
  .tag.green {{ background: #16a34a; }}
  audio {{
    width: 100%;
    margin-top: 12px;
    outline: none;
  }}
  .meta {{
    font-size: 13px;
    color: #94a3b8;
    margin-top: 10px;
  }}
</style>
</head>
<body>

<h1>Cillian Murphy: Lightweight Local CPU Voice Clones</h1>
<p class="subtitle">Rendered 100% locally on your home Zorin Intel i5-12400 CPU &bull; Zero Cloud Cost ($0.00)</p>

<div class="text-box">
  <strong>Audition Text (from Chapter 10):</strong><br>
  &ldquo;Though its origins and its government ministers had IRA roots, the independent Ireland over which de Valera presided was deeply at odds with the IRA.&rdquo;
</div>

<div class="card">
  <h2>
    <span>1. Chatterbox Turbo (Cillian Murphy Clone)</span>
    <span class="tag green">Local CPU &bull; $0.00</span>
  </h2>
  <audio controls>
    <source src="data:audio/mpeg;base64,{turbo_b64}" type="audio/mpeg">
    Your browser does not support audio playback.
  </audio>
  <div class="meta">
    Duration: 8.47s &bull; Model: Chatterbox Turbo (~0.5B) &bull; Host: Zorin CPU &bull; Voice: <code>cillian_irish_dry.wav</code>
  </div>
</div>

<div class="card">
  <h2>
    <span>2. Chatterbox Nano (Cillian Murphy Clone)</span>
    <span class="tag">Ultra-Light CPU &bull; $0.00</span>
  </h2>
  <audio controls>
    <source src="data:audio/mpeg;base64,{nano_b64}" type="audio/mpeg">
    Your browser does not support audio playback.
  </audio>
  <div class="meta">
    Duration: 9.46s &bull; Model: Chatterbox Nano (~0.3B) &bull; Host: Zorin CPU &bull; Voice: <code>cillian_irish_dry.wav</code>
  </div>
</div>

</body>
</html>
"""

player_file = brain_dir / "cillian_lightweight_audition.html"
player_file.write_text(html_content, encoding="utf-8")
print(f"Created audition player: {player_file} ({player_file.stat().st_size:,} bytes)")
