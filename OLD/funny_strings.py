def process_string(s: str) -> list[str]:
    parts = s.split('_')
    if parts and parts[-1].endswith('x') and parts[-1][:-1].isdigit():
        return [f"{'_'.join(parts[:-1])}_{parts[-1][:-1]}{d}" for d in range(8)]
    
    i = len(parts)
    while i > 0 and parts[i - 1].isdigit():
        i -= 1
    
    prefix, numeric = '_'.join(parts[:i]), parts[i:]
    if len(numeric) <= 1:
        return [s]
    
    base = numeric[0]
    return [f"{prefix}_{base}"] + [f"{prefix}_{base[:-1]}{n}" for n in numeric[1:]]

def process_strings(strings: list[str]) -> list[str]:
    return [res for s in strings for res in process_string(s)]

if __name__ == '__main__':
    test_strings = [
        "my_name_101",
        "my_name_104_7",
        "Who_am_i_now_another_word_702_4_5_7",
        "bad_dog_30x",
        "woo_woo_101_3_4_7_9",
        "simple_test"
    ]
    
    print("\nProcessed results:")
    for res in process_strings(test_strings):
        print(f"  {res}")
