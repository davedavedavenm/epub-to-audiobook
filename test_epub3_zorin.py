import subprocess
remote_cmd = """docker exec epub-to-audiobook-ui python3 -c "
import sys, os
from pathlib import Path
sys.path.insert(0, '/app')
from epub_generator import package_epub3_with_audio

job_id = 'job-modest'
input_filename = 'modest_proposal.epub'
output_dirname = 'ModestProposal'
book_name = 'A Modest Proposal'

epub_in = Path('/data/uploads') / input_filename
epub_out = Path('/data/audiobooks') / output_dirname / (book_name + '.epub')
chunks_log = Path('/data/transcripts') / job_id / 'chunks.jsonl'
output_path = Path('/data/audiobooks') / output_dirname

try:
    package_epub3_with_audio(str(epub_in), str(epub_out), str(output_path), str(chunks_log))
except Exception as e:
    import traceback
    traceback.print_exc()
" """
subprocess.run(["ssh", "zorin", remote_cmd])