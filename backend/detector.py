import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
AMBIGUOUS_PATH = BASE_DIR / "data" / "ambiguous_words.json"

with open(AMBIGUOUS_PATH, "r", encoding="utf-8") as f:
    AMBIGUOUS_WORDS = json.load(f)

WEAK_TERMS = {
    "should": {
        "category": "Weak Modality",
        "explanation": "The word 'should' makes the requirement weak or optional in meaning.",
        "suggestion": "Use 'shall' if the requirement is mandatory.",
        "severity": "Medium"
    },
    "may": {
        "category": "Optional Requirement",
        "explanation": "The word 'may' indicates optional behavior, not a strict requirement.",
        "suggestion": "Use 'shall' if this behavior is required.",
        "severity": "Medium"
    },
    "can": {
        "category": "Weak Modality",
        "explanation": "The word 'can' describes possibility, not a strict requirement.",
        "suggestion": "Rewrite as a direct functional requirement.",
        "severity": "Medium"
    },
    "some": {
        "category": "Vague Quantity",
        "explanation": "The quantity is unclear and cannot be tested precisely.",
        "suggestion": "Replace 'some' with an exact number or range.",
        "severity": "Medium"
    },
    "many": {
        "category": "Vague Quantity",
        "explanation": "The quantity is too vague to measure or test.",
        "suggestion": "Specify the exact count or threshold.",
        "severity": "Medium"
    },
    "few": {
        "category": "Vague Quantity",
        "explanation": "The quantity is unclear.",
        "suggestion": "Use an exact count instead of 'few'.",
        "severity": "Medium"
    }
}

def detect(sentence):
    results = []
    sentence_lower = sentence.lower()

    for term, details in AMBIGUOUS_WORDS.items():
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        if re.search(pattern, sentence_lower):
            results.append({
                "term": term,
                "category": details["category"],
                "explanation": details["explanation"],
                "suggestion": details["suggestion"],
                "severity": details["severity"]
            })

    for term, details in WEAK_TERMS.items():
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        if re.search(pattern, sentence_lower):
            results.append({
                "term": term,
                "category": details["category"],
                "explanation": details["explanation"],
                "suggestion": details["suggestion"],
                "severity": details["severity"]
            })

    return results