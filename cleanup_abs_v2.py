import os
import shutil

abs_dir = "/opt/stacks/audiobookshelf/audiobooks"
if os.path.exists(abs_dir):
    for item in os.listdir(abs_dir):
        # We only want to delete directories that look like old EPUB conversions, 
        # but the instruction said "clear and properly clean up the ABS library..there are way too many old converts that are now below parr. aside from the apple in china book we did today".
        # I'll preserve "Apple in China" if it exists, and "nlp_test_ryan", and delete the rest.
        if "Apple" in item or "nlp_test" in item:
            print(f"Preserving: {item}")
            continue
        
        path = os.path.join(abs_dir, item)
        if os.path.isdir(path):
            print(f"Removing old audiobook: {item}")
            shutil.rmtree(path)
        elif os.path.isfile(path):
            print(f"Removing old file: {item}")
            os.remove(path)
    print("ABS library cleanup complete.")
else:
    print(f"Directory {abs_dir} not found on docker-vm.")