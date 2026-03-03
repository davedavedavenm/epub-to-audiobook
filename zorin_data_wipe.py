import os
import shutil

base = "/data"
to_clear = ["audiobooks", "previews", "toc_cache", "transcripts"]
for d in to_clear:
    path = os.path.join(base, d)
    if os.path.exists(path):
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            try:
                if os.path.isdir(item_path): shutil.rmtree(item_path)
                else: os.remove(item_path)
            except: pass

# Special handling for uploads
uploads = os.path.join(base, "uploads")
keep = ["modest_proposal.epub", "jekyll_hyde.epub", "modest_proposal_tts.epub", "jekyll_hyde_tts.epub"]
if os.path.exists(uploads):
    for item in os.listdir(uploads):
        if item not in keep and not item.startswith("search_"):
            item_path = os.path.join(uploads, item)
            try:
                if os.path.isdir(item_path): shutil.rmtree(item_path)
                else: os.remove(item_path)
            except: pass

print("Zorin /data cleanup complete.")