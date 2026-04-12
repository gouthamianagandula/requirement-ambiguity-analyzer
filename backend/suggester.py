import re


VAGUE_REPLACEMENTS = {
    "fast": "within 2 seconds",
    "quick": "within 2 seconds",
    "quickly": "within 2 seconds",
    "soon": "within [exact time]",
    "easy": "[measurable usability requirement]",
    "user-friendly": "[measurable usability criteria]",
    "efficient": "[measurable efficiency target]",
    "appropriate": "[exact rule]",
    "optimal": "[measurable criteria]",
    "many": "[exact number]",
    "some": "[exact number]",
    "few": "[exact count]",
}

PRONOUN_REPLACEMENTS = {
    "it": "[exact component]",
    "they": "[exact actors or components]",
    "them": "[exact actors or components]",
    "their": "[exact owner]",
    "this": "[exact item]",
    "that": "[exact item]",
    "these": "[exact items]",
    "those": "[exact items]",
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


def _replace_word(text: str, word: str, replacement: str) -> str:
    if not word or not replacement:
        return text
    return re.sub(rf"\b{re.escape(word)}\b", replacement, text, flags=re.IGNORECASE)


def _apply_issue_replacements(text, detected_items):
    rewritten = text

    for item in detected_items:
        issue_type = item.get("issue_type", "")
        original = item.get("term", "")
        replacement = item.get("replacement", "")

        if not original:
            continue

        if issue_type == "ambiguity":
            rewritten = _replace_word(
                rewritten,
                original,
                VAGUE_REPLACEMENTS.get(original.lower(), replacement or "[specific measurable term]")
            )

        elif issue_type == "unclear_pronoun":
            rewritten = _replace_word(
                rewritten,
                original,
                PRONOUN_REPLACEMENTS.get(original.lower(), "[exact noun]")
            )

        elif issue_type == "repeated_word":
            parts = original.split()
            if parts:
                rewritten = rewritten.replace(original, parts[0], 1)

        elif issue_type == "double_negative":
            rewritten = re.sub(r"\bcannot not\b", "cannot", rewritten, flags=re.IGNORECASE)
            rewritten = re.sub(r"\bcan't not\b", "cannot", rewritten, flags=re.IGNORECASE)
            rewritten = re.sub(r"\bnot no\b", "no", rewritten, flags=re.IGNORECASE)

        elif issue_type in {"grammar", "wrong_verb_form", "spelling", "punctuation", "casing", "style"}:
            if replacement:
                rewritten = re.sub(
                    re.escape(original),
                    replacement,
                    rewritten,
                    count=1,
                    flags=re.IGNORECASE
                )

    return _clean_spaces(rewritten)


def _normalize_requirement_style(text: str) -> str:
    text = _clean_spaces(text)

    replacements = [
        (r"\bthe system should\b", "The system shall"),
        (r"\bsystem should\b", "The system shall"),
        (r"\bthe system will\b", "The system shall"),
        (r"\bsystem will\b", "The system shall"),
        (r"\bthe application should\b", "The application shall"),
        (r"\bapplication should\b", "The application shall"),
        (r"\bthe software should\b", "The software shall"),
        (r"\bsoftware should\b", "The software shall"),
        (r"\band/or\b", "or"),
    ]

    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    text = text.replace("/", " or ")
    text = re.sub(r"\s*;\s*", ". ", text)
    text = re.sub(r"\s*,\s*which\s+", ". This ", text, flags=re.IGNORECASE)
    text = _clean_spaces(text)

    if text:
        text = text[0].upper() + text[1:]

    return _ensure_period(text)


def generate_rewrite(text, detected_items):
    rewritten = _apply_issue_replacements(text, detected_items)
    rewritten = _normalize_requirement_style(rewritten)
    return rewritten