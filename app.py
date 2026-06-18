import os
import json
import requests
from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup
import anthropic

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

EVALUATION_PROMPT = """You are a content moderation and editorial quality reviewer for a community storytelling platform.

Evaluate the following story against two criteria:

## 1. Safety & Moderation
Check for violations including:
- Hate speech, discrimination, or harassment targeting any group
- Explicit sexual content
- Graphic or gratuitous violence
- Promotion of self-harm or dangerous activities
- Dangerous misinformation presented as fact
- Spam, excessive self-promotion, or off-topic content
- Personal attacks or doxxing

## 2. Tone & Voice
The platform expects a **professional and informative** tone:
- Clear, well-structured writing (coherent intro, body, conclusion)
- Authoritative but accessible language
- Factual claims supported by context or evidence
- No excessive slang, profanity, or inflammatory language
- Relevant and focused content that stays on topic
- Respectful and constructive framing

## Story to evaluate:
Title: {title}

Content:
{content}

## Response format
Respond ONLY with a valid JSON object in exactly this structure:
{{
  "safety": {{
    "score": <integer 0-100>,
    "verdict": "<Pass|Flag|Reject>",
    "issues": [<list of specific issues found, or empty list>],
    "summary": "<1-2 sentence summary of safety assessment>"
  }},
  "tone": {{
    "score": <integer 0-100>,
    "verdict": "<Pass|Flag|Reject>",
    "issues": [<list of specific tone issues found, or empty list>],
    "summary": "<1-2 sentence summary of tone assessment>"
  }},
  "overall": {{
    "verdict": "<Approved|Needs Review|Rejected>",
    "recommendation": "<1-2 sentences on what action to take>"
  }},
  "extracted_title": "<the story title you identified, or empty string if none>"
}}

Scoring guide:
- 85-100: Excellent, no concerns
- 70-84: Good, minor or no issues
- 50-69: Moderate issues that should be reviewed
- 0-49: Serious violations

Verdict rules:
- Pass: score >= 70
- Flag: score 50-69
- Reject: score < 50

Overall verdict rules:
- Approved: both safety and tone are Pass
- Needs Review: either is Flag (and neither is Reject)
- Rejected: either is Reject
"""


def fetch_story(url: str) -> tuple[str, str]:
    """Fetch URL and extract title + main text content."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; StoryEvaluator/1.0)"
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract title
    title = ""
    if soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)
    elif soup.find("title"):
        title = soup.find("title").get_text(strip=True)

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                     "advertisement", "form", "button"]):
        tag.decompose()

    # Try semantic content containers first
    content = ""
    for selector in ["article", "main", "[role='main']", ".content",
                     ".post-content", ".entry-content", ".story-content",
                     ".article-body", "#content"]:
        el = soup.select_one(selector)
        if el:
            content = el.get_text(separator="\n", strip=True)
            break

    if not content:
        content = soup.get_text(separator="\n", strip=True)

    # Trim to ~8000 chars to stay within reasonable token limits
    content = content[:8000]
    return title, content


def evaluate_story(title: str, content: str) -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = EVALUATION_PROMPT.format(title=title, content=content)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/evaluate", methods=["POST"])
def evaluate():
    data = request.get_json()
    url = (data or {}).get("url", "").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400

    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY is not configured on the server"}), 500

    try:
        title, content = fetch_story(url)
    except requests.exceptions.Timeout:
        return jsonify({"error": "The page took too long to load. Please try again."}), 408
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Could not reach that URL. Check the address and try again."}), 400
    except requests.exceptions.HTTPError as e:
        return jsonify({"error": f"The page returned an error: {e.response.status_code}"}), 400

    if not content or len(content) < 50:
        return jsonify({"error": "Could not extract readable text from that URL."}), 400

    try:
        result = evaluate_story(title, content)
    except json.JSONDecodeError:
        return jsonify({"error": "Evaluation returned an unexpected format. Please try again."}), 500
    except anthropic.APIError as e:
        return jsonify({"error": f"AI evaluation failed: {str(e)}"}), 500

    result["url"] = url
    result["char_count"] = len(content)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
