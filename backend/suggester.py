import re


def generate_rewrite(text, detected_items):
    rewritten = text
    replacements = []

    for item in detected_items:
        original = item.get("term", "")
        replacement = item.get("replacement", "")
        if original and replacement:
            replacements.append((original, replacement))

    replacements.sort(key=lambda x: len(x[0]), reverse=True)

    for original, replacement in replacements:
        pattern = re.compile(re.escape(original), re.IGNORECASE)
        rewritten = pattern.sub(replacement, rewritten)

    return rewritten