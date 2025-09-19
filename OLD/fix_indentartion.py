import re

def correct_indentation(code: str) -> str:
    lines = code.splitlines()
    corrected_lines = []
    indent_level = 0
    inside_struct = False

    was_class = False
    for line in lines:
        stripped_line = line.strip()
        
        if stripped_line.startswith('class '):
            was_class = True
        if was_class and stripped_line=='':
            was_class = False
            continue
        if stripped_line.startswith('class '):
            indent_level = 0
            corrected_lines.append('    ' * indent_level + stripped_line)
        elif stripped_line.startswith('parser'):
            indent_level += 1
            corrected_lines.append('    ' * indent_level + stripped_line)
        elif stripped_line.startswith('struct_name'):
            corrected_lines.append('    ' * indent_level + stripped_line)
        elif stripped_line.startswith('typedef struct'):
            indent_level += 1
            corrected_lines.append('    ' * indent_level + stripped_line)
        elif stripped_line.startswith('{'):
            inside_struct = True
            corrected_lines.append('    ' * indent_level + stripped_line)
        elif stripped_line.startswith('}'):
            corrected_lines.append('    ' * indent_level + stripped_line)
            inside_struct = False
        elif stripped_line.startswith("'''"):
            corrected_lines.append('    ' * indent_level + stripped_line)
            indent_level -= 1
        elif inside_struct:
            corrected_lines.append('    ' * (1 + indent_level) + stripped_line)
        else:
            corrected_lines.append('    ' * indent_level + stripped_line)
        
        if stripped_line.startswith('class '):
            was_class = True
        else:
            was_class = False
        

    return '\n'.join(corrected_lines)

def process_file(input_filepath: str, output_filepath: str) -> None:
    with open(input_filepath, 'r') as infile:
        code = infile.read()
    
    corrected_code = correct_indentation(code)
    
    with open(output_filepath, 'w') as outfile:
        outfile.write(corrected_code)

if __name__ == "__main__":
    input_filepath = 'infile.py'
    output_filepath = 'outfile.py'

    process_file(input_filepath, output_filepath)
    print(f"Corrected code written to {output_filepath}")
