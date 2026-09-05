from __future__ import annotations

from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "evaluations" / "new-engines" / "output" / "kokoro_variations"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_TEXT = (
    "Silicon Valley can be an amazingly drab place. "
    "The peninsula south of San Francisco has natural beauty, with rolling hills and coastal views, "
    "but you strain to see them beyond so many corporate parking lots. "
    "Mountain View and Menlo Park are bizarrely full of rug shops."
)

VARIATIONS = [
    {"name": "george_relaxed", "voice": "bm_george", "speed": 0.92, "label": "George (Relaxed 0.92x)"},
    {"name": "lewis_relaxed", "voice": "bm_lewis", "speed": 0.92, "label": "Lewis (Relaxed 0.92x)"},
    {"name": "blend_george_lewis", "voice": "bm_george(2)+bm_lewis(1)", "speed": 0.95, "label": "Blend: 67% George + 33% Lewis (0.95x)"},
    {"name": "blend_lewis_george", "voice": "bm_lewis(2)+bm_george(1)", "speed": 0.95, "label": "Blend: 67% Lewis + 33% George (0.95x)"},
    {"name": "fable_storyteller", "voice": "bm_fable", "speed": 0.92, "label": "Fable (British Storyteller 0.92x)"},
]

def main():
    url = "http://localhost:8880/v1/audio/speech"
    for var in VARIATIONS:
        out_file = OUT_DIR / f"kokoro_{var['name']}.mp3"
        print(f"Generating {var['label']}...")
        r = requests.post(
            url,
            json={
                "input": SAMPLE_TEXT,
                "voice": var["voice"],
                "speed": var["speed"],
                "response_format": "mp3",
            },
            timeout=30,
        )
        r.raise_for_status()
        out_file.write_bytes(r.content)
        print(f"  Wrote {out_file.name} ({len(r.content):,} bytes)")

if __name__ == "__main__":
    main()
