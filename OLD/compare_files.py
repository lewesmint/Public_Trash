import argparse
from collections import defaultdict

def normalize_file_content(file_path):
    """
    Reads the file content and normalizes it by:
    - Ignoring line-ending differences (converting to '\n').
    - Removing Byte Order Marks (BOMs).
    """
    try:
        with open(file_path, 'rb') as file:
            raw_content = file.read()
            # Decode with BOM removal
            text = raw_content.decode('utf-8-sig')
            # Normalize line endings
            normalized_content = text.replace('\r\n', '\n').replace('\r', '\n')
            return normalized_content
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}")
        return None
    except PermissionError:
        print(f"Error: Permission denied: {file_path}")
        return None

def get_file_list(file_list_path):
    """
    Reads the file containing the list of file paths.
    """
    try:
        with open(file_list_path, 'r') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        print(f"Error: File list not found: {file_list_path}")
        return []
    except PermissionError:
        print(f"Error: Permission denied: {file_list_path}")
        return []

def compare_files(file_list_path):
    """
    Compares the content of files listed in the given file.
    """
    file_list = get_file_list(file_list_path)
    if not file_list:
        return [], []

    content_map = defaultdict(list)

    for file_path in file_list:
        normalized_content = normalize_file_content(file_path)
        if normalized_content is not None:
            content_map[normalized_content].append(file_path)

    # Separate into identical and unique groups
    identical_files = [files for files in content_map.values() if len(files) > 1]
    unique_files = [files[0] for files in content_map.values() if len(files) == 1]

    return identical_files, unique_files

def main():
    parser = argparse.ArgumentParser(description="Compare files listed in a file, ignoring line endings and BOMs.")
    parser.add_argument(
        "file_list", help="Path to a file containing a list of file paths to compare."
    )
    args = parser.parse_args()

    identical, unique = compare_files(args.file_list)

    print("\nIdentical Files:")
    if identical:
        for group in identical:
            print(f"  {', '.join(group)}")
    else:
        print("  None")

    print("\nUnique Files:")
    if unique:
        for file in unique:
            print(f"  {file}")
    else:
        print("  None")

if __name__ == "__main__":
    main()
