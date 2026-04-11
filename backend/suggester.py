def generate_rewrite(sentence, detected_items):
    rewritten = sentence

    replacement_map = {}

    for item in detected_items:
        term = item["term"]
        replacement = item.get("replacement", "").strip()
        if replacement:
            replacement_map[term.lower()] = replacement

    for term, replacement in replacement_map.items():
        rewritten = rewritten.replace(term, replacement)
        rewritten = rewritten.replace(term.capitalize(), replacement.capitalize())

    return rewritten