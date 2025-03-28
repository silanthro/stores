from collections import Counter


def check_duplicates(input_list: list):
    counts = Counter(input_list)
    duplicates = [i for i in counts if counts[i] > 1]
    if duplicates:
        raise ValueError(f"Found duplicate(s): {duplicates}")
