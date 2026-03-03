import subprocess
remote_cmd = "ls -la /home/dave/ai/lab/stacks/epub-to-audiobook/data/transcripts/job-modest"
subprocess.run(["ssh", "zorin", remote_cmd])