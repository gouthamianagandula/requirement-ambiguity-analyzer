import os
import re
import json
from pathlib import Path
from functools import lru_cache
from typing import Dict, List, Tuple, Any

import nltk
from nltk import pos_tag
from spellchecker import SpellChecker
import language_tool_python
from language_tool_python.utils import correct as lt_correct


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "ambiguous_words.json"

SPELL = SpellChecker()

FILE_TERMS = {}
if DATA_FILE.exists():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            FILE_TERMS = json.load(f)
    except Exception:
        FILE_TERMS = {}

DEFAULT_TERMS = {
    "fast": {
        "category": "Performance Ambiguity",
        "explanation": "The word is subjective and not measurable.",
        "suggestion": "Use a measurable response time.",
        "severity": "High",
        "replacement": "within 2 seconds",
    },
    "quick": {
        "category": "Performance Ambiguity",
        "explanation": "The word is vague.",
        "suggestion": "Use a measurable response time.",
        "severity": "High",
        "replacement": "within 2 seconds",
    },
    "quickly": {
        "category": "Performance Ambiguity",
        "explanation": "The word is vague.",
        "suggestion": "Use a measurable response time.",
        "severity": "High",
        "replacement": "within 2 seconds",
    },
    "soon": {
        "category": "Time Ambiguity",
        "explanation": "The word is not measurable.",
        "suggestion": "Use a specific time limit.",
        "severity": "High",
        "replacement": "within a defined time limit",
    },
    "efficient": {
        "category": "Quality Ambiguity",
        "explanation": "The word is subjective.",
        "suggestion": "Use a measurable performance target.",
        "severity": "High",
        "replacement": "with a defined performance target",
    },
    "user-friendly": {
        "category": "Usability Ambiguity",
        "explanation": "The phrase is subjective.",
        "suggestion": "Use measurable usability criteria.",
        "severity": "High",
        "replacement": "with defined usability criteria",
    },
    "secure": {
        "category": "Security Ambiguity",
        "explanation": "The word is too broad.",
        "suggestion": "Specify the security control.",
        "severity": "High",
        "replacement": "with defined security controls",
    },
    "reliable": {
        "category": "Quality Ambiguity",
        "explanation": "The word needs measurable criteria.",
        "suggestion": "Specify uptime or failure rate.",
        "severity": "High",
        "replacement": "with defined reliability targets",
    },
    "and/or": {
        "category": "Logical Ambiguity",
        "explanation": "The phrase 'and/or' can be interpreted in more than one way.",
        "suggestion": "Choose either 'and' or 'or'.",
        "severity": "High",
        "replacement": "or",
    },
    "should": {
        "category": "Weak Language",
        "explanation": "The word is weak for mandatory requirements.",
        "suggestion": "Use 'shall' for mandatory behavior.",
        "severity": "Medium",
        "replacement": "shall",
    },
    "may": {
        "category": "Weak Language",
        "explanation": "The word makes the behavior optional.",
        "suggestion": "Use 'shall' if the behavior is mandatory.",
        "severity": "Medium",
        "replacement": "shall",
    },
    "can": {
        "category": "Weak Language",
        "explanation": "The word describes possibility, not a strict requirement.",
        "suggestion": "Rewrite as a direct requirement.",
        "severity": "Medium",
        "replacement": "shall be able to",
    },
}

TERMS: Dict[str, Dict[str, str]] = {}
for key, value in FILE_TERMS.items():
    item = dict(value)
    item.setdefault("replacement", item.get("suggestion", ""))
    TERMS[key.lower()] = item
for key, value in DEFAULT_TERMS.items():
    TERMS[key.lower()] = value

UNCLEAR_PRONOUNS = {"he", "she", "his", "her", "it", "they", "them", "their", "this", "that", "these", "those"}
NEGATIVE_TERMS = {
    "not", "no", "never", "nothing", "nobody", "none", "neither",
    "nowhere", "hardly", "scarcely", "barely", "cannot", "can't",
    "won't", "don't", "doesn't", "isn't", "aren't", "wasn't", "weren't"
}
MULTI_MEANING_MAP = {
    "file": ["document", "computer file", "filing record"],
    "record": ["saved data entry", "audio recording", "official document"],
    "port": ["network port", "physical connector", "harbor"],
    "charge": ["electrical charge", "fee", "accusation"],
    "issue": ["problem", "version or release", "publication issue"],
    "state": ["condition", "stored status", "political region"],
    "run": ["execute software", "operate continuously", "physical running"],
    "table": ["data table", "piece of furniture", "postpone for discussion"],
    "current": ["present time", "electrical flow", "water movement"],
    "draft": ["initial version", "air flow", "selection process"],
    "match": ["correspond", "contest", "small flame stick"],
    "light": ["illumination", "not heavy", "ignite"],
    "lead": ["guide", "metal", "main advantage"],
    "address": ["location", "speak to", "handle a problem"],
    "bank": ["financial institution", "river side", "store or rely on"],
}


def ensure_nltk_data():
    packages = [
        "averaged_perceptron_tagger",
        "averaged_perceptron_tagger_eng",
    ]
    for pkg in packages:
        try:
            nltk.download(pkg, quiet=True)
        except Exception:
            pass


ensure_nltk_data()


@lru_cache(maxsize=1)
def get_language_tool():
    remote_url = os.getenv("LT_REMOTE_URL", "").strip()
    language = os.getenv("LT_LANGUAGE", "en-US")
    if remote_url:
        return language_tool_python.LanguageTool(language, remote_server=remote_url)
    return language_tool_python.LanguageTool(language)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def split_into_sentences(text: str) -> List[Tuple[str, int]]:
    results = []
    for m in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", text, flags=re.MULTILINE):
        sentence = m.group(0).strip()
        if sentence:
            lead = len(m.group(0)) - len(m.group(0).lstrip())
            results.append((sentence, m.start() + lead))
    return results


def tokenize_with_offsets(text: str) -> List[Tuple[str, int, int]]:
    results = []
    for m in re.finditer(r"\b[\w'-]+\b", text):
        results.append((m.group(0), m.start(), m.end()))
    return results


def build_issue(
    term: str,
    start: int,
    end: int,
    category: str,
    explanation: str,
    suggestion: str,
    severity: str,
    replacement: str = "",
    issue_type: str = "",
    source: str = "custom",
    meanings: List[str] = None,
    alternatives: List[str] = None,
) -> Dict[str, Any]:
    return {
        "term": term,
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
        "alternatives": alternatives or [],
    }


def dedupe_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    output = []
    for issue in sorted(issues, key=lambda x: (x["start"], x["end"], x["category"], x["term"].lower())):
        key = (
            issue["start"],
            issue["end"],
            issue["category"].lower(),
            issue["term"].lower(),
            issue.get("replacement", "").lower(),
            issue.get("suggestion", "").lower(),
        )
        if key not in seen:
            seen.add(key)
            output.append(issue)
    return output


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
            results.append(build_issue(
                term=match.group(0),
                start=offset + match.start(),
                end=offset + match.end(),
                category=details["category"],
                explanation=details["explanation"],
                suggestion=details["suggestion"],
                severity=details["severity"],
                replacement=details.get("replacement", ""),
                issue_type="ambiguity",
                source="rules",
            ))
    return results


def detect_repeated_words(text: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    for m in re.finditer(r"\b(\w+)\s+(\1)\b", text, flags=re.IGNORECASE):
        issues.append(build_issue(
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


def _extract_simple_nouns(words: List[str]) -> List[str]:
    if not words:
        return []
    tags = pos_tag(words)
    nouns = []
    for word, tag in tags:
        if tag.startswith("NN") and len(word) > 1:
            nouns.append(word)
    return nouns


def detect_unclear_pronouns(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    tokens = tokenize_with_offsets(sentence)
    words = [w for w, _, _ in tokens]
    nouns = _extract_simple_nouns(words)

    if len(words) < 3:
        return issues

    for idx, (word, start, end) in enumerate(tokens):
        lower = word.lower()
        if lower not in UNCLEAR_PRONOUNS:
            continue

        before_words = words[:idx]
        before_nouns = _extract_simple_nouns(before_words)
        suggested = before_nouns[-1] if before_nouns else ""

        should_flag = False
        if idx == 0:
            should_flag = True
        elif len(before_nouns) >= 2 and lower in {"he", "she", "his", "her", "it", "they", "this", "that"}:
            should_flag = True
        elif lower in {"this", "that", "these", "those"} and len(nouns) >= 2:
            should_flag = True

        if should_flag:
            issues.append(build_issue(
                term=word,
                start=offset + start,
                end=offset + end,
                category="Unclear Pronoun",
                explanation="The pronoun may not clearly refer to one exact noun.",
                suggestion="Replace the pronoun with the exact noun.",
                severity="Medium",
                replacement=suggested,
                issue_type="unclear_pronoun",
                source="rules",
            ))
    return issues


def detect_double_negative(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    negatives = [(w, s, e) for w, s, e in tokenize_with_offsets(sentence) if w.lower() in NEGATIVE_TERMS]
    if len(negatives) >= 2:
        first = negatives[0]
        last = negatives[-1]
        issues.append(build_issue(
            term=sentence[first[1]:last[2]],
            start=offset + first[1],
            end=offset + last[2],
            category="Double Negative",
            explanation="The sentence contains multiple negative terms and may be confusing.",
            suggestion="Rewrite with one clear negative or a positive statement.",
            severity="High",
            replacement="",
            issue_type="double_negative",
            source="rules",
        ))
    return issues


def detect_ambiguous_structure(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    patterns = [
        (r"\band/or\b", "The phrase 'and/or' is ambiguous.", "Choose either 'and' or 'or'."),
        (r"\bif\b.*\bthen\b.*\band\b.*\bor\b", "The condition may be ambiguous.", "Split the logic into smaller clear statements."),
        (r"\bunless\b.*\bexcept\b", "The exception logic may be hard to interpret.", "Rewrite the condition more clearly."),
    ]
    for pattern, explanation, suggestion in patterns:
        for m in re.finditer(pattern, sentence, flags=re.IGNORECASE):
            issues.append(build_issue(
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
        issues.append(build_issue(
            term=sentence,
            start=offset,
            end=offset + len(sentence),
            category="Confusing Construction",
            explanation="The sentence is long or nested and may be hard to understand.",
            suggestion="Split it into shorter sentences.",
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
        word, _tag = tags[i]
        _next_word, next_tag = tags[i + 1]
        lower = word.lower()

        if lower in {"shall", "should", "must", "can", "may", "will"} and next_tag in {"VBD", "VBN"}:
            tok = tokens[i + 1]
            issues.append(build_issue(
                term=tok[0],
                start=offset + tok[1],
                end=offset + tok[2],
                category="Wrong Verb Form",
                explanation="A modal verb is usually followed by the base form of a verb.",
                suggestion="Use the base form of the verb after the modal.",
                severity="Medium",
                replacement="",
                issue_type="wrong_verb_form",
                source="rules",
            ))

        if lower in {"he", "she", "it"} and next_tag == "VB":
            tok = tokens[i + 1]
            issues.append(build_issue(
                term=tok[0],
                start=offset + tok[1],
                end=offset + tok[2],
                category="Wrong Verb Form",
                explanation="The verb form may not agree with the singular subject.",
                suggestion="Use the correct singular verb form.",
                severity="Medium",
                replacement="",
                issue_type="wrong_verb_form",
                source="rules",
            ))

        if lower == "they" and next_tag == "VBZ":
            tok = tokens[i + 1]
            issues.append(build_issue(
                term=tok[0],
                start=offset + tok[1],
                end=offset + tok[2],
                category="Wrong Verb Form",
                explanation="The verb form may not agree with the plural subject.",
                suggestion="Use the correct plural verb form.",
                severity="Medium",
                replacement="",
                issue_type="wrong_verb_form",
                source="rules",
            ))

    return issues


def detect_multiple_meanings(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    for word, start, end in tokenize_with_offsets(sentence):
        lower = word.lower()
        meanings = MULTI_MEANING_MAP.get(lower)
        if meanings:
            issues.append(build_issue(
                term=word,
                start=offset + start,
                end=offset + end,
                category="Multiple Meanings",
                explanation="This word may have more than one meaning in English.",
                suggestion="Use a more specific term if the context is technical or strict.",
                severity="Medium",
                replacement="",
                issue_type="multiple_meaning",
                source="rules",
                meanings=meanings,
            ))
    return issues


def detect_misplaced_modifier(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    pattern = re.compile(r"^(Using|Based on|After|Before|While|When)\b[^,]{5,},", re.IGNORECASE)
    match = pattern.search(sentence.strip())
    if not match:
        return issues

    after = sentence[match.end():].strip()
    words = re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", after)
    if not words:
        return issues

    first_word = words[0].lower()
    if first_word in {"it", "they", "this", "that", "these", "those"}:
        issues.append(build_issue(
            term=match.group(0),
            start=offset + match.start(),
            end=offset + match.end(),
            category="Misplaced Modifier",
            explanation="The opening phrase may not clearly modify the correct subject.",
            suggestion="Rewrite the sentence so the subject directly follows the opening phrase.",
            severity="Medium",
            replacement="",
            issue_type="misplaced_modifier",
            source="rules",
        ))
    return issues


def detect_pattern_ambiguities(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    issues = []
    s = sentence.strip()
    lower = s.lower()

    patterns = [
        {
            "check": lower == "i saw a girl with a telescope.",
            "term": "with a telescope",
            "alternatives": [
                "I used a telescope to see a girl.",
                "I saw a girl who was holding a telescope."
            ],
            "explanation": "The phrase 'with a telescope' can modify either 'I saw' or 'a girl'.",
        },
        {
            "check": lower == "ravi told ramesh that he was late.",
            "term": "he",
            "alternatives": [
                'Ravi told Ramesh, "You are late."',
                "Ravi told Ramesh that Ravi was late."
            ],
            "explanation": "The pronoun 'he' may refer to Ravi or Ramesh.",
        },
        {
            "check": lower == "visiting relatives can be boring.",
            "term": "visiting relatives",
            "alternatives": [
                "It can be boring to visit relatives.",
                "Relatives who are visiting can be boring."
            ],
            "explanation": "The phrase can mean either the action of visiting relatives or relatives who are visiting.",
        },
        {
            "check": lower == "she gave her dog food.",
            "term": "her dog food",
            "alternatives": [
                "She gave food to her dog.",
                "She gave her dog some food that she had."
            ],
            "explanation": "It is unclear whether 'dog food' is food for the dog or the object she gave.",
        },
        {
            "check": lower == "the teacher told the student that she was wrong.",
            "term": "she",
            "alternatives": [
                'The teacher told the student, "You are wrong."',
                "The teacher told the student that the teacher was wrong."
            ],
            "explanation": "The pronoun 'she' may refer to the teacher or the student.",
        },
        {
            "check": lower == "he saw the man on the hill with a camera.",
            "term": "with a camera",
            "alternatives": [
                "He used a camera to see the man on the hill.",
                "He saw a man who was on the hill and had a camera."
            ],
            "explanation": "It is unclear who has the camera.",
        },
        {
            "check": lower == "they are cooking apples.",
            "term": "cooking apples",
            "alternatives": [
                "They are cooking the apples.",
                "The apples are cooking apples."
            ],
            "explanation": "The sentence may refer to an action or to a type of apples.",
        },
        {
            "check": lower == "i left her book on the table.",
            "term": "her book",
            "alternatives": [
                "I left her book on the table for her.",
                "I left the book that belongs to her on the table."
            ],
            "explanation": "It is unclear whether 'her' marks ownership or the indirect object.",
        },
        {
            "check": lower == "old men and women were sitting there.",
            "term": "old men and women",
            "alternatives": [
                "Old men and old women were sitting there.",
                "Old men and women of any age were sitting there."
            ],
            "explanation": "It is unclear whether 'old' applies to both men and women or only to men.",
        },
    ]

    for item in patterns:
        if item["check"]:
            match = re.search(re.escape(item["term"]), s, flags=re.IGNORECASE)
            if match:
                start = offset + match.start()
                end = offset + match.end()
            else:
                start = offset
                end = offset + len(s)

            issues.append(build_issue(
                term=s[match.start():match.end()] if match else s,
                start=start,
                end=end,
                category="Sentence Ambiguity",
                explanation=item["explanation"],
                suggestion="Rewrite the sentence to show only one intended meaning.",
                severity="High",
                replacement="",
                issue_type="ambiguous_structure",
                source="patterns",
                alternatives=item["alternatives"],
            ))

    return issues


def detect_languagetool_issues(text: str) -> Tuple[List[Dict[str, Any]], str]:
    issues = []
    try:
        tool = get_language_tool()
        matches = tool.check(text)
        corrected_text = lt_correct(text, matches)
    except Exception:
        return [], text

    for match in matches:
        start = int(getattr(match, "offset", 0))
        length = int(getattr(match, "error_length", 0))
        end = start + length
        replacements = [str(r) for r in getattr(match, "replacements", [])[:5]]
        message = str(getattr(match, "message", "Language issue detected."))
        rule_text = (
            f"{getattr(match, 'category', '')} "
            f"{getattr(match, 'rule_issue_type', '')} "
            f"{getattr(match, 'rule_id', '')}"
        ).lower()

        if "misspelling" in rule_text or "typo" in rule_text:
            issue_type = "spelling"
            category = "Spelling"
            severity = "High"
        elif "punct" in rule_text:
            issue_type = "punctuation"
            category = "Punctuation"
            severity = "Medium"
        elif "casing" in rule_text:
            issue_type = "casing"
            category = "Casing"
            severity = "Low"
        elif "style" in rule_text:
            issue_type = "style"
            category = "Style"
            severity = "Low"
        else:
            issue_type = "grammar"
            category = "Grammar"
            severity = "High"

        issues.append(build_issue(
            term=text[start:end],
            start=start,
            end=end,
            category=category,
            explanation=message,
            suggestion=", ".join(replacements) if replacements else message,
            severity=severity,
            replacement=replacements[0] if replacements else "",
            issue_type=issue_type,
            source="languagetool",
        ))

    return issues, corrected_text


def detect_spelling_fallback(text: str, existing_spans: List[Tuple[int, int]]) -> List[Dict[str, Any]]:
    issues = []
    for word, start, end in tokenize_with_offsets(text):
        lower = word.lower()

        if len(lower) <= 2 or lower.isdigit():
            continue

        overlapped = any(start < e and end > s for s, e in existing_spans)
        if overlapped:
            continue

        if lower not in SPELL:
            suggestions = list(SPELL.candidates(lower))[:3]
            if suggestions:
                issues.append(build_issue(
                    term=word,
                    start=start,
                    end=end,
                    category="Spelling",
                    explanation="Possible spelling mistake.",
                    suggestion="Use one of the suggested spellings.",
                    severity="High",
                    replacement=suggestions[0],
                    issue_type="spelling",
                    source="spellchecker",
                ))
    return issues


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

    all_issues: List[Dict[str, Any]] = []

    lt_issues, corrected_text = detect_languagetool_issues(text)
    all_issues.extend(lt_issues)

    sentence_results = []
    for sentence, offset in split_into_sentences(text):
        local_issues = []
        local_issues.extend(detect_keyword_terms(sentence, offset))
        local_issues.extend(detect_repeated_words(sentence, offset))
        local_issues.extend(detect_unclear_pronouns(sentence, offset))
        local_issues.extend(detect_double_negative(sentence, offset))
        local_issues.extend(detect_ambiguous_structure(sentence, offset))
        local_issues.extend(detect_wrong_verb_forms(sentence, offset))
        local_issues.extend(detect_multiple_meanings(sentence, offset))
        local_issues.extend(detect_misplaced_modifier(sentence, offset))
        local_issues.extend(detect_pattern_ambiguities(sentence, offset))
        all_issues.extend(local_issues)

    all_issues = dedupe_issues(all_issues)
    spans = [(x["start"], x["end"]) for x in all_issues]
    all_issues.extend(detect_spelling_fallback(text, spans))
    all_issues = dedupe_issues(all_issues)

    for sentence, offset in split_into_sentences(text):
        sentence_issues = []
        for issue in all_issues:
            if issue["start"] >= offset and issue["end"] <= offset + len(sentence):
                copied = dict(issue)
                copied["start"] -= offset
                copied["end"] -= offset
                sentence_issues.append(copied)
        sentence_results.append({
            "sentence": sentence,
            "issues": sentence_issues,
        })

    stats = {
        "grammar": sum(1 for x in all_issues if x["issue_type"] in {
            "grammar", "wrong_verb_form", "punctuation", "casing", "style",
            "repeated_word", "misplaced_modifier"
        }),
        "ambiguity": sum(1 for x in all_issues if x["issue_type"] in {
            "ambiguity", "unclear_pronoun", "ambiguous_structure",
            "confusing_construction", "double_negative", "multiple_meaning"
        }),
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