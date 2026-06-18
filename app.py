import os
import json
import requests
from flask import Flask, request, jsonify, make_response
from bs4 import BeautifulSoup
import anthropic

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# v4 — inlined to avoid Vercel template bundling issues
INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Story Evaluator</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #f5f5f7; --card: #ffffff; --border: #e0e0e0; --text: #1a1a1a; --muted: #666;
      --approved: #1a7f37; --approved-bg: #e6f4ea; --flag: #9a6700; --flag-bg: #fff8e1;
      --reject: #b91c1c; --reject-bg: #fef2f2; --accent: #2563eb; --accent-hover: #1d4ed8;
      --score-track: #e8e8e8;
    }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; padding: 2rem 1rem; }
    .container { max-width: 760px; margin: 0 auto; }
    header { text-align: center; margin-bottom: 2.5rem; }
    header h1 { font-size: 1.75rem; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0.4rem; }
    header p { color: var(--muted); font-size: 0.95rem; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem 1.5rem; margin-bottom: 1.25rem; }
    .tabs { display: flex; border-bottom: 1px solid var(--border); margin-bottom: 1rem; }
    .tab-btn { padding: 0.5rem 1rem; font-size: 0.875rem; font-weight: 500; border: none; background: none; cursor: pointer; color: var(--muted); border-bottom: 2px solid transparent; margin-bottom: -1px; transition: color 0.15s, border-color 0.15s; }
    .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; }
    .input-row { display: flex; gap: 0.75rem; }
    input[type="url"], input[type="text"] { flex: 1; padding: 0.65rem 0.9rem; border: 1px solid var(--border); border-radius: 8px; font-size: 0.95rem; outline: none; transition: border-color 0.15s; }
    input[type="url"]:focus, input[type="text"]:focus { border-color: var(--accent); }
    textarea { width: 100%; padding: 0.65rem 0.9rem; border: 1px solid var(--border); border-radius: 8px; font-size: 0.9rem; font-family: inherit; resize: vertical; outline: none; transition: border-color 0.15s; min-height: 140px; margin-top: 0.75rem; }
    textarea:focus { border-color: var(--accent); }
    .paste-label { font-size: 0.8rem; color: var(--muted); margin-bottom: 0.3rem; display: block; }
    .paste-title-row { margin-bottom: 0.5rem; }
    .paste-actions { margin-top: 0.75rem; display: flex; justify-content: flex-end; }
    .btn { padding: 0.65rem 1.4rem; background: var(--accent); color: #fff; border: none; border-radius: 8px; font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: background 0.15s; }
    .btn:hover:not(:disabled) { background: var(--accent-hover); }
    .btn:disabled { opacity: 0.6; cursor: default; }
    .spinner { display: none; text-align: center; padding: 2rem; color: var(--muted); font-size: 0.9rem; }
    .spinner.active { display: block; }
    .spinner-ring { width: 36px; height: 36px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 0.75rem; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .error-box { display: none; background: var(--reject-bg); border: 1px solid #fca5a5; border-radius: 8px; padding: 0.9rem 1rem; color: var(--reject); font-size: 0.875rem; margin-bottom: 1.25rem; }
    .error-box.active { display: block; }
    .btn-hint { margin-top: 0.6rem; padding: 0.45rem 1rem; background: var(--accent); color: #fff; border: none; border-radius: 6px; font-size: 0.82rem; font-weight: 600; cursor: pointer; }
    .btn-hint:hover { background: var(--accent-hover); }
    #results { display: none; }
    #results.active { display: block; }
    .verdict-banner { display: flex; align-items: center; gap: 1rem; padding: 1.25rem 1.5rem; border-radius: 12px; margin-bottom: 1.25rem; }
    .verdict-banner.approved { background: var(--approved-bg); border: 1px solid #bbf7d0; }
    .verdict-banner.needs-review { background: var(--flag-bg); border: 1px solid #fde68a; }
    .verdict-banner.rejected { background: var(--reject-bg); border: 1px solid #fca5a5; }
    .verdict-icon { font-size: 2rem; flex-shrink: 0; }
    .verdict-label { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.2rem; }
    .verdict-banner.approved .verdict-label { color: var(--approved); }
    .verdict-banner.needs-review .verdict-label { color: var(--flag); }
    .verdict-banner.rejected .verdict-label { color: var(--reject); }
    .verdict-title { font-size: 1.15rem; font-weight: 700; }
    .verdict-rec { font-size: 0.875rem; color: var(--muted); margin-top: 0.15rem; }
    .criteria-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.25rem; }
    @media (max-width: 520px) { .criteria-grid { grid-template-columns: 1fr; } .input-row { flex-direction: column; } }
    .criterion-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; }
    .criterion-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
    .criterion-name { font-weight: 600; font-size: 0.9rem; }
    .criterion-badge { font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.55rem; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.05em; }
    .badge-pass { background: var(--approved-bg); color: var(--approved); }
    .badge-flag { background: var(--flag-bg); color: var(--flag); }
    .badge-reject { background: var(--reject-bg); color: var(--reject); }
    .score-display { display: flex; align-items: baseline; gap: 0.25rem; margin-bottom: 0.5rem; }
    .score-num { font-size: 2.25rem; font-weight: 700; line-height: 1; }
    .score-denom { font-size: 0.9rem; color: var(--muted); }
    .score-bar { height: 6px; background: var(--score-track); border-radius: 999px; overflow: hidden; margin-bottom: 0.75rem; }
    .score-fill { height: 100%; border-radius: 999px; transition: width 0.6s ease; }
    .fill-pass { background: var(--approved); }
    .fill-flag { background: #eab308; }
    .fill-reject { background: var(--reject); }
    .criterion-summary { font-size: 0.82rem; color: var(--muted); line-height: 1.5; margin-bottom: 0.6rem; }
    .issues-list { list-style: none; display: flex; flex-direction: column; gap: 0.3rem; }
    .issues-list li { font-size: 0.8rem; display: flex; gap: 0.4rem; line-height: 1.4; }
    .issues-list li::before { content: "\\2022"; color: var(--reject); flex-shrink: 0; }
    .no-issues { font-size: 0.8rem; color: var(--approved); }
    .story-card h3 { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); margin-bottom: 0.5rem; }
    .story-card .story-title { font-size: 1rem; font-weight: 600; margin-bottom: 0.3rem; }
    .story-card .story-url { font-size: 0.8rem; color: var(--accent); word-break: break-all; }
    .story-meta { font-size: 0.8rem; color: var(--muted); margin-top: 0.5rem; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Story Evaluator</h1>
      <p>Check a story against our community guidelines.</p>
    </header>

    <div class="card">
      <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('url')">By URL</button>
        <button class="tab-btn" onclick="switchTab('paste')">Paste Text</button>
      </div>

      <div class="tab-panel active" id="tab-url">
        <div class="input-row">
          <input id="url-input" type="url" placeholder="https://yoursite.com/stories/example" autocomplete="off" spellcheck="false" />
          <button class="btn" id="url-submit-btn" onclick="runUrlEvaluation()">Evaluate</button>
        </div>
      </div>

      <div class="tab-panel" id="tab-paste">
        <div class="paste-title-row">
          <label class="paste-label">Story title (optional)</label>
          <input type="text" id="paste-title" placeholder="My story title" />
        </div>
        <label class="paste-label">Story content</label>
        <textarea id="paste-content" placeholder="Paste the full story text here…"></textarea>
        <div class="paste-actions">
          <button class="btn" id="paste-submit-btn" onclick="runPasteEvaluation()">Evaluate</button>
        </div>
      </div>
    </div>

    <div class="error-box" id="error-box">
      <div id="error-msg"></div>
      <div id="error-hint" style="display:none">
        <button class="btn-hint" onclick="switchTab('paste')">Switch to Paste Text &rarr;</button>
      </div>
    </div>

    <div class="spinner" id="spinner">
      <div class="spinner-ring"></div>
      <span id="spinner-text">Fetching and evaluating story&hellip;</span>
    </div>

    <div id="results">
      <div class="verdict-banner" id="verdict-banner">
        <div class="verdict-icon" id="verdict-icon"></div>
        <div>
          <div class="verdict-label" id="verdict-label"></div>
          <div class="verdict-title" id="verdict-title"></div>
          <div class="verdict-rec" id="verdict-rec"></div>
        </div>
      </div>

      <div class="criteria-grid">
        <div class="criterion-card">
          <div class="criterion-header">
            <span class="criterion-name">Safety &amp; Moderation</span>
            <span class="criterion-badge" id="safety-badge"></span>
          </div>
          <div class="score-display"><span class="score-num" id="safety-score"></span><span class="score-denom">/100</span></div>
          <div class="score-bar"><div class="score-fill" id="safety-bar"></div></div>
          <div class="criterion-summary" id="safety-summary"></div>
          <ul class="issues-list" id="safety-issues"></ul>
        </div>
        <div class="criterion-card">
          <div class="criterion-header">
            <span class="criterion-name">Tone &amp; Voice</span>
            <span class="criterion-badge" id="tone-badge"></span>
          </div>
          <div class="score-display"><span class="score-num" id="tone-score"></span><span class="score-denom">/100</span></div>
          <div class="score-bar"><div class="score-fill" id="tone-bar"></div></div>
          <div class="criterion-summary" id="tone-summary"></div>
          <ul class="issues-list" id="tone-issues"></ul>
        </div>
      </div>

      <div class="card story-card" id="story-info">
        <h3>Evaluated Story</h3>
        <div class="story-title" id="story-title-display"></div>
        <a class="story-url" id="story-url-display" target="_blank" rel="noopener"></a>
        <div class="story-meta" id="story-meta"></div>
      </div>
    </div>
  </div>

  <script>
    document.getElementById('url-input').addEventListener('keydown', e => {
      if (e.key === 'Enter') runUrlEvaluation();
    });

    function switchTab(name) {
      document.querySelectorAll('.tab-btn').forEach((b, i) => {
        b.classList.toggle('active', (i === 0 && name === 'url') || (i === 1 && name === 'paste'));
      });
      document.getElementById('tab-url').classList.toggle('active', name === 'url');
      document.getElementById('tab-paste').classList.toggle('active', name === 'paste');
      clearError();
    }

    function clearError() {
      document.getElementById('error-box').classList.remove('active');
      document.getElementById('error-hint').style.display = 'none';
    }

    function showError(msg, showHint = false) {
      document.getElementById('error-msg').textContent = msg;
      document.getElementById('error-hint').style.display = showHint ? 'block' : 'none';
      document.getElementById('error-box').classList.add('active');
    }

    function setLoading(on, text) {
      document.getElementById('spinner').classList.toggle('active', on);
      if (text) document.getElementById('spinner-text').textContent = text;
      document.getElementById('url-submit-btn').disabled = on;
      document.getElementById('paste-submit-btn').disabled = on;
    }

    function verdictClass(v) { return v === 'Approved' ? 'approved' : v === 'Needs Review' ? 'needs-review' : 'rejected'; }
    function verdictIcon(v) { return v === 'Approved' ? '\\u2705' : v === 'Needs Review' ? '\\u26a0\\ufe0f' : '\\ud83d\\udeab'; }
    function badgeClass(v) { return v === 'Pass' ? 'badge-pass' : v === 'Flag' ? 'badge-flag' : 'badge-reject'; }
    function fillClass(v) { return v === 'Pass' ? 'fill-pass' : v === 'Flag' ? 'fill-flag' : 'fill-reject'; }

    function renderCriterion(prefix, data) {
      document.getElementById(prefix + '-score').textContent = data.score;
      document.getElementById(prefix + '-summary').textContent = data.summary;
      const badge = document.getElementById(prefix + '-badge');
      badge.textContent = data.verdict;
      badge.className = 'criterion-badge ' + badgeClass(data.verdict);
      const bar = document.getElementById(prefix + '-bar');
      bar.style.width = data.score + '%';
      bar.className = 'score-fill ' + fillClass(data.verdict);
      const list = document.getElementById(prefix + '-issues');
      list.innerHTML = '';
      const prev = list.previousElementSibling;
      if (prev && prev.classList.contains('no-issues')) prev.remove();
      if (data.issues && data.issues.length) {
        data.issues.forEach(issue => {
          const li = document.createElement('li');
          li.textContent = issue;
          list.appendChild(li);
        });
      } else {
        const p = document.createElement('p');
        p.className = 'no-issues';
        p.textContent = 'No issues found.';
        list.parentNode.insertBefore(p, list);
      }
    }

    function renderResults(data, sourceUrl) {
      const banner = document.getElementById('verdict-banner');
      banner.className = 'verdict-banner ' + verdictClass(data.overall.verdict);
      document.getElementById('verdict-icon').textContent = verdictIcon(data.overall.verdict);
      document.getElementById('verdict-label').textContent = 'Overall verdict';
      document.getElementById('verdict-title').textContent = data.overall.verdict;
      document.getElementById('verdict-rec').textContent = data.overall.recommendation;
      renderCriterion('safety', data.safety);
      renderCriterion('tone', data.tone);
      document.getElementById('story-title-display').textContent = data.extracted_title || 'Untitled Story';
      const urlEl = document.getElementById('story-url-display');
      if (sourceUrl) { urlEl.textContent = sourceUrl; urlEl.href = sourceUrl; urlEl.style.display = ''; }
      else { urlEl.style.display = 'none'; }
      document.getElementById('story-meta').textContent = data.char_count.toLocaleString() + ' characters evaluated';
      document.getElementById('results').classList.add('active');
    }

    async function runUrlEvaluation() {
      const url = document.getElementById('url-input').value.trim();
      if (!url) { document.getElementById('url-input').focus(); return; }
      clearError();
      document.getElementById('results').classList.remove('active');
      setLoading(true, 'Fetching and evaluating story…');
      try {
        const res = await fetch('/evaluate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
        const data = await res.json();
        setLoading(false);
        if (!res.ok || data.error) { showError(data.error || 'An unexpected error occurred.', !!data.blocked); return; }
        renderResults(data, url);
      } catch { setLoading(false); showError('Network error — please check your connection and try again.'); }
    }

    async function runPasteEvaluation() {
      const content = document.getElementById('paste-content').value.trim();
      const title = document.getElementById('paste-title').value.trim();
      if (content.length < 50) { showError('Please paste at least 50 characters of story content.'); return; }
      clearError();
      document.getElementById('results').classList.remove('active');
      setLoading(true, 'Evaluating story…');
      try {
        const res = await fetch('/evaluate-text', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, content }) });
        const data = await res.json();
        setLoading(false);
        if (!res.ok || data.error) { showError(data.error || 'An unexpected error occurred.'); return; }
        renderResults(data, '');
      } catch { setLoading(false); showError('Network error — please check your connection and try again.'); }
    }
  </script>
</body>
</html>"""

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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    title = ""
    if soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)
    elif soup.find("title"):
        title = soup.find("title").get_text(strip=True)

    for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                     "advertisement", "form", "button"]):
        tag.decompose()

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
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


@app.route("/")
def index():
    resp = make_response(INDEX_HTML)
    resp.headers["Content-Type"] = "text/html"
    resp.headers["Cache-Control"] = "no-store"
    return resp


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
        code = e.response.status_code
        if code in (401, 403, 429):
            return jsonify({"error": f"The website blocked access ({code}). Use the Paste Text tab instead.", "blocked": True}), 400
        return jsonify({"error": f"The website returned an error ({code})."}), 400

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


@app.route("/evaluate-text", methods=["POST"])
def evaluate_text():
    data = request.get_json()
    title = (data or {}).get("title", "").strip()
    content = (data or {}).get("content", "").strip()

    if not content or len(content) < 50:
        return jsonify({"error": "Please paste at least 50 characters of story content."}), 400

    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY is not configured on the server"}), 500

    content = content[:8000]
    try:
        result = evaluate_story(title, content)
    except json.JSONDecodeError:
        return jsonify({"error": "Evaluation returned an unexpected format. Please try again."}), 500
    except anthropic.APIError as e:
        return jsonify({"error": f"AI evaluation failed: {str(e)}"}), 500

    result["url"] = ""
    result["char_count"] = len(content)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
