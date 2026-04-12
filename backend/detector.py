import os
import re
import json
from pathlib import Path
from functools import lru_cache
from typing import Dict, List, Tuple, Any

import nltk
from nltk import pos_tag
from nltk.corpus import wordnet as wn
from spellchecker import SpellChecker
import language_tool_python
from language_tool_python.utils import correct as lt_correct


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "ambiguous_words.json"


def ensure_nltk_data():
    packages = [
        "wordnet",
        "omw-1.4",
        "averaged_perceptron_tagger",
        "averaged_perceptron_tagger_eng",
    ]
    for pkg in packages:
        try:
            nltk.download(pkg, quiet=True)
        except Exception:
            pass


ensure_nltk_data()

SPELL = SpellChecker()

FILE_TERMS = {}
if DATA_FILE.exists():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        FILE_TERMS = json.load(f)

DEFAULT_TERMS = {
    "fast": {
        "category": "Performance Ambiguity",
        "explanation": "The word is subjective and not measurable.",
        "suggestion": "Specify exact response time.",
        "severity": "High",
        "replacement": "within 2 seconds",
    },
    "quick": {
        "category": "Performance Ambiguity",
        "explanation": "The word is vague.",
        "suggestion": "Specify exact response time.",
        "severity": "High",
        "replacement": "within 2 seconds",
    },
    "quickly": {
        "category": "Performance Ambiguity",
        "explanation": "The word is vague.",
        "suggestion": "Specify exact response time.",
        "severity": "High",
        "replacement": "within 2 seconds",
    },
    "soon": {
        "category": "Time Ambiguity",
        "explanation": "The word is not measurable.",
        "suggestion": "Specify exact deadline or time.",
        "severity": "High",
        "replacement": "within [exact time]",
    },
    "easy": {
        "category": "Usability Ambiguity",
        "explanation": "The word is subjective.",
        "suggestion": "Define measurable usability criteria.",
        "severity": "High",
        "replacement": "[measurable usability requirement]",
    },
    "user-friendly": {
        "category": "Usability Ambiguity",
        "explanation": "The phrase is subjective.",
        "suggestion": "Use measurable usability criteria.",
        "severity": "High",
        "replacement": "[measurable usability criteria]",
    },
    "efficient": {
        "category": "Quality Ambiguity",
        "explanation": "The word is subjective.",
        "suggestion": "Use measurable performance or efficiency criteria.",
        "severity": "High",
        "replacement": "[measurable efficiency target]",
    },
    "etc": {
        "category": "Incomplete Requirement",
        "explanation": "The term leaves the requirement incomplete.",
        "suggestion": "List all required items explicitly.",
        "severity": "High",
        "replacement": "[complete list]",
    },
    "and/or": {
        "category": "Logical Ambiguity",
        "explanation": "The phrase is ambiguous.",
        "suggestion": "Choose either 'and' or 'or'.",
        "severity": "High",
        "replacement": "[choose one]",
    },
    "may": {
        "category": "Weak Language",
        "explanation": "The word makes the requirement optional.",
        "suggestion": "Use 'shall' if the behavior is mandatory.",
        "severity": "Medium",
        "replacement": "shall",
    },
    "should": {
        "category": "Weak Language",
        "explanation": "The word is weak and not strictly enforceable.",
        "suggestion": "Use 'shall' or 'must' for mandatory behavior.",
        "severity": "Medium",
        "replacement": "shall",
    },
    "can": {
        "category": "Weak Language",
        "explanation": "The word describes possibility, not a strict requirement.",
        "suggestion": "Rewrite as direct system behavior.",
        "severity": "Medium",
        "replacement": "shall be able to",
    },
    "might": {
        "category": "Uncertainty",
        "explanation": "The word introduces uncertainty.",
        "suggestion": "State the requirement clearly and directly.",
        "severity": "Medium",
        "replacement": "shall",
    },
    "appropriate": {
        "category": "Subjective Language",
        "explanation": "The word is not precise.",
        "suggestion": "Define the exact condition or rule.",
        "severity": "Medium",
        "replacement": "[exact rule]",
    },
    "sufficient": {
        "category": "Vague Quantity",
        "explanation": "The word is vague.",
        "suggestion": "Specify threshold or quantity.",
        "severity": "Medium",
        "replacement": "[exact threshold]",
    },
    "minimal": {
        "category": "Vague Quantity",
        "explanation": "The word is unclear.",
        "suggestion": "Specify exact minimum value.",
        "severity": "Medium",
        "replacement": "[exact minimum]",
    },
    "optimal": {
        "category": "Subjective Language",
        "explanation": "The word is subjective.",
        "suggestion": "Define measurable criteria.",
        "severity": "High",
        "replacement": "[measurable criteria]",
    },
    "reliable": {
        "category": "Quality Ambiguity",
        "explanation": "The word needs measurable criteria.",
        "suggestion": "Specify uptime or failure rate.",
        "severity": "High",
        "replacement": "99.9% uptime",
    },
    "secure": {
        "category": "Security Ambiguity",
        "explanation": "The word is too broad.",
        "suggestion": "Specify exact security controls.",
        "severity": "High",
        "replacement": "[specific security controls]",
    },
    "simple": {
        "category": "Subjective Language",
        "explanation": "The word is subjective.",
        "suggestion": "Describe exact interaction steps.",
        "severity": "High",
        "replacement": "[exact interaction steps]",
    },
    "many": {
        "category": "Vague Quantity",
        "explanation": "The quantity is unclear.",
        "suggestion": "Use an exact number.",
        "severity": "Medium",
        "replacement": "[exact number]",
    },
    "some": {
        "category": "Vague Quantity",
        "explanation": "The quantity is vague.",
        "suggestion": "Use an exact number or list.",
        "severity": "Medium",
        "replacement": "[exact number]",
    },
    "few": {
        "category": "Vague Quantity",
        "explanation": "The quantity is vague.",
        "suggestion": "Use an exact count.",
        "severity": "Medium",
        "replacement": "[exact count]",
    },
    "as soon as possible": {
        "category": "Time Ambiguity",
        "explanation": "The phrase is not measurable.",
        "suggestion": "Specify deadline or time limit.",
        "severity": "High",
        "replacement": "[exact deadline]",
    },
    "if possible": {
        "category": "Optional Language",
        "explanation": "The phrase makes the requirement optional and unclear.",
        "suggestion": "State whether it is mandatory or remove it.",
        "severity": "Medium",
        "replacement": "[mandatory rule]",
    },
    "where necessary": {
        "category": "Conditional Ambiguity",
        "explanation": "The phrase does not define the condition clearly.",
        "suggestion": "Specify the exact condition.",
        "severity": "Medium",
        "replacement": "[exact condition]",
    },
    "where applicable": {
        "category": "Conditional Ambiguity",
        "explanation": "The condition is unclear.",
        "suggestion": "Specify when it applies.",
        "severity": "Medium",
        "replacement": "[exact condition]",
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

UNCLEAR_PRONOUNS = {"he", "she", "it", "they", "them", "their", "this", "that", "these", "those"}
DOUBLE_NEGATIVE_TERMS = {
    "not", "no", "never", "nothing", "nobody", "none", "neither",
    "nowhere", "hardly", "scarcely", "barely", "cannot", "can't",
    "won't", "don't", "doesn't"
}
MULTI_MEANING_WORDS = {
    "bank", "file", "light", "charge", "right", "left", "draft",
    "current", "issue", "case", "match", "port", "table", "state",
    "block", "record", "run", "monitor", "lead", "address"
}


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_into_sentences(text: str) -> List[Tuple[str, int]]:
    out = []
    for m in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", text, flags=re.MULTILINE):
        sentence = m.group(0).strip()
        if sentence:
            leading = len(m.group(0)) - len(m.group(0).lstrip())
            out.append((sentence, m.start() + leading))
    return out


def tokenize_with_offsets(text: str) -> List[Tuple[str, int, int]]:
    items = []
    for m in re.finditer(r"\b[\w'-]+\b", text):
        items.append((m.group(0), m.start(), m.end()))
    return items


@lru_cache(maxsize=1)
def get_language_tool():
    remote_url = os.getenv("LT_REMOTE_URL", "").strip()
    language = os.getenv("LT_LANGUAGE", "en-US")
    if remote_url:
        return language_tool_python.LanguageTool(language, remote_server=remote_url)
    return language_tool_python.LanguageTool(language)


def make_issue(
    term: str,
    start: int,
    end: int,
    category: str,
    explanation: str,
    suggestion: str,
    severity: str,
    replacement: str = "",
    matched_term: str = "",
    issue_type: str = "",
    source: str = "custom",
    meanings: List[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return {
        "term": term,
        "matched_term": matched_term or term.lower(),
        "category": category,
        "explanation": explanation,
        "suggestion": suggestion,
        "severity": severity,
        "replacement": replacement,
        "start": start,
        "end": end,
        "issue_type": issue_type or category.lower().replace(" ", "_"),
        "source": source,
        "meanings": meanings or [],
    }


def dedupe_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for issue in sorted(issues, key=lambda x: (x["start"], x["end"], x["category"], x["term"].lower())):
        key = (
            issue["start"],
            issue["end"],
            issue["category"].lower(),
            issue["term"].lower(),
            issue["suggestion"].lower(),
        )
        if key not in seen:
            seen.add(key)
            out.append(issue)
    return out


def _find_term_matches(text: str, term: str):
    escaped = re.escape(term)
    if " " in term or "-" in term or "/" in term:
        pattern = re.compile(escaped, re.IGNORECASE)
    else:
        pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
    return list(pattern.finditer(text))


def detect_keyword_terms(text: str, offset: int = 0) -> List[Dict[str, Any]]:
    results = []
    for term, details in TERMS.items():
        for match in _find_term_matches(text, term):
            results.append(make_issue(
                term=match.group(0),
                matched_term=term,
                category=details["category"],
                explanation=details["explanation"],
                suggestion=details["suggestion"],
                severity=details["severity"],
                replacement=details.get("replacement", ""),
                start=offset + match.start(),
                end=offset + match.end(),
                issue_type="ambiguity",
                source="rules",
            ))
    return results


def detect_repeated_words(text: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    for m in re.finditer(r"\b(\w+)\s+(\1)\b", text, flags=re.IGNORECASE):
        issues.append(make_issue(
            term=m.group(0),
            start=offset + m.start(),
            end=offset + m.end(),
            category="Repeated Word",
            explanation="The same word appears twice in sequence.",
            suggestion="Remove the repeated word.",
            severity="High",
            replacement=m.group(1),
            issue_type="repeated_word",
            source="rules",
        ))
    return issues


def detect_unclear_pronouns(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    tokens = tokenize_with_offsets(sentence)
    words = [w for w, _, _ in tokens]

    for idx, (word, start, end) in enumerate(tokens):
        lower = word.lower()
        if lower not in UNCLEAR_PRONOUNS:
            continue

        before = words[:idx]
        tags = pos_tag(before) if before else []
        noun_count = sum(1 for _, tag in tags if tag.startswith("NN"))

        if idx == 0 or noun_count >= 2 or lower in {"it", "they", "this", "that"}:
            issues.append(make_issue(
                term=word,
                start=offset + start,
                end=offset + end,
                category="Unclear Pronoun",
                explanation="The pronoun may not clearly refer to one exact noun.",
                suggestion="Replace the pronoun with the exact actor, object, or component name.",
                severity="High",
                replacement="[exact noun]",
                issue_type="unclear_pronoun",
                source="nlp",
            ))
    return issues


def detect_double_negatives(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    negatives = [(w, s, e) for w, s, e in tokenize_with_offsets(sentence) if w.lower() in DOUBLE_NEGATIVE_TERMS]
    if len(negatives) >= 2:
        first = negatives[0]
        last = negatives[-1]
        issues.append(make_issue(
            term=sentence[first[1]:last[2]],
            start=offset + first[1],
            end=offset + last[2],
            category="Double Negative",
            explanation="The sentence contains multiple negative terms and may confuse the meaning.",
            suggestion="Rewrite the sentence using one clear negative or a positive form.",
            severity="High",
            replacement="",
            issue_type="double_negative",
            source="nlp",
        ))
    return issues


def get_word_meanings(word: str, limit: int = 3) -> List[Dict[str, str]]:
    meanings = []
    used = set()
    for syn in wn.synsets(word.lower()):
        definition = syn.definition().strip()
        lemmas = ", ".join([l.replace("_", " ") for l in syn.lemma_names()[:4]])
        key = (definition, lemmas)
        if key in used:
            continue
        used.add(key)
        meanings.append({
            "sense": syn.name(),
            "definition": definition,
            "lemmas": lemmas,
        })
        if len(meanings) >= limit:
            break
    return meanings


def detect_multiple_meanings(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    for word, start, end in tokenize_with_offsets(sentence):
        lower = word.lower()
        synsets = wn.synsets(lower)
        if len(synsets) >= 3 and (lower in MULTI_MEANING_WORDS or len(synsets) >= 6):
            meanings = get_word_meanings(lower, 3)
            if meanings:
                issues.append(make_issue(
                    term=word,
                    start=offset + start,
                    end=offset + end,
                    category="Multiple Meanings",
                    explanation="This word can have multiple meanings and may confuse the reader.",
                    suggestion="Replace it with a more precise term if needed.",
                    severity="Medium",
                    replacement="",
                    issue_type="multiple_meaning",
                    source="wordnet",
                    meanings=meanings,
                ))
    return issues


def detect_ambiguous_structures(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    patterns = [
        (r"\band/or\b", "The phrase 'and/or' is ambiguous.", "Choose either 'and' or 'or'."),
        (r"\bif\b.*\bthen\b.*\band\b.*\bor\b", "The logical condition may be ambiguous.", "Split the logic into smaller clear statements."),
        (r"\bunless\b.*\bexcept\b", "The exception logic may be hard to interpret.", "Rewrite the condition in a simpler form."),
    ]
    for pattern, explanation, suggestion in patterns:
        for m in re.finditer(pattern, sentence, flags=re.IGNORECASE):
            issues.append(make_issue(
                term=m.group(0),
                start=offset + m.start(),
                end=offset + m.end(),
                category="Ambiguous Structure",
                explanation=explanation,
                suggestion=suggestion,
                severity="High",
                replacement="",
                issue_type="ambiguous_structure",
                source="rules",
            ))

    token_count = len(tokenize_with_offsets(sentence))
    comma_count = sentence.count(",")
    if token_count >= 28 or comma_count >= 3:
        issues.append(make_issue(
            term=sentence,
            start=offset,
            end=offset + len(sentence),
            category="Confusing Construction",
            explanation="The sentence is long or nested, which makes the meaning harder to interpret.",
            suggestion="Split it into shorter requirement sentences.",
            severity="Medium",
            replacement="",
            issue_type="confusing_construction",
            source="rules",
        ))
    return issues


def detect_wrong_verb_forms(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    tokens = tokenize_with_offsets(sentence)
    words = [w for w, _, _ in tokens]
    if not words:
        return issues

    tags = pos_tag(words)

    for i in range(len(tags) - 1):
        word, tag = tags[i]
        next_word, next_tag = tags[i + 1]
        lw = word.lower()

        if lw in {"he", "she", "it"} and next_tag == "VB":
            tok = tokens[i + 1]
            issues.append(make_issue(
                term=tok[0],
                start=offset + tok[1],
                end=offset + tok[2],
                category="Wrong Verb Form",
                explanation=f"The verb form after '{word}' may be incorrect.",
                suggestion="Use the correct singular verb form.",
                severity="High",
                replacement="",
                issue_type="wrong_verb_form",
                source="nlp",
            ))

        if lw == "they" and next_tag == "VBZ":
            tok = tokens[i + 1]
            issues.append(make_issue(
                term=tok[0],
                start=offset + tok[1],
                end=offset + tok[2],
                category="Wrong Verb Form",
                explanation="The plural subject 'they' may need a plural or base verb form.",
                suggestion="Use the correct plural verb form.",
                severity="High",
                replacement="",
                issue_type="wrong_verb_form",
                source="nlp",
            ))

        if lw in {"shall", "should", "must", "can", "may", "will"} and next_tag in {"VBD", "VBN"}:
            tok = tokens[i + 1]
            issues.append(make_issue(
                term=tok[0],
                start=offset + tok[1],
                end=offset + tok[2],
                category="Wrong Verb Form",
                explanation="A modal verb is usually followed by the base form of a verb.",
                suggestion="Use the base form of the verb after the modal.",
                severity="Medium",
                replacement="",
                issue_type="wrong_verb_form",
                source="nlp",
            ))
    return issues


def detect_surface_issues(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    stripped = sentence.strip()
    if not stripped:
        return issues

    if stripped[0].islower():
        issues.append(make_issue(
            term=stripped[0],
            start=offset,
            end=offset + 1,
            category="Casing",
            explanation="The sentence starts with a lowercase letter.",
            suggestion="Start the sentence with an uppercase letter.",
            severity="Low",
            replacement=stripped[0].upper(),
            issue_type="casing",
            source="rules",
        ))

    if stripped[-1] not in ".!?":
        issues.append(make_issue(
            term=stripped[-1],
            start=offset + len(sentence.rstrip()) - 1,
            end=offset + len(sentence.rstrip()),
            category="Punctuation",
            explanation="The sentence may be missing ending punctuation.",
            suggestion="End the sentence with a period.",
            severity="Low",
            replacement=".",
            issue_type="punctuation",
            source="rules",
        ))

    return issues


def detect_spelling_fallback(text: str, existing_spans: List[Tuple[int, int]], offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    for word, start, end in tokenize_with_offsets(text):
        lower = word.lower()
        if len(lower) <= 2 or lower.isdigit():
            continue
        overlap = any((offset + start) < e and (offset + end) > s for s, e in existing_spans)
        if overlap:
            continue
        if lower not in SPELL:
            suggestions = list(SPELL.candidates(lower))[:3]
            if suggestions:
                issues.append(make_issue(
                    term=word,
                    start=offset + start,
                    end=offset + end,
                    category="Spelling",
                    explanation="Possible spelling mistake.",
                    suggestion="Use one of the suggested spellings.",
                    severity="High",
                    replacement=suggestions[0],
                    issue_type="spelling",
                    source="spellchecker",
                ))
    return issues


def detect_languagetool_issues(text: str) -> List[Dict[str, Any]]:
    issues = []
    try:
        matches = get_language_tool().check(text)
    except Exception:
        return issues

    for match in matches:
        start = int(getattr(match, "offset", 0))
        length = int(getattr(match, "error_length", 0))
        end = start + length
        category = str(getattr(match, "category", "") or "Grammar")
        replacements = [str(r) for r in getattr(match, "replacements", [])[:5]]
        message = str(getattr(match, "message", "Language issue detected."))
        issue_type_raw = str(getattr(match, "rule_issue_type", "")).lower()
        rule_text = f"{category} {issue_type_raw} {str(getattr(match, 'rule_id', ''))}".lower()

        if "misspelling" in rule_text or "typo" in rule_text:
            issue_type = "spelling"
            category_name = "Spelling"
            severity = "High"
        elif "punct" in rule_text:
            issue_type = "punctuation"
            category_name = "Punctuation"
            severity = "Medium"
        elif "style" in rule_text:
            issue_type = "style"
            category_name = "Style"
            severity = "Medium"
        elif "casing" in rule_text:
            issue_type = "casing"
            category_name = "Casing"
            severity = "Low"
        else:
            issue_type = "grammar"
            category_name = "Grammar"
            severity = "High"

        issues.append(make_issue(
            term=text[start:end],
            start=start,
            end=end,
            category=category_name,
            explanation=message,
            suggestion=("Suggestions: " + ", ".join(replacements)) if replacements else message,
            severity=severity,
            replacement=replacements[0] if replacements else "",
            issue_type=issue_type,
            source="languagetool",
        ))
    return issues


def detect_sentence(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    issues.extend(detect_keyword_terms(sentence, offset))
    issues.extend(detect_repeated_words(sentence, offset))
    issues.extend(detect_unclear_pronouns(sentence, offset))
    issues.extend(detect_double_negatives(sentence, offset))
    issues.extend(detect_multiple_meanings(sentence, offset))
    issues.extend(detect_ambiguous_structures(sentence, offset))
    issues.extend(detect_wrong_verb_forms(sentence, offset))
    issues.extend(detect_surface_issues(sentence, offset))
    return issues


def detect(text: str) -> List[Dict[str, Any]]:
    text = normalize_text(text)
    if not text:
        return []

    issues = []
    issues.extend(detect_languagetool_issues(text))

    for sentence, offset in split_into_sentences(text):
        issues.extend(detect_sentence(sentence, offset))

    issues = dedupe_issues(issues)
    spans = [(x["start"], x["end"]) for x in issues]
    issues.extend(detect_spelling_fallback(text, spans, 0))
    return dedupe_issues(issues)


def analyze_text(text: str) -> Dict[str, Any]:
    text = normalize_text(text)
    if not text:
        return {
            "sentences": [],
            "all_issues": [],
            "corrected_text": "",
            "summary": "No text provided.",
            "stats": {"grammar": 0, "ambiguity": 0, "spelling": 0, "total": 0},
        }

    all_issues = detect(text)

    sentence_results = []
    for sentence, offset in split_into_sentences(text):
        local_issues = []
        for issue in all_issues:
            if issue["start"] >= offset and issue["end"] <= offset + len(sentence):
                copied = dict(issue)
                copied["start"] = copied["start"] - offset
                copied["end"] = copied["end"] - offset
                local_issues.append(copied)
        sentence_results.append({
            "sentence": sentence,
            "issues": local_issues,
        })

    try:
        corrected_text = lt_correct(text, get_language_tool().check(text))
    except Exception:
        corrected_text = text

    stats = {
        "grammar": sum(1 for x in all_issues if x["issue_type"] in {"grammar", "wrong_verb_form", "punctuation", "casing", "style", "repeated_word"}),
        "ambiguity": sum(1 for x in all_issues if x["issue_type"] in {"ambiguity", "unclear_pronoun", "multiple_meaning", "ambiguous_structure", "confusing_construction", "double_negative"}),
        "spelling": sum(1 for x in all_issues if x["issue_type"] == "spelling"),
        "total": len(all_issues),
    }

    return {
        "sentences": sentence_results,
        "all_issues": all_issues,
        "corrected_text": corrected_text,
        "summary": f"Detected {len(all_issues)} issue(s).",
        "stats": stats,
    }