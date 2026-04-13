import json
import os
import re
import time
from typing import Any, Dict, List

import requests

from backend.ai_prompts import SYSTEM_PROMPT


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

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


def _extract_raw_text_from_response(data: Dict[str, Any]) -> str:
    candidates = data.get("candidates", [])
    if not candidates:
        return ""

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        return ""

    return "".join(part.get("text", "") for part in parts).strip()


def _extract_json_candidates(raw_text: str) -> List[str]:
    candidates: List[str] = []

    if not raw_text:
        return candidates

    candidates.append(raw_text.strip())

    fenced = re.findall(r"```json\s*(\{.*?\})\s*```", raw_text, flags=re.DOTALL)
    candidates.extend([item.strip() for item in fenced if item.strip()])

    fenced_any = re.findall(r"```\s*(\{.*?\})\s*```", raw_text, flags=re.DOTALL)
    candidates.extend([item.strip() for item in fenced_any if item.strip()])

    first = raw_text.find("{")
    last = raw_text.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidates.append(raw_text[first:last + 1].strip())

    # unique preserve order
    seen = set()
    unique_candidates = []
    for item in candidates:
      if item not in seen:
        seen.add(item)
        unique_candidates.append(item)

    return unique_candidates


def _try_parse_analysis(raw_text: str) -> Dict[str, Any] | None:
    for candidate in _extract_json_candidates(raw_text):
        parsed = _safe_json_load(candidate)
        if isinstance(parsed, dict):
            return parsed
    return None


def _salvage_from_plain_text(text: str, raw_text: str) -> Dict[str, Any]:
    """
    Fallback when Gemini returns plain text instead of JSON.
    We still return something useful instead of failing.
    """
    corrected_text = text
    rewrite = text
    issues: List[Dict[str, Any]] = []

    corrected_match = re.search(
        r"(corrected_text|corrected sentence)\s*[:\-]\s*(.+)",
        raw_text,
        flags=re.IGNORECASE
    )
    rewrite_match = re.search(
        r"(rewrite|professional rewrite)\s*[:\-]\s*(.+)",
        raw_text,
        flags=re.IGNORECASE
    )

    if corrected_match:
        corrected_text = corrected_match.group(2).strip()

    if rewrite_match:
        rewrite = rewrite_match.group(2).strip()

    # if still same, use first non-empty lines from raw output
    lines = [line.strip(" -*\t") for line in raw_text.splitlines() if line.strip()]
    useful_lines = [line for line in lines if len(line.split()) >= 3]

    if corrected_text == text and useful_lines:
        corrected_text = useful_lines[0]

    if rewrite == text and len(useful_lines) > 1:
        rewrite = useful_lines[1]
    elif rewrite == text and useful_lines:
        rewrite = useful_lines[0]

    if corrected_text == text and rewrite == text:
        # still nothing usable, return soft fallback
        return {
            "issues": [],
            "corrected_text": text,
            "rewrite": text,
            "error": "RAA could not generate a structured analysis. Please try again."
        }

    return {
        "issues": issues,
        "corrected_text": corrected_text,
        "rewrite": rewrite,
        "error": ""
    }


def analyze_with_ai(text: str) -> Dict[str, Any]:
    text = (text or "").strip()

    if not text:
        return _error_result("", "Text is empty.")

    if text in CACHE:
        return CACHE[text]

    if len(text.split()) < 2:
        return _success_result(text, [], text, text)

    if not GEMINI_API_KEY:
        return _error_result(text, "RAA configuration error: GEMINI_API_KEY is missing.")

    payload = {
        "system_instruction": {
            "parts": [
                {"text": SYSTEM_PROMPT}
            ]
        },
        "contents": [
            {
                "parts": [
                    {"text": _build_prompt(text)}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.05,
            "topP": 0.8,
            "topK": 20,
            "maxOutputTokens": 700,
            "responseMimeType": "application/json"
        }
    }

    retry_delays = [1, 2]
    last_error = ""

    for attempt, delay in enumerate(retry_delays, start=1):
        try:
            response = requests.post(
                GEMINI_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-goog-api-key": GEMINI_API_KEY
                },
                json=payload,
                timeout=20
            )

            if response.status_code == 200:
                data = response.json()
                raw_text = _extract_raw_text_from_response(data)

                parsed = _try_parse_analysis(raw_text)

                if parsed is None:
                    fallback = _salvage_from_plain_text(text, raw_text)
                    if not fallback.get("error"):
                        return _success_result(
                            text,
                            fallback.get("issues", []),
                            fallback.get("corrected_text", text),
                            fallback.get("rewrite", text)
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

            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = f"Temporary service issue: {response.status_code}"
                if attempt < len(retry_delays):
                    time.sleep(delay)
                    continue
                return _error_result(text, "RAA is currently busy. Please try again in a moment.")

            return _error_result(
                text,
                f"RAA analysis failed: {response.status_code} - {response.text}"
            )

        except requests.Timeout:
            last_error = "RAA request timed out."
            if attempt < len(retry_delays):
                time.sleep(delay)
                continue
            return _error_result(text, "RAA request timed out. Please try again.")

        except Exception as e:
            return _error_result(text, f"RAA analysis failed: {str(e)}")

    return _error_result(text, last_error or "RAA request failed.")