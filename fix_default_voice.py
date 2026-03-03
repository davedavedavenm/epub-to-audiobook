import os

# 1. Update app.py to pass default_voice
app_path = 'webapp/app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    content = f.read()

if 'default_voice=DEFAULT_VOICE' not in content:
    content = content.replace("render_template('index.html', voices=VOICES, engines=TTS_ENGINES)",
                              "render_template('index.html', voices=VOICES, engines=TTS_ENGINES, default_voice=DEFAULT_VOICE)")

with open(app_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

# 2. Update index.html to use default_voice
html_path = 'webapp/templates/index.html'
with open(html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Pass default_voice to JS
if 'const defaultVoice =' not in html:
    html = html.replace('const voices = {{ voices | tojson }};',
                        'const voices = {{ voices | tojson }};\n    const defaultVoice = "{{ default_voice }}";')

# Set default value in the select
# Find: <select id="voice-${bookId}" class="input-control">${voiceOptions}</select>
# Replace with one that sets the value
html = html.replace('<select id="voice-${bookId}" class="input-control">${voiceOptions}</select>',
                    '<select id="voice-${bookId}" class="input-control" onchange="this.dataset.changed=true">${voiceOptions}</select>')

# Inject logic to set the default value after innerHTML is set
# We need to find where grid.innerHTML is assigned and add a line to set defaults
if 'document.getElementById(`voice-${bookId}`).value = defaultVoice;' not in html:
    html = html.replace('grid.innerHTML = filtered.map(b => {', 
                        'grid.innerHTML = filtered.map(b => {') # No change here, just marker
    
    # We need to set it after the innerHTML is rendered. 
    # Since it's a map().join(''), we need to do it after the loop.
    # Actually, it's easier to just use template literals with 'selected' logic in voiceOptions.
    
# Let's try a different approach: modify the voiceOptions mapping to include 'selected'
voice_opt_logic = """        const voiceOptions = engines.map(engine => {
            const engineVoices = Object.entries(voices).filter(([id, v]) => v.engine === engine);
            return `<optgroup label="${engine.toUpperCase()} ENGINE">${engineVoices.map(([id, v]) => `<option value="${id}" ${id === defaultVoice ? 'selected' : ''}>${v.name} (${v.accent})</option>`).join('')}</optgroup>`;
        }).join('');"""

# Find old voiceOptions logic
import re
html = re.sub(r'const voiceOptions = engines\.map\(engine => \{.*?\}\)\.join\(\'\'\);', voice_opt_logic, html, flags=re.DOTALL)

with open(html_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(html)