import json
import os
from typing import Any, Dict, List

from openai import OpenAI

from backend.ai_prompts import SYSTEM_PROMPT


client = OpenAI()


ANALYSIS_SCHEMA: Dict[str, Any] = {
    "name": "ambiguity_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "term": {"type": "string"},
                        "issue_type": {"type": "string"},
                        "category": {"type": "string"},
                        "explanation": {"type": "string"},
                        "suggestion": {"type": "string"},
                        "replacement": {"type": "string"},
                        "severity": {"type": "string"},
                        "alternatives": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "meanings": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": [
                        "term",
                        "issue_type",
                        "category",
                        "explanation",
                        "suggestion",
                        "replacement",
                        "severity",
                        "alternatives",
                        "meanings"
                    ],
                    "additionalProperties": False
                }
            },
            "corrected_text": {"type": "string"},
            "rewrite": {"type": "string"}
        },
        "required": ["issues", "corrected_text", "rewrite"],
        "additionalProperties": False
    }
}


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


def analyze_with_ai(text: str) -> Dict[str, Any]:
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    user_prompt = f"""
Analyze this text dynamically and return structured JSON.

Text:
{text}
"""

    try:
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "json_schema": ANALYSIS_SCHEMA
                }
            }
        )

        output_text = getattr(response, "output_text", "") or ""
        parsed = _safe_json_load(output_text)

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