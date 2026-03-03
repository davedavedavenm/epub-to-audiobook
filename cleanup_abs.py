import os
import shutil

abs_dir = "/data/abs"
if os.path.exists(abs_dir):
    for item in os.listdir(abs_dir):
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