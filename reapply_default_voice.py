p = '/home/dave/ai/lab/stacks/epub-to-audiobook/webapp/templates/index.html'
import re
with open(p, 'r', encoding='utf-8') as f:
    c = f.read()

# Fix 1: Inject defaultVoice if missing
if 'const defaultVoice =' not in c:
    c = c.replace('const voices = {{ voices | tojson }};',
                  'const voices = {{ voices | tojson }};\n    const defaultVoice = "{{ default_voice }}";')

# Fix 2: Add selected logic to voiceOptions
new_logic = """        const voiceOptions = engines.map(engine => {
            const engineVoices = Object.entries(voices).filter(([id, v]) => v.engine === engine);
            return `<optgroup label="${engine.toUpperCase()} ENGINE">${engineVoices.map(([id, v]) => `<option value="${id}" ${id === defaultVoice ? 'selected' : ''}>${v.name} (${v.accent})</option>`).join('')}</optgroup>`;
        }).join('');"""

# Find the old block and replace it
old_pattern = r'const voiceOptions = engines\.map\(engine => \{.*?\}\)\.join\(\'\'\);'
c = re.sub(old_pattern, new_logic, c, flags=re.DOTALL)

with open(p, 'w', encoding='utf-8') as f:
    f.write(c)