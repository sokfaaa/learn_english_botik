def parse_bulk(text: str):
    """
    Парсит строку вида 'apple:яблоко; dog:собака'.
    Возвращает (pairs, errors).
    """
    pairs, errors = [], []
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            errors.append(chunk)
            continue
        en, ru = chunk.split(":", 1)
        en, ru = en.strip().lower(), ru.strip().lower()
        if not en or not ru:
            errors.append(chunk)
            continue
        pairs.append((en, ru))
    return pairs, errors