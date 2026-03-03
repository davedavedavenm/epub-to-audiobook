import subprocess
remote_cmd = """docker logs --tail 200 epub-to-audiobook-worker | grep -A 20 -B 5 "Renamed 3 files in /data/audiobooks/ModestProposal" """
subprocess.run(["ssh", "zorin", remote_cmd])