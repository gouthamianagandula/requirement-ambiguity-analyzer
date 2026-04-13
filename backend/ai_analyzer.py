import json
import os
import time
from typing import Any, Dict, List

import requests

from backend.ai_prompts import SYSTEM_PROMPT


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Simple in-memory cache for repeated text
CACHE: Dict[str, Dict[str, Any]] = {}


def _safe_json_load(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        return {
            "issues": [],
            "corrected_text": "",
            "rewrite": ""
        }


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
Analyze the following user text carefully.

Return JSON only.

Quality requirements:
- corrected_text must fix grammar, punctuation, and spelling.
- rewrite must be more professional, more precise, and less ambiguous.
- Do not simply copy the original sentence unless it is already correct.
- For weak requirement wording, improve rewrite into clearer professional requirement language.
- For ambiguous wording, explain the problem in issues and give better alternatives.
- For vague words, suggest clearer replacements.
- For unclear pronouns, try to suggest a clearer noun or clearer rewrite.
- For sentence ambiguity, add alternatives that express different possible meanings clearly.
- Keep issues useful and specific.
- Keep term short and exact.
- Do not use placeholders like [exact noun].
- Use direct and natural English.

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

    # Ultra-fast repeated result
    if text in CACHE:
        return CACHE[text]

    # Skip unnecessary AI call for extremely short text
    if len(text.split()) < 2:
        return _success_result(text, [], text, text)

    if not GEMINI_API_KEY:
        return _error_result(text, "RAA configuration error: GEMINI_API_KEY is missing.")

    prompt = _build_prompt(text)

    payload = {
        "system_instruction": {
            "parts": [
                {"text": SYSTEM_PROMPT}
            ]
        },
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.8,
            "topK": 20,
            "maxOutputTokens": 800,
            "responseMimeType": "application/json"
        }
    }

    # Reduced retry count for faster response
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
                timeout=25
            )

            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])

                if not candidates:
                    return _error_result(text, "RAA could not generate a response.")

                parts = candidates[0].get("content", {}).get("parts", [])
                raw_text = "".join(part.get("text", "") for part in parts).strip()

                json_text = _extract_json_block(raw_text)
                if not json_text:
                    return _error_result(
                        text,
                        "RAA could not read the AI response correctly. Please try again."
                    )

                parsed = _safe_json_load(json_text)

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

                if corrected_text.strip() == text.strip() and issues:
                    # Keep rewrite stronger even when corrected text is close to original
                    rewrite = rewrite if rewrite.strip() else corrected_text

                if rewrite.strip() == text.strip() and corrected_text.strip() != text.strip():
                    rewrite = corrected_text

                return _success_result(text, issues, corrected_text, rewrite)

            # Temporary service overloads
            if response.status_code in {429, 500, 502, 503, 504}:
                last_error = f"Temporary service issue: {response.status_code}"
                if attempt < len(retry_delays):
                    time.sleep(delay)
                    continue
                return _error_result(
                    text,
                    "RAA is currently busy. Please try again in a moment."
                )

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