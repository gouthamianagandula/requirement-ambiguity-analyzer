import re
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "ambiguous_words.json"

FILE_TERMS = {}
if DATA_FILE.exists():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        FILE_TERMS = json.load(f)

DEFAULT_TERMS = {
    "fast": {
        "category": "Performance Ambiguity",
        "explanation": "The word 'fast' is subjective and not measurable.",
        "suggestion": "Specify exact response time.",
        "severity": "High",
        "replacement": "within 2 seconds"
    },
    "quick": {
        "category": "Performance Ambiguity",
        "explanation": "The word 'quick' is vague.",
        "suggestion": "Specify exact response time.",
        "severity": "High",
        "replacement": "within 2 seconds"
    },
    "soon": {
        "category": "Time Ambiguity",
        "explanation": "The word 'soon' is not measurable.",
        "suggestion": "Specify exact deadline.",
        "severity": "High",
        "replacement": "by [exact date/time]"
    },
    "easy": {
        "category": "Usability Ambiguity",
        "explanation": "The word 'easy' is subjective.",
        "suggestion": "Define measurable usability criteria.",
        "severity": "High",
        "replacement": "[measurable usability requirement]"
    },
    "user-friendly": {
        "category": "Usability Ambiguity",
        "explanation": "The phrase 'user-friendly' is subjective.",
        "suggestion": "Use measurable usability criteria.",
        "severity": "High",
        "replacement": "[measurable usability criteria]"
    },
    "efficient": {
        "category": "Quality Ambiguity",
        "explanation": "The word 'efficient' is subjective.",
        "suggestion": "Use measurable performance or efficiency criteria.",
        "severity": "High",
        "replacement": "[measurable efficiency target]"
    },
    "etc": {
        "category": "Incomplete Requirement",
        "explanation": "The term 'etc' leaves the requirement incomplete.",
        "suggestion": "List all required items explicitly.",
        "severity": "High",
        "replacement": "[complete list]"
    },
    "and/or": {
        "category": "Logical Ambiguity",
        "explanation": "The phrase 'and/or' is ambiguous.",
        "suggestion": "Choose either 'and' or 'or'.",
        "severity": "High",
        "replacement": "[and or or]"
    },
    "may": {
        "category": "Weak Language",
        "explanation": "The word 'may' makes the requirement optional.",
        "suggestion": "Use 'shall' if the behavior is mandatory.",
        "severity": "Medium",
        "replacement": "shall"
    },
    "should": {
        "category": "Weak Language",
        "explanation": "The word 'should' is weak and not strictly enforceable.",
        "suggestion": "Use 'shall' or 'must' for mandatory behavior.",
        "severity": "Medium",
        "replacement": "shall"
    },
    "can": {
        "category": "Weak Language",
        "explanation": "The word 'can' describes possibility, not a strict requirement.",
        "suggestion": "Rewrite as direct system behavior.",
        "severity": "Medium",
        "replacement": "shall be able to"
    },
    "might": {
        "category": "Uncertainty",
        "explanation": "The word 'might' introduces uncertainty.",
        "suggestion": "State the requirement clearly and directly.",
        "severity": "Medium",
        "replacement": "shall"
    },
    "appropriate": {
        "category": "Subjective Language",
        "explanation": "The word 'appropriate' is not precise.",
        "suggestion": "Define the exact condition or rule.",
        "severity": "Medium",
        "replacement": "[exact rule]"
    },
    "sufficient": {
        "category": "Vague Quantity",
        "explanation": "The word 'sufficient' is vague.",
        "suggestion": "Specify threshold or quantity.",
        "severity": "Medium",
        "replacement": "[exact threshold]"
    },
    "minimal": {
        "category": "Vague Quantity",
        "explanation": "The word 'minimal' is unclear.",
        "suggestion": "Specify exact minimum value.",
        "severity": "Medium",
        "replacement": "[exact minimum]"
    },
    "optimal": {
        "category": "Subjective Language",
        "explanation": "The word 'optimal' is subjective.",
        "suggestion": "Define measurable criteria.",
        "severity": "High",
        "replacement": "[measurable criteria]"
    },
    "reliable": {
        "category": "Quality Ambiguity",
        "explanation": "The word 'reliable' needs measurable criteria.",
        "suggestion": "Specify uptime or failure rate.",
        "severity": "High",
        "replacement": "99.9% uptime"
    },
    "secure": {
        "category": "Security Ambiguity",
        "explanation": "The word 'secure' is too broad.",
        "suggestion": "Specify exact security controls.",
        "severity": "High",
        "replacement": "[specific security controls]"
    },
    "simple": {
        "category": "Subjective Language",
        "explanation": "The word 'simple' is subjective.",
        "suggestion": "Describe exact interaction steps.",
        "severity": "High",
        "replacement": "[exact interaction steps]"
    },
    "many": {
        "category": "Vague Quantity",
        "explanation": "The quantity is unclear.",
        "suggestion": "Use an exact number.",
        "severity": "Medium",
        "replacement": "[exact number]"
    },
    "some": {
        "category": "Vague Quantity",
        "explanation": "The quantity is vague.",
        "suggestion": "Use an exact number or list.",
        "severity": "Medium",
        "replacement": "[exact number]"
    },
    "few": {
        "category": "Vague Quantity",
        "explanation": "The quantity is vague.",
        "suggestion": "Use an exact count.",
        "severity": "Medium",
        "replacement": "[exact count]"
    },
    "as soon as possible": {
        "category": "Time Ambiguity",
        "explanation": "The phrase is not measurable.",
        "suggestion": "Specify deadline or time limit.",
        "severity": "High",
        "replacement": "[exact deadline]"
    },
    "if possible": {
        "category": "Optional Language",
        "explanation": "The phrase makes the requirement optional and unclear.",
        "suggestion": "State whether it is mandatory or remove it.",
        "severity": "Medium",
        "replacement": "[mandatory rule]"
    },
    "where necessary": {
        "category": "Conditional Ambiguity",
        "explanation": "The phrase does not define the condition clearly.",
        "suggestion": "Specify the exact condition.",
        "severity": "Medium",
        "replacement": "[exact condition]"
    },
    "where applicable": {
        "category": "Conditional Ambiguity",
        "explanation": "The condition is unclear.",
        "suggestion": "Specify when it applies.",
        "severity": "Medium",
        "replacement": "[exact condition]"
    }
}

TERMS = {}

for key, value in FILE_TERMS.items():
    item = dict(value)
    if "replacement" not in item:
        item["replacement"] = item.get("suggestion", "")
    TERMS[key.lower()] = item

for key, value in DEFAULT_TERMS.items():
    TERMS[key.lower()] = value


def split_into_sentences(text: str):
    text = text.strip()
    if not text:
        return []
    parts = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [p.strip() for p in parts if p.strip()]


def _find_term_matches(text: str, term: str):
    escaped = re.escape(term)
    if " " in term or "-" in term:
        pattern = re.compile(escaped, re.IGNORECASE)
    else:
        pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
    return list(pattern.finditer(text))


def detect(text: str):
    results = []
    for term, details in TERMS.items():
        matches = _find_term_matches(text, term)
        for match in matches:
            results.append({
                "term": match.group(0),
                "matched_term": term,
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

    for sentence in sentences:
        issues = detect(sentence)
        sentence_results.append({
            "sentence": sentence,
            "issues": issues
        })

    all_issues = detect(text)

    return {
        "sentences": sentence_results,
        "all_issues": all_issues
    }