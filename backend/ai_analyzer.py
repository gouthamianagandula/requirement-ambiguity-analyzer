import os
from typing import List, Literal

from google import genai
from pydantic import BaseModel, Field

from backend.ai_prompts import SYSTEM_PROMPT


class AnalysisIssue(BaseModel):
    term: str = Field(description="Exact problematic word or short phrase.")
    issue_type: Literal[
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
    ] = Field(description="Type of issue.")
    category: str = Field(description="Readable category name.")
    explanation: str = Field(description="Why this is a problem.")
    suggestion: str = Field(description="How to improve it.")
    replacement: str = Field(description="Direct replacement if applicable.")
    severity: Literal["Low", "Medium", "High"] = Field(description="Issue severity.")
    alternatives: List[str] = Field(default_factory=list, description="Clear alternative rewrites.")
    meanings: List[str] = Field(default_factory=list, description="Possible meanings if ambiguous.")


class AnalysisResult(BaseModel):
    issues: List[AnalysisIssue] = Field(default_factory=list)
    corrected_text: str = Field(description="Grammar-corrected text.")
    rewrite: str = Field(description="Professional and clearer rewrite.")


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()

# SDK reads GEMINI_API_KEY from environment automatically
client = genai.Client()

CACHE: dict[str, dict] = {}


def _error_result(text: str, message: str) -> dict:
    return {
        "issues": [],
        "corrected_text": text,
        "rewrite": text,
        "error": message,
    }


def _build_prompt(text: str) -> str:
    return f"""
Analyze the following user text carefully.

You must:
- detect ambiguity, grammar, punctuation, spelling, unclear pronouns, vague wording, confusing structure, wrong verb forms, and double negatives
- return useful issues
- improve corrected_text
- make rewrite more professional and clearer
- not repeat the original unless it is already correct
- keep "term" short and exact
- avoid placeholders like [exact noun]

User text:
{text}
""".strip()


def analyze_with_ai(text: str) -> dict:
    text = (text or "").strip()

    if not text:
        return _error_result("", "Text is empty.")

    if text in CACHE:
        return CACHE[text]

    if len(text.split()) < 2:
        result = {
            "issues": [],
            "corrected_text": text,
            "rewrite": text,
            "error": "",
        }
        CACHE[text] = result
        return result

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=_build_prompt(text),
            config={
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
                "response_json_schema": AnalysisResult.model_json_schema(),
                "temperature": 0.1,
                "top_p": 0.8,
                "top_k": 20,
                "max_output_tokens": 700,
            },
        )

        parsed = AnalysisResult.model_validate_json(response.text)

        corrected_text = parsed.corrected_text.strip() or text
        rewrite = parsed.rewrite.strip() or corrected_text

        # keep rewrite useful
        if rewrite == text and corrected_text != text:
            rewrite = corrected_text

        result = {
            "issues": [issue.model_dump() for issue in parsed.issues],
            "corrected_text": corrected_text,
            "rewrite": rewrite,
            "error": "",
        }

        CACHE[text] = result
        return result

    except Exception as e:
        return _error_result(text, f"RAA analysis failed: {str(e)}")