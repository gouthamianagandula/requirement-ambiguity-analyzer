import re


VAGUE_REPLACEMENTS = {
    "fast": "within 2 seconds",
    "quick": "within 2 seconds",
    "quickly": "within 2 seconds",
    "soon": "within a defined time limit",
    "efficient": "with a defined performance target",
    "user-friendly": "with defined usability criteria",
    "secure": "with defined security controls",
    "reliable": "with defined reliability targets",
    "appropriate": "according to the defined rule",
    "optimal": "according to the defined optimization target",
    "many": "the specified number of",
    "some": "the specified",
    "few": "the defined number of",
}

WEAK_WORD_REPLACEMENTS = {
    "should": "shall",
    "may": "shall",
    "can": "shall be able to",
}


def _clean_spaces(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def _ensure_period(text: str) -> str:
    text = text.strip()
    if text and text[-1] not in ".!?":
        text += "."
    return text


def _capitalize_sentences(text: str) -> str:
    parts = re.split(r"([.!?]\s*)", text)
    if not parts:
        return text

    rebuilt = []
    for i in range(0, len(parts), 2):
        sentence = parts[i].strip()
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        if sentence:
            sentence = sentence[0].upper() + sentence[1:]
            rebuilt.append(sentence + sep)
    return "".join(rebuilt).strip()


def _replace_word(text: str, old: str, new: str) -> str:
    if not old or not new:
        return text
    return re.sub(rf"\b{re.escape(old)}\b", new, text, flags=re.IGNORECASE)


def _find_nearest_subject_before(text: str, pronoun: str) -> str:
    pattern = re.compile(rf"\b{re.escape(pronoun)}\b", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return ""

    before = text[:match.start()]
    nouns = re.findall(r"\b[A-Za-z][A-Za-z'-]{2,}\b", before)
    if not nouns:
        return ""

    filtered = [w for w in nouns if w.lower() not in {
        "the", "a", "an", "and", "or", "but", "with", "from", "into",
        "that", "this", "these", "those", "shall", "should", "must",
        "will", "can", "may", "was", "were", "is", "are", "be", "been"
    }]
    return filtered[-1] if filtered else ""


def _apply_replacements(text, detected_items):
    rewritten = text

    for item in detected_items:
        issue_type = item.get("issue_type", "")
        original = item.get("term", "")
        replacement = item.get("replacement", "") or ""

        if not original:
            continue

        if issue_type == "ambiguity":
            better = VAGUE_REPLACEMENTS.get(original.lower(), replacement)
            if better:
                rewritten = _replace_word(rewritten, original, better)

        elif issue_type == "unclear_pronoun":
            pronoun = original.lower()
            antecedent = replacement.strip() if replacement.strip() else _find_nearest_subject_before(rewritten, original)
            if antecedent and pronoun in {"it", "this", "that"}:
                rewritten = _replace_word(rewritten, original, antecedent)
            elif antecedent and pronoun in {"they", "them", "their", "these", "those"}:
                rewritten = _replace_word(rewritten, original, antecedent)

        elif issue_type == "repeated_word":
            parts = original.split()
            if parts:
                rewritten = rewritten.replace(original, parts[0], 1)

        elif issue_type == "double_negative":
            rewritten = re.sub(r"\bcannot not\b", "cannot", rewritten, flags=re.IGNORECASE)
            rewritten = re.sub(r"\bcan't not\b", "cannot", rewritten, flags=re.IGNORECASE)
            rewritten = re.sub(r"\bnot no\b", "no", rewritten, flags=re.IGNORECASE)
            rewritten = re.sub(r"\bnever no\b", "no", rewritten, flags=re.IGNORECASE)

        elif issue_type in {"grammar", "wrong_verb_form", "spelling", "punctuation", "casing", "style"}:
            if replacement:
                rewritten = re.sub(re.escape(original), replacement, rewritten, count=1, flags=re.IGNORECASE)

    return _clean_spaces(rewritten)


def _normalize_requirement_style(text: str) -> str:
    text = _clean_spaces(text)

    for weak, strong in WEAK_WORD_REPLACEMENTS.items():
        text = re.sub(rf"\b{re.escape(weak)}\b", strong, text, flags=re.IGNORECASE)

    text = re.sub(r"\band/or\b", "or", text, flags=re.IGNORECASE)
    text = text.replace("/", " or ")
    text = re.sub(r"\s*;\s*", ". ", text)
    text = re.sub(r"\s*,\s*which\s+", ". This ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*,\s*and\s+", ", and ", text)
    text = _clean_spaces(text)
    text = _capitalize_sentences(text)
    text = _ensure_period(text)
    return text


def _split_overlong_sentences(text: str) -> str:
    text = re.sub(
        r",\s+(because|although|while|when|if)\s+",
        lambda m: ". " + m.group(1).capitalize() + " ",
        text,
        flags=re.IGNORECASE,
    )
    text = _clean_spaces(text)
    return _ensure_period(text)


def generate_rewrite(text, detected_items, corrected_text=None):
    base = corrected_text if corrected_text else text
    base = _apply_replacements(base, detected_items)
    base = _split_overlong_sentences(base)
    base = _normalize_requirement_style(base)
    return base