import subprocess
remote_cmd = """docker logs --tail 100 epub-to-audiobook-worker | grep EPUB3"""
subprocess.run(["ssh", "zorin", remote_cmd])