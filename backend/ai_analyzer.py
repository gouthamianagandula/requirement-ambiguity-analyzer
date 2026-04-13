import os
import json
import requests

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={GEMINI_API_KEY}"


def analyze_with_ai(text: str):
    prompt = f"""
You are an advanced English analyzer.

Analyze the text and return STRICT JSON only.

Text:
{text}

Return:
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
"""

    try:
        response = requests.post(
            GEMINI_URL,
            headers={
                "Content-Type": "application/json"
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ]
            }
        )

        data = response.json()

        # 🔥 extract AI text
        ai_text = data["candidates"][0]["content"]["parts"][0]["text"]

        # 🔥 extract JSON from response
        start = ai_text.find("{")
        end = ai_text.rfind("}") + 1
        json_text = ai_text[start:end]

        parsed = json.loads(json_text)

        return parsed

    except Exception as e:
        return {
            "issues": [],
            "corrected_text": text,
            "rewrite": text,
            "error": str(e)
        }