import json
import os
from typing import Any, Dict, List

import requests


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


def _safe_json_load(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        return {
            "issues": [],
            "corrected_text": "",
            "rewrite": ""
        }


def _normalize_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "term": str(issue.get("term", "")),
        "issue_type": str(issue.get("issue_type", "style")),
        "category": str(issue.get("category", "Style")),
        "explanation": str(issue.get("explanation", "")),
        "suggestion": str(issue.get("suggestion", "")),
        "replacement": str(issue.get("replacement", "")),
        "severity": str(issue.get("severity", "Medium")),
        "alternatives": issue.get("alternatives", []) or [],
        "meanings": issue.get("meanings", []) or [],
    }


def _extract_json_block(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start:end + 1]


def analyze_with_ai(text: str) -> Dict[str, Any]:
    if not GEMINI_API_KEY:
        return {
            "issues": [],
            "corrected_text": text,
            "rewrite": text,
            "error": "GEMINI_API_KEY is missing in Render environment variables."
        }

    prompt = f"""
You are an advanced English ambiguity and writing-quality analyzer.

Analyze ANY user-provided sentence or paragraph.

Detect:
- grammar errors
- spelling mistakes
- punctuation mistakes
- wrong verb forms
- unclear pronouns
- ambiguous sentence structures
- misplaced modifiers
- confusing sentence constructions
- vague words
- multiple-meaning words
- double negatives

Rules:
- Do NOT hardcode known example sentences.
- Analyze the actual input dynamically.
- Do NOT return placeholders like [exact noun].
- Use natural English.
- If a sentence is grammatically correct but ambiguous, keep corrected_text close to the original and improve rewrite.
- If the input is a paragraph, analyze all sentences and produce one corrected_text and one rewrite for the full paragraph.
- Return JSON only.

Return exactly this JSON shape:
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

Text:
{text}
"""

    try:
        response = requests.post(
            GEMINI_URL,
            headers={
                "Content-Type": "application/json",
                "X-goog-api-key": GEMINI_API_KEY
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2
                }
            },
            timeout=60
        )

        if response.status_code != 200:
            return {
                "issues": [],
                "corrected_text": text,
                "rewrite": text,
                "error": f"Gemini API failed: {response.status_code} - {response.text}"
            }

        data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return {
                "issues": [],
                "corrected_text": text,
                "rewrite": text,
                "error": "Gemini returned no candidates."
            }

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return {
                "issues": [],
                "corrected_text": text,
                "rewrite": text,
                "error": "Gemini returned empty content."
            }

        raw_text = "".join(part.get("text", "") for part in parts).strip()
        json_text = _extract_json_block(raw_text)

        if not json_text:
            return {
                "issues": [],
                "corrected_text": text,
                "rewrite": text,
                "error": f"Gemini did not return valid JSON. Raw output: {raw_text[:500]}"
            }

        parsed = _safe_json_load(json_text)

        issues: List[Dict[str, Any]] = [
            _normalize_issue(issue) for issue in parsed.get("issues", [])
        ]

        corrected_text = str(parsed.get("corrected_text", text)).strip() or text
        rewrite = str(parsed.get("rewrite", corrected_text)).strip() or corrected_text

        return {
            "issues": issues,
            "corrected_text": corrected_text,
            "rewrite": rewrite,
            "error": ""
        }

    except Exception as e:
        return {
            "issues": [],
            "corrected_text": text,
            "rewrite": text,
            "error": str(e)
        }