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
        "severity": "Medium",
        "replacement": "shall"
    },
    "may": {
        "category": "Optional Requirement",
        "explanation": "The word 'may' indicates optional behavior, not a strict requirement.",
        "suggestion": "Use 'shall' if this behavior is required.",
        "severity": "Medium",
        "replacement": "shall"
    },
    "can": {
        "category": "Weak Modality",
        "explanation": "The word 'can' describes possibility, not a strict requirement.",
        "suggestion": "Rewrite as a direct functional requirement.",
        "severity": "Medium",
        "replacement": "shall be able to"
    },
    "some": {
        "category": "Vague Quantity",
        "explanation": "The quantity is unclear and cannot be tested precisely.",
        "suggestion": "Replace 'some' with an exact number or range.",
        "severity": "Medium",
        "replacement": "[exact number]"
    },
    "many": {
        "category": "Vague Quantity",
        "explanation": "The quantity is too vague to measure or test.",
        "suggestion": "Specify the exact count or threshold.",
        "severity": "Medium",
        "replacement": "[exact number]"
    },
    "few": {
        "category": "Vague Quantity",
        "explanation": "The quantity is unclear.",
        "suggestion": "Use an exact count instead of 'few'.",
        "severity": "Medium",
        "replacement": "[exact number]"
    },
    "fast": {
        "category": "Performance Ambiguity",
        "explanation": "The term 'fast' is subjective and not measurable.",
        "suggestion": "Specify measurable response time.",
        "severity": "High",
        "replacement": "within 2 seconds"
    },
    "quick": {
        "category": "Performance Ambiguity",
        "explanation": "The term 'quick' is vague.",
        "suggestion": "Specify measurable response time.",
        "severity": "High",
        "replacement": "within 2 seconds"
    },
    "efficient": {
        "category": "Subjective Quality",
        "explanation": "The word 'efficient' is not measurable by itself.",
        "suggestion": "Define measurable efficiency criteria.",
        "severity": "High",
        "replacement": "[measurable efficiency target]"
    },
    "easy": {
        "category": "Subjective Quality",
        "explanation": "The word 'easy' is subjective.",
        "suggestion": "State measurable usability requirements.",
        "severity": "High",
        "replacement": "[measurable usability target]"
    },
    "simple": {
        "category": "Subjective Quality",
        "explanation": "The word 'simple' is subjective.",
        "suggestion": "Describe the exact expected user interaction.",
        "severity": "High",
        "replacement": "[exact interaction steps]"
    },
    "user-friendly": {
        "category": "Subjective Quality",
        "explanation": "The phrase 'user-friendly' is subjective and unclear.",
        "suggestion": "Use measurable usability criteria.",
        "severity": "High",
        "replacement": "[measurable usability criteria]"
    },
    "reliable": {
        "category": "Quality Ambiguity",
        "explanation": "The word 'reliable' needs measurable targets.",
        "suggestion": "Specify uptime, availability, or error rate.",
        "severity": "High",
        "replacement": "99.9% uptime"
    },
    "secure": {
        "category": "Security Ambiguity",
        "explanation": "The word 'secure' is too general.",
        "suggestion": "Specify encryption, authentication, or access control.",
        "severity": "High",
        "replacement": "[specific security controls]"
    },
    "robust": {
        "category": "Quality Ambiguity",
        "explanation": "The word 'robust' is vague.",
        "suggestion": "Specify fault tolerance or recovery conditions.",
        "severity": "High",
        "replacement": "[fault tolerance target]"
    },
    "appropriate": {
        "category": "Subjective Language",
        "explanation": "The word 'appropriate' is subjective.",
        "suggestion": "Define the exact condition or rule.",
        "severity": "Medium",
        "replacement": "[exact rule]"
    },
    "sufficient": {
        "category": "Subjective Language",
        "explanation": "The word 'sufficient' is not measurable.",
        "suggestion": "State the required quantity or threshold.",
        "severity": "Medium",
        "replacement": "[exact threshold]"
    },
    "minimal": {
        "category": "Vague Quantity",
        "explanation": "The word 'minimal' is vague.",
        "suggestion": "Specify the exact minimum value.",
        "severity": "Medium",
        "replacement": "[exact minimum value]"
    },
    "maximum": {
        "category": "Vague Quantity",
        "explanation": "The word 'maximum' without a number is incomplete.",
        "suggestion": "Specify the maximum numeric value.",
        "severity": "Medium",
        "replacement": "[exact maximum value]"
    }
}


def split_into_sentences(text: str):
    text = text.strip()
    if not text:
        return []

    parts = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [part.strip() for part in parts if part.strip()]


def detect(sentence: str):
    results = []
    sentence_lower = sentence.lower()

    all_terms = {}

    for term, details in AMBIGUOUS_WORDS.items():
        details_copy = dict(details)
        if "replacement" not in details_copy:
            details_copy["replacement"] = details_copy.get("suggestion", "")
        all_terms[term.lower()] = details_copy

    for term, details in WEAK_TERMS.items():
        all_terms[term.lower()] = details

    for term, details in all_terms.items():
        pattern = r"\b" + re.escape(term) + r"\b"
        for match in re.finditer(pattern, sentence_lower):
            results.append({
                "term": term,
                "category": details["category"],
                "explanation": details["explanation"],
                "suggestion": details["suggestion"],
                "severity": details["severity"],
                "replacement": details.get("replacement", ""),
                "start": match.start(),
                "end": match.end()
            })

    results.sort(key=lambda x: x["start"])
    return results


def analyze_text(text: str):
    sentences = split_into_sentences(text)
    sentence_results = []
    all_issues = []

    for sentence in sentences:
        issues = detect(sentence)
        sentence_results.append({
            "sentence": sentence,
            "issues": issues
        })
        all_issues.extend(issues)

    return {
        "sentences": sentence_results,
        "all_issues": all_issues
    }