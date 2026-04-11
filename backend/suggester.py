def generate_rewrite(sentence, detected_items):
    rewritten = sentence

    replacement_map = {
        "should": "shall",
        "may": "shall",
        "can": "shall be able to"
    }

    for item in detected_items:
        term = item["term"]
        if term in replacement_map:
            rewritten = rewritten.replace(term, replacement_map[term])
            rewritten = rewritten.replace(term.capitalize(), replacement_map[term].capitalize())

    return rewritten