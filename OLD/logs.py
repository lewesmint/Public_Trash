import os
import re
from pathlib import Path

def find_matching_logs(input_file):
    input_path = Path(input_file)
    base_name = input_path.name  # Extracts "client.log" from "logs/client.log"
    base_stem, base_ext = os.path.splitext(base_name)  # "client", ".log"
    
    # If the input has a path prefix, search only in that folder
    search_dirs = [input_path.parent] if input_path.parent != Path('.') else [Path('.'), Path('logs')]
    
    pattern = re.compile(rf"^{re.escape(base_stem)}\.\d{{4}}\.\d{{2}}\.\d{{2}}_\d{{2}}\.\d{{2}}\.\d{{2}}{re.escape(base_ext)}$")
    
    log_files = []
    
    for directory in search_dirs:
        if directory.exists():
            for file in directory.iterdir():
                if file.name == base_name or pattern.match(file.name):
                    log_files.append(file)
    
    # Sort files by timestamp extracted from the filename, treating base file as most recent
    def extract_timestamp(log_file):
        match = re.search(r'(\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2})', log_file.name)
        return match.group(1) if match else '9999.99.99_99.99.99'  # Ensures base file is latest

    log_files.sort(key=extract_timestamp, reverse=True)
    
    return log_files

# Example usage
input_file = "client.log"  # Can be "logs/client.log" or another prefixed path
matching_logs = find_matching_logs(input_file)

# Output the sorted list
for log in matching_logs:
    print(log)
