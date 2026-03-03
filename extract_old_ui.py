import subprocess
# Fetch binary from Zorin
cmd = ['ssh', 'zorin', "cd /home/dave/ai/lab/stacks/epub-to-audiobook && git show 340bfc6ae91ee4f4a3504641d08e52c18bd708a1:webapp/templates/index.html"]
res = subprocess.run(cmd, capture_output=True)
# Decode UTF-16
text = res.stdout.decode('utf-16')
# Save locally for reference
with open('old_index_fixed.html', 'w', encoding='utf-8') as f:
    f.write(text)
print("Successfully extracted and decoded old index.html")