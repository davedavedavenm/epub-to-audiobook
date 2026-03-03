import subprocess
remote_cmd = """cd /home/dave/ai/lab/stacks/epub-to-audiobook/data/audiobooks/ModestProposal && \
ls -la && \
unzip -l 'A Modest Proposal.epub' | grep -E "SMIL|Audio"
"""
subprocess.run(["ssh", "zorin", remote_cmd])