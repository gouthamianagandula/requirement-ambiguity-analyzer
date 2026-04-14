import json
import os
import re
from typing import Any, Dict, List

from groq import Groq


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192").strip()

CACHE: Dict[str, Dict[str, Any]] = {}


def _get_client() -> Groq:
    return Groq(api_key=GROQ_API_KEY)


def _safe_json_load(text: str) -> Dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:
        return None


def _normalize_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _normalize_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _normalize_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    issue_type = _normalize_string(issue.get("issue_type"), "style")
    category = _normalize_string(issue.get("category"), "Style")
    severity = _normalize_string(issue.get("severity"), "Medium")

    allowed_issue_types = {
        "grammar",
        "spelling",
        "punctuation",
        "wrong_verb_form",
        "unclear_pronoun",
        "ambiguous_structure",
        "misplaced_modifier",
        "confusing_construction",
        "vague_word",
        "vague_time",
        "vague_quantity",
        "unspecified_actor",
        "double_negative",
        "multiple_meaning",
        "style",
    }

    if issue_type not in allowed_issue_types:
        issue_type = "style"

    if severity not in {"Low", "Medium", "High"}:
        severity = "Medium"

    return {
        "term": _normalize_string(issue.get("term")),
        "issue_type": issue_type,
        "category": category,
        "explanation": _normalize_string(issue.get("explanation")),
        "suggestion": _normalize_string(issue.get("suggestion")),
        "replacement": _normalize_string(issue.get("replacement")),
        "severity": severity,
        "alternatives": _normalize_list(issue.get("alternatives")),
        "meanings": _normalize_list(issue.get("meanings")),
    }


def _error_result(text: str, message: str) -> Dict[str, Any]:
    return {
        "issues": [],
        "corrected_text": text,
        "rewrite": text,
        "error": message,
    }


def _success_result(
    text: str,
    issues: List[Dict[str, Any]],
    corrected_text: str,
    rewrite: str,
) -> Dict[str, Any]:
    result = {
        "issues": issues,
        "corrected_text": corrected_text,
        "rewrite": rewrite,
        "error": "",
    }
    CACHE[text] = result
    return result


def _extract_json_candidates(raw_text: str) -> List[str]:
    candidates: List[str] = []

    if not raw_text:
        return candidates

    cleaned = raw_text.strip()
    candidates.append(cleaned)

    fenced_json = re.findall(r"```json\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    candidates.extend([item.strip() for item in fenced_json if item.strip()])

    fenced_any = re.findall(r"```\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    candidates.extend([item.strip() for item in fenced_any if item.strip()])

    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidates.append(cleaned[first:last + 1].strip())

    unique: List[str] = []
    seen = set()
    for item in candidates:
        if item not in seen:
            seen.add(item)
            unique.append(item)

    return unique


def _try_parse_analysis(raw_text: str) -> Dict[str, Any] | None:
    for candidate in _extract_json_candidates(raw_text):
        parsed = _safe_json_load(candidate)
        if isinstance(parsed, dict):
            return parsed
    return None


def _salvage_from_plain_text(original_text: str, raw_text: str) -> Dict[str, Any]:
    corrected_text = original_text
    rewrite = original_text
    issues: List[Dict[str, Any]] = []

    corrected_match = re.search(
        r"(corrected_text|corrected sentence)\s*[:\-]\s*(.+)",
        raw_text,
        flags=re.IGNORECASE,
    )
    rewrite_match = re.search(
        r"(rewrite|professional rewrite)\s*[:\-]\s*(.+)",
        raw_text,
        flags=re.IGNORECASE,
    )

    if corrected_match:
        corrected_text = corrected_match.group(2).strip()

    if rewrite_match:
        rewrite = rewrite_match.group(2).strip()

    lines = [line.strip(" -*\t") for line in raw_text.splitlines() if line.strip()]
    useful_lines = [line for line in lines if len(line.split()) >= 3]

    if corrected_text == original_text and useful_lines:
        corrected_text = useful_lines[0]

    if rewrite == original_text and len(useful_lines) > 1:
        rewrite = useful_lines[1]
    elif rewrite == original_text and useful_lines:
        rewrite = useful_lines[0]

    if corrected_text == original_text and rewrite == original_text:
        return _error_result(
            original_text,
            "RAA could not generate a structured analysis. Please try again.",
        )

    return {
        "issues": issues,
        "corrected_text": corrected_text,
        "rewrite": rewrite,
        "error": "",
    }


def _build_prompt(text: str) -> str:
    return f"""
You are an expert requirement ambiguity analyzer and writing assistant.

Analyze the text deeply and return ONLY valid JSON.
Do not add markdown.
Do not add triple backticks.
Do not add explanation outside JSON.

TEXT:
{text}

You must detect:
1. grammar errors
2. spelling mistakes
3. punctuation mistakes
4. unclear pronouns
5. ambiguous sentence structure
6. vague words
7. vague time expressions
8. vague quantity expressions
9. unspecified actors
10. wrong verb forms
11. double negatives
12. multiple-meaning words
13. confusing constructions
14. misplaced modifiers

Required JSON format:
{{
  "issues": [
    {{
      "term": "exact word or short phrase only",
      "issue_type": "grammar | spelling | punctuation | wrong_verb_form | unclear_pronoun | ambiguous_structure | misplaced_modifier | confusing_construction | vague_word | vague_time | vague_quantity | unspecified_actor | double_negative | multiple_meaning | style",
      "category": "short readable category",
      "explanation": "clear explanation",
      "suggestion": "clear fix instruction",
      "replacement": "better replacement text",
      "severity": "Low | Medium | High",
      "alternatives": ["alternative 1", "alternative 2"],
      "meanings": ["meaning 1", "meaning 2"]
    }}
  ],
  "corrected_text": "grammar-corrected text",
  "rewrite": "professional clear rewrite"
}}

Rules:
- Return valid JSON only.
- corrected_text must fix grammar, punctuation, spelling, and obvious clarity problems.
- rewrite must be more professional, clearer, and less ambiguous.
- Keep "term" short and exact.
- Do not use placeholders like [exact noun].
- Do not return the same sentence unless it is already correct.
- If ambiguity exists, explain it properly.
- If no issues exist, return an empty issues list.

Now return the JSON.
""".strip()


def analyze_with_ai(text: str) -> Dict[str, Any]:
    text = (text or "").strip()

    if not text:
        return _error_result("", "Text is empty.")

    if text in CACHE:
        return CACHE[text]

    if len(text.split()) < 2:
        return _success_result(text, [], text, text)

    if not GROQ_API_KEY:
        return _error_result(text, "RAA configuration error: GROQ_API_KEY is missing.")

    try:
        client = _get_client()

        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": "You return only valid JSON and follow the user's requested schema exactly.",
                },
                {
                    "role": "user",
                    "content": _build_prompt(text),
                },
            ],
        )

        raw_text = completion.choices[0].message.content or ""
        parsed = _try_parse_analysis(raw_text)

        if parsed is None:
            fallback = _salvage_from_plain_text(text, raw_text)
            if not fallback.get("error"):
                return _success_result(
                    text,
                    fallback.get("issues", []),
                    fallback.get("corrected_text", text),
                    fallback.get("rewrite", text),
                )
            return _error_result(text, fallback["error"])

        issues_raw = parsed.get("issues", [])
        if not isinstance(issues_raw, list):
            issues_raw = []

        issues: List[Dict[str, Any]] = []
        for issue in issues_raw:
            if isinstance(issue, dict):
                normalized = _normalize_issue(issue)
                if normalized["term"] or normalized["explanation"]:
                    issues.append(normalized)

        corrected_text = _normalize_string(parsed.get("corrected_text"), text) or text
        rewrite = _normalize_string(parsed.get("rewrite"), corrected_text) or corrected_text

        if rewrite.strip() == text.strip() and corrected_text.strip() != text.strip():
            rewrite = corrected_text

        return _success_result(text, issues, corrected_text, rewrite)

    except Exception as e:
        return _error_result(text, f"RAA AI failed: {str(e)}")