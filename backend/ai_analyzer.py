import json
import os
from typing import Any, Dict, List

from groq import Groq

from backend.ai_prompts import SYSTEM_PROMPT


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

CACHE: Dict[str, Dict[str, Any]] = {}


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


def _extract_json_block(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end < start:
        return ""

    return text[start:end + 1]


def _build_prompt(text: str) -> str:
    return f"""
Return ONLY valid JSON.
Do not add markdown.
Do not add triple backticks.
Do not add explanation outside JSON.

Required JSON format:
{{
  "issues": [
    {{
      "term": "",
      "issue_type": "",
      "category": "",
      "explanation": "",
      "suggestion": "",
      "replacement": "",
      "severity": "",
      "alternatives": [],
      "meanings": []
    }}
  ],
  "corrected_text": "",
  "rewrite": ""
}}

Rules:
- corrected_text must fix grammar, punctuation, and spelling.
- rewrite must be clearer, more professional, and less ambiguous.
- If no issue exists, return empty issues array.
- Keep "term" short and exact.
- Do not use placeholders like [exact noun].
- Analyze the actual text dynamically.

User text:
{text}
""".strip()


def _error_result(text: str, message: str) -> Dict[str, Any]:
    return {
        "issues": [],
        "corrected_text": text,
        "rewrite": text,
        "error": message
    }


def _success_result(
    text: str,
    issues: List[Dict[str, Any]],
    corrected_text: str,
    rewrite: str
) -> Dict[str, Any]:
    result = {
        "issues": issues,
        "corrected_text": corrected_text,
        "rewrite": rewrite,
        "error": ""
    }
    CACHE[text] = result
    return result


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
        client = Groq(api_key=GROQ_API_KEY)

        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": _build_prompt(text)
                }
            ]
        )

        raw_text = completion.choices[0].message.content or ""
        json_text = _extract_json_block(raw_text)

        if not json_text:
            return _error_result(
                text,
                "RAA could not read the AI response correctly. Please try again."
            )

        parsed = _safe_json_load(json_text)
        if not isinstance(parsed, dict):
            return _error_result(
                text,
                "RAA could not parse the AI response. Please try again."
            )

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
        return _error_result(text, f"RAA analysis failed: {str(e)}")