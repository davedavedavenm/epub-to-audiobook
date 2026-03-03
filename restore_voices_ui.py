import os
import re

p = 'webapp/templates/index.html'
# Read the current clean Zorin file (we already sanitized it to ASCII)
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Inject the Missing CSS for the Voices Tab (Editorial Noir style)
noir_css = """
.engine-section { margin-bottom: 64px; }
.engine-header { 
    font-family: 'Lora', serif; font-size: 1.4rem; font-weight: 800; 
    letter-spacing: 0.1em; color: var(--accent); margin-bottom: 32px; 
    border-bottom: 1px solid var(--border); padding-bottom: 16px;
    display: flex; align-items: center; gap: 16px;
}
.engine-header::after { content: ''; flex: 1; height: 1px; background: var(--border); opacity: 0.5; }

.voices-grid { 
    display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); 
    gap: 24px; 
}

.voice-card { 
    background: var(--bg-card); border: 1px solid var(--border); 
    border-radius: var(--radius-md); padding: 24px; transition: 0.3s;
    display: flex; justify-content: space-between; align-items: center;
}
.voice-card:hover { 
    border-color: var(--accent); transform: translateY(-4px); 
    box-shadow: 0 12px 30px -10px rgba(0,0,0,0.1); 
}

.voice-name { font-family: 'Lora', serif; font-size: 1.2rem; font-weight: 700; margin-bottom: 4px; }
.voice-meta { font-size: 0.85rem; color: var(--text-secondary); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }

.preview-btn { 
    width: 40px; height: 40px; border-radius: 50%; border: 1px solid var(--border);
    display: flex; align-items: center; justify-content: center; cursor: pointer;
    background: var(--bg-element); transition: 0.2s; color: var(--text-primary);
}
.preview-btn:hover { background: var(--accent); color: #fff; border-color: var(--accent); }
"""

# Inject before the closing </style>
c = c.replace('</style>', noir_css + '\n</style>')

# 2. Upgrade the renderVoices function to use the new UI and include Preview
new_render_voices = """
    function renderVoices() {
        const container = document.getElementById('voices-content');
        if(!container) return;
        const engines = [...new Set(Object.values(voices).map(v => v.engine))];
        container.innerHTML = engines.map(engine => {
            const engineVoices = Object.entries(voices).filter(([id, v]) => v.engine === engine);
            return `
                <div class="engine-section">
                    <div class="engine-header">${engine.toUpperCase()} ENGINE</div>
                    <div class="voices-grid">
                        ${engineVoices.map(([id, v]) => `
                            <div class="voice-card">
                                <div>
                                    <div class="voice-name">${escapeHtml(v.name)}</div>
                                    <div class="voice-meta">${v.accent} - ${v.gender}</div>
                                </div>
                                <button class="preview-btn" onclick="playVoicePreview('${id}', this)" title="Listen to preview">
                                    <span style="margin-left: 2px;">&#9654;</span>
                                </button>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }).join('');
    }

    async function playVoicePreview(voiceId, btn) {
        const original = btn.innerHTML;
        btn.innerHTML = '<span class="loading-spinner" style="width:16px; height:16px; border:2px solid #fff; border-top-color:transparent; border-radius:50%; animation:spin 1s linear infinite; display:inline-block;"></span>';
        btn.disabled = true;
        
        try {
            const resp = await fetch('/api/voices/preview', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ voice: voiceId })
            });
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const audio = document.getElementById('preview-audio');
            audio.src = url;
            audio.play();
            
            btn.innerHTML = '<span style="color:var(--success)">&#10003;</span>';
            setTimeout(() => { btn.innerHTML = original; btn.disabled = false; }, 2000);
        } catch(e) {
            console.error(e);
            btn.innerHTML = '<span style="color:var(--error)">!</span>';
            setTimeout(() => { btn.innerHTML = original; btn.disabled = false; }, 2000);
        }
    }
"""

# Replace the entire renderVoices function
c = re.sub(r'function renderVoices\(\) \{.*?\}\n', new_render_voices, c, flags=re.DOTALL)

with open(p, 'w', encoding='utf-8', newline='\n') as f:
    f.write(c)