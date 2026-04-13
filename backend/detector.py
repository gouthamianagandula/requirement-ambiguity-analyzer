import os
import re
import json
from pathlib import Path
from functools import lru_cache
from typing import Dict, List, Tuple, Any

import spacy
from spellchecker import SpellChecker
import language_tool_python
from language_tool_python.utils import correct as lt_correct


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "ambiguous_words.json"

SPELL = SpellChecker()

FILE_TERMS: Dict[str, Dict[str, str]] = {}
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
        "explanation": "The phrase can be interpreted in more than one way.",
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

NEGATIVE_TERMS = {
    "not", "no", "never", "nothing", "nobody", "none", "neither",
    "nowhere", "hardly", "scarcely", "barely", "cannot", "can't",
    "won't", "don't", "doesn't", "isn't", "aren't", "wasn't", "weren't",
}

PRONOUNS = {"he", "she", "his", "her", "it", "they", "them", "their", "this", "that", "these", "those"}

MULTI_MEANING_WORDS = {
    "file": ["document", "computer file", "filing record"],
    "record": ["saved data entry", "audio recording", "official document"],
    "port": ["network port", "physical connector", "harbor"],
    "charge": ["electrical charge", "fee", "accusation"],
    "issue": ["problem", "version or release", "publication issue"],
    "state": ["condition", "stored status", "political region"],
    "run": ["execute software", "operate continuously", "physical activity"],
    "table": ["data table", "piece of furniture", "postpone for discussion"],
    "current": ["present time", "electrical flow", "water movement"],
    "draft": ["initial version", "air flow", "selection process"],
    "match": ["correspond", "contest", "small flame stick"],
    "light": ["illumination", "not heavy", "ignite"],
    "lead": ["guide", "metal", "main advantage"],
    "address": ["location", "speak to", "handle a problem"],
    "bank": ["financial institution", "river bank", "store or rely on"],
    "case": ["instance", "container", "legal matter"],
    "block": ["prevent", "group", "physical piece"],
}

ATTACHMENT_PREPOSITIONS = {"with", "by", "in", "on", "at", "near", "for", "from"}
LEADING_MODIFIER_WORDS = {"using", "based", "after", "before", "while", "when", "having"}

SUBORDINATE_MARKERS = {"because", "although", "while", "when", "if", "unless", "whereas", "since"}

# -----------------------------
# Load NLP tools
# -----------------------------


@lru_cache(maxsize=1)
def get_nlp():
    model_name = os.getenv("SPACY_MODEL", "en_core_web_sm")
    try:
        return spacy.load(model_name)
    except Exception:
        # fallback so app still runs, but real ambiguity features need the model
        nlp = spacy.blank("en")
        if "sentencizer" not in nlp.pipe_names:
            nlp.add_pipe("sentencizer")
        return nlp


@lru_cache(maxsize=1)
def get_language_tool():
    remote_url = os.getenv("LT_REMOTE_URL", "").strip()
    language = os.getenv("LT_LANGUAGE", "en-US")
    if remote_url:
        return language_tool_python.LanguageTool(language, remote_server=remote_url)
    return language_tool_python.LanguageTool(language)


# -----------------------------
# Helpers
# -----------------------------


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
    return [(m.group(0), m.start(), m.end()) for m in re.finditer(r"\b[\w'-]+\b", text)]


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


def _char_span_from_token(doc, token, offset: int) -> Tuple[int, int]:
    return offset + token.idx, offset + token.idx + len(token.text)


def _sentence_subject_nouns(sent_doc) -> List[str]:
    nouns = []
    for token in sent_doc:
        if token.dep_ in {"nsubj", "nsubjpass"} and token.pos_ in {"NOUN", "PROPN", "PRON"}:
            nouns.append(token.text)
    return nouns


# -----------------------------
# General detectors
# -----------------------------


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


def detect_multiple_meanings_spacy(sent_doc, offset: int) -> List[Dict[str, Any]]:
    issues = []
    for token in sent_doc:
        lower = token.text.lower()
        meanings = MULTI_MEANING_WORDS.get(lower)
        if meanings and token.pos_ in {"NOUN", "VERB", "ADJ"}:
            start, end = _char_span_from_token(sent_doc, token, offset)
            issues.append(build_issue(
                term=token.text,
                start=start,
                end=end,
                category="Multiple Meanings",
                explanation="This word may have more than one meaning in English.",
                suggestion="Use a more specific term if the context is technical or strict.",
                severity="Medium",
                replacement="",
                issue_type="multiple_meaning",
                source="spacy",
                meanings=meanings,
            ))
    return issues


def detect_unclear_pronouns_spacy(sent_doc, offset: int) -> List[Dict[str, Any]]:
    issues = []
    nouns_before = [t for t in sent_doc if t.pos_ in {"NOUN", "PROPN"}]

    for token in sent_doc:
        lower = token.text.lower()
        if lower not in PRONOUNS or token.pos_ != "PRON":
            continue

        antecedent_candidates = []
        for prev in sent_doc:
            if prev.i >= token.i:
                break
            if prev.pos_ in {"NOUN", "PROPN"}:
                antecedent_candidates.append(prev)

        if len(antecedent_candidates) >= 2:
            start, end = _char_span_from_token(sent_doc, token, offset)
            suggestion = "Replace the pronoun with the exact noun."
            replacement = antecedent_candidates[-1].text
            issues.append(build_issue(
                term=token.text,
                start=start,
                end=end,
                category="Unclear Pronoun",
                explanation="The pronoun may refer to more than one earlier noun.",
                suggestion=suggestion,
                severity="High",
                replacement=replacement,
                issue_type="unclear_pronoun",
                source="spacy",
                alternatives=[
                    f"Replace '{token.text}' with '{cand.text}'." for cand in antecedent_candidates[-2:]
                ],
            ))
        elif lower in {"this", "that", "these", "those"} and len(nouns_before) >= 2:
            start, end = _char_span_from_token(sent_doc, token, offset)
            issues.append(build_issue(
                term=token.text,
                start=start,
                end=end,
                category="Unclear Pronoun",
                explanation="This pointing word may not clearly refer to one exact item.",
                suggestion="Replace it with the exact noun.",
                severity="Medium",
                replacement=nouns_before[-1].text,
                issue_type="unclear_pronoun",
                source="spacy",
            ))
    return issues


def detect_attachment_ambiguity_spacy(sent_doc, offset: int) -> List[Dict[str, Any]]:
    issues = []
    text = sent_doc.text

    for token in sent_doc:
        if token.dep_ != "prep" or token.text.lower() not in ATTACHMENT_PREPOSITIONS:
            continue

        pobj = None
        for child in token.children:
            if child.dep_ == "pobj":
                pobj = child
                break
        if pobj is None:
            continue

        head = token.head
        earlier_nouns = [t for t in sent_doc if t.i < token.i and t.pos_ in {"NOUN", "PROPN"}]
        earlier_verbs = [t for t in sent_doc if t.i < token.i and t.pos_ == "VERB"]

        if head.pos_ in {"NOUN", "PROPN"} and earlier_verbs:
            phrase_start = token.idx
            phrase_end = pobj.idx + len(pobj.text)
            phrase = text[phrase_start:phrase_end]

            noun_head = head.text
            verb_head = earlier_verbs[-1].lemma_
            alt1 = f"The phrase '{phrase}' describes '{noun_head}'."
            alt2 = f"The phrase '{phrase}' describes the action '{verb_head}'."

            issues.append(build_issue(
                term=phrase,
                start=offset + phrase_start,
                end=offset + phrase_end,
                category="Sentence Ambiguity",
                explanation="This prepositional phrase may attach to more than one part of the sentence.",
                suggestion="Rewrite the sentence so the phrase modifies only one intended part.",
                severity="High",
                replacement="",
                issue_type="ambiguous_structure",
                source="spacy",
                alternatives=[alt1, alt2],
            ))
    return issues


def detect_gerund_or_compound_ambiguity_spacy(sent_doc, offset: int) -> List[Dict[str, Any]]:
    issues = []
    text = sent_doc.text

    # Examples like "Visiting relatives can be boring" / "cooking apples"
    if len(sent_doc) >= 2:
        first = sent_doc[0]
        second = sent_doc[1]

        if first.tag_ == "VBG" and second.pos_ in {"NOUN", "PROPN"}:
            phrase = f"{first.text} {second.text}"
            start = offset + first.idx
            end = offset + second.idx + len(second.text)
            issues.append(build_issue(
                term=phrase,
                start=start,
                end=end,
                category="Sentence Ambiguity",
                explanation="This opening phrase may refer either to an action or to a noun phrase.",
                suggestion="Rewrite the sentence so only one meaning is possible.",
                severity="High",
                replacement="",
                issue_type="ambiguous_structure",
                source="spacy",
                alternatives=[
                    f"It can be difficult to {first.lemma_} {second.text}.",
                    f"{second.text.capitalize()} who are {first.text.lower()} can be difficult."
                ],
            ))

    for token in sent_doc:
        if token.dep_ == "compound" and token.head.pos_ == "NOUN":
            phrase = f"{token.text} {token.head.text}"
            start = offset + token.idx
            end = offset + token.head.idx + len(token.head.text)

            if token.tag_ == "VBG":
                issues.append(build_issue(
                    term=phrase,
                    start=start,
                    end=end,
                    category="Sentence Ambiguity",
                    explanation="This phrase may describe an action or a type of thing.",
                    suggestion="Rewrite it to show the intended meaning.",
                    severity="Medium",
                    replacement="",
                    issue_type="ambiguous_structure",
                    source="spacy",
                    alternatives=[
                        f"The sentence may mean '{token.text.lower()} the {token.head.text.lower()}'.",
                        f"The sentence may mean '{token.text.lower()} {token.head.text.lower()}' as a type."
                    ],
                ))
    return issues


def detect_misplaced_modifier_spacy(sent_doc, offset: int) -> List[Dict[str, Any]]:
    issues = []
    text = sent_doc.text.strip()

    if "," not in text:
        return issues

    first_chunk = text.split(",", 1)[0].strip()
    first_words = first_chunk.split()
    if not first_words:
        return issues

    first_word = first_words[0].lower()
    if first_word not in LEADING_MODIFIER_WORDS:
        return issues

    subject_nouns = _sentence_subject_nouns(sent_doc)
    if not subject_nouns:
        return issues

    # If leading modifier is followed by a pronoun subject, often unclear
    for token in sent_doc:
        if token.dep_ in {"nsubj", "nsubjpass"} and token.pos_ == "PRON":
            start = offset + text.find(first_chunk)
            end = start + len(first_chunk)
            issues.append(build_issue(
                term=first_chunk,
                start=start,
                end=end,
                category="Misplaced Modifier",
                explanation="The opening phrase may not clearly modify the correct subject.",
                suggestion="Place the intended subject directly after the opening phrase.",
                severity="Medium",
                replacement="",
                issue_type="misplaced_modifier",
                source="spacy",
            ))
            break

    return issues


def detect_confusing_construction_spacy(sent_doc, offset: int) -> List[Dict[str, Any]]:
    text = sent_doc.text
    token_count = len([t for t in sent_doc if not t.is_space])
    comma_count = text.count(",")
    subordinate_count = sum(1 for t in sent_doc if t.text.lower() in SUBORDINATE_MARKERS)
    conjunction_count = sum(1 for t in sent_doc if t.dep_ == "cc")

    if token_count >= 30 or comma_count >= 3 or subordinate_count >= 2 or conjunction_count >= 3:
        return [build_issue(
            term=text,
            start=offset,
            end=offset + len(text),
            category="Confusing Construction",
            explanation="The sentence is long or structurally dense and may be hard to understand.",
            suggestion="Split it into shorter sentences or clauses.",
            severity="Medium",
            replacement="",
            issue_type="confusing_construction",
            source="spacy",
        )]
    return []


def detect_double_negative(sentence: str, offset: int = 0) -> List[Dict[str, Any]]:
    negatives = [(w, s, e) for w, s, e in tokenize_with_offsets(sentence) if w.lower() in NEGATIVE_TERMS]
    if len(negatives) < 2:
        return []
    first = negatives[0]
    last = negatives[-1]
    return [build_issue(
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
    )]


def detect_wrong_verb_forms_spacy(sent_doc, offset: int) -> List[Dict[str, Any]]:
    issues = []

    for token in sent_doc:
        if token.dep_ not in {"ROOT", "conj", "auxpass", "ccomp", "xcomp"}:
            continue

        children = list(token.children)
        subjects = [c for c in children if c.dep_ in {"nsubj", "nsubjpass"}]
        if not subjects:
            continue

        subj = subjects[0]
        subj_lower = subj.text.lower()

        if subj_lower in {"he", "she", "it"} and token.tag_ == "VB":
            start, end = _char_span_from_token(sent_doc, token, offset)
            issues.append(build_issue(
                term=token.text,
                start=start,
                end=end,
                category="Wrong Verb Form",
                explanation="The verb may not agree with the singular subject.",
                suggestion="Use the correct singular verb form.",
                severity="Medium",
                replacement="",
                issue_type="wrong_verb_form",
                source="spacy",
            ))

        if subj_lower == "they" and token.tag_ == "VBZ":
            start, end = _char_span_from_token(sent_doc, token, offset)
            issues.append(build_issue(
                term=token.text,
                start=start,
                end=end,
                category="Wrong Verb Form",
                explanation="The verb may not agree with the plural subject.",
                suggestion="Use the correct plural verb form.",
                severity="Medium",
                replacement="",
                issue_type="wrong_verb_form",
                source="spacy",
            ))

    return issues


def detect_languagetool_issues(text: str) -> Tuple[List[Dict[str, Any]], str]:
    try:
        tool = get_language_tool()
        matches = tool.check(text)
        corrected_text = lt_correct(text, matches)
    except Exception:
        return [], text

    issues = []
    for match in matches:
        start = int(getattr(match, "offset", 0))
        end = start + int(getattr(match, "error_length", 0))
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
        if any(start < e and end > s for s, e in existing_spans):
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


def choose_sentence_alternative(local_issues: List[Dict[str, Any]], sentence_text: str) -> str:
    # Prefer clear sentence-level rewrites when ambiguity detector has good alternatives
    for issue in local_issues:
        alternatives = issue.get("alternatives") or []
        if alternatives:
            first = alternatives[0]
            # Keep only natural, direct alternatives
            if "may mean" not in first.lower() and "describes" not in first.lower():
                return first
    return sentence_text


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

    lt_issues, lt_corrected = detect_languagetool_issues(text)
    all_issues.extend(lt_issues)

    nlp = get_nlp()
    doc = nlp(text)

    sentence_results = []
    for sent in doc.sents:
        sent_text = sent.text.strip()
        if not sent_text:
            continue

        # Find sentence offset in original text
        offset = sent.start_char
        local_issues: List[Dict[str, Any]] = []

        local_issues.extend(detect_keyword_terms(sent_text, offset))
        local_issues.extend(detect_repeated_words(sent_text, offset))
        local_issues.extend(detect_double_negative(sent_text, offset))
        local_issues.extend(detect_multiple_meanings_spacy(sent, offset))
        local_issues.extend(detect_unclear_pronouns_spacy(sent, offset))
        local_issues.extend(detect_attachment_ambiguity_spacy(sent, offset))
        local_issues.extend(detect_gerund_or_compound_ambiguity_spacy(sent, offset))
        local_issues.extend(detect_misplaced_modifier_spacy(sent, offset))
        local_issues.extend(detect_confusing_construction_spacy(sent, offset))
        local_issues.extend(detect_wrong_verb_forms_spacy(sent, offset))

        all_issues.extend(local_issues)
        sentence_results.append({
            "sentence": sent_text,
            "offset": offset,
            "issues": local_issues,
        })

    all_issues = dedupe_issues(all_issues)
    spans = [(x["start"], x["end"]) for x in all_issues]
    all_issues.extend(detect_spelling_fallback(text, spans))
    all_issues = dedupe_issues(all_issues)

    # Build corrected sentence text:
    # start from LT-corrected text, but if a sentence has a strong ambiguity alternative, use it.
    lt_sentences = split_into_sentences(lt_corrected) if lt_corrected else split_into_sentences(text)
    corrected_parts = []

    for idx, s in enumerate(sentence_results):
        local_issues = [
            issue for issue in all_issues
            if issue["start"] >= s["offset"] and issue["end"] <= s["offset"] + len(s["sentence"])
        ]
        if idx < len(lt_sentences):
            base_sentence = lt_sentences[idx][0]
        else:
            base_sentence = s["sentence"]
        corrected_parts.append(choose_sentence_alternative(local_issues, base_sentence))

    corrected_text = " ".join(part.strip() for part in corrected_parts if part.strip())

    # Normalize local issue offsets for per-sentence display
    normalized_sentence_results = []
    for s in sentence_results:
        local = []
        for issue in all_issues:
            if issue["start"] >= s["offset"] and issue["end"] <= s["offset"] + len(s["sentence"]):
                copied = dict(issue)
                copied["start"] -= s["offset"]
                copied["end"] -= s["offset"]
                local.append(copied)
        normalized_sentence_results.append({
            "sentence": s["sentence"],
            "issues": local,
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
        "sentences": normalized_sentence_results,
        "all_issues": all_issues,
        "corrected_text": corrected_text,
        "summary": f"Detected {len(all_issues)} issue(s).",
        "stats": stats,
    }