import os
import time

# Folder to scan
folder = r"C:\Your\Folder"

# 15 minutes ago (in seconds since epoch)
threshold = time.time() - (15 * 60)

for root, dirs, files in os.walk(folder):
    for fname in files:
        full_path = os.path.join(root, fname)
        try:
            ctime = os.path.getctime(full_path)
            if ctime >= threshold:
                print(full_path)
        except OSError:
            pass  # Skip inaccessible files
