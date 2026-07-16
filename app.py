"""Smart Code Reviewer — LLM-powered pre-review for readability, structure, maintainability.

Design decisions (see README for rationale):
- Code is line-numbered before being sent to the model, so line references are grounded.
- The model must return schema-shaped JSON; freeform prose is rejected.
- Line references are validated deterministically in Python (not by a second LLM pass).
- High-severity issues gate the verdict to "request_changes".
- Provider-agnostic: works with any OpenAI-compatible endpoint (OpenAI, Groq, Gemini,
  Azure OpenAI) via environment variables.
"""

import json
import os
import re

import streamlit as st

# ---------------------------------------------------------------------------
# Provider setup: any OpenAI-compatible endpoint, chosen by env vars.
#
#   OPENAI_API_KEY   — required (e.g. a Groq key)
#   OPENAI_BASE_URL  — optional, e.g. https://api.groq.com/openai/v1
#   OPENAI_MODEL     — optional, e.g. llama-3.3-70b-versatile
#
# Or Azure OpenAI via AZURE_OPENAI_ENDPOINT / _API_KEY / _DEPLOYMENT.
# ---------------------------------------------------------------------------

def get_client():
    if os.environ.get("AZURE_OPENAI_ENDPOINT"):
        from openai import AzureOpenAI

        return AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01"),
        ), os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

    from openai import OpenAI

    return OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    ), os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


# ---------------------------------------------------------------------------
# Prompt: explicit rubric + strict output contract.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a senior software engineer performing a pre-review of a code snippet
before it reaches human review. You review against exactly three dimensions:

1. readability — naming, clarity, comments that lie or are missing where needed,
   magic values, deep nesting.
2. structure — function/class size, separation of concerns, duplication,
   error-handling design, dead code.
3. maintainability — testability, hidden coupling, mutable shared state,
   fragile assumptions, missing input validation.

Severity levels:
- high: likely to cause bugs or make the code unsafe to change (e.g. swallowed
  exceptions, mutable default arguments, hidden global state).
- medium: meaningfully hurts comprehension or future changes (e.g. 50-line
  function doing three jobs, duplicated logic).
- low: advisory style or polish (e.g. unclear name, magic number).

Rules:
- The code is given with line numbers in the form "N: code". Every issue MUST
  reference line numbers that exist in the snippet.
- Report at most 6 issues. Prefer the highest-impact ones. Do not pad.
- If the code is genuinely clean in a dimension, do not invent issues for it.
- Always include exactly one specific positive note about the code.
- suggested_fix must be a concrete rewrite or concrete instruction, not "consider improving".

Respond with ONLY a valid JSON object, no markdown fences, matching this schema:
{
  "summary": "one or two sentences on overall state",
  "positive_note": "one specific thing done well",
  "issues": [
    {
      "line_start": <int>,
      "line_end": <int>,
      "dimension": "readability" | "structure" | "maintainability",
      "severity": "high" | "medium" | "low",
      "title": "short issue title",
      "explanation": "why this matters, 1-3 sentences",
      "suggested_fix": "concrete fix"
    }
  ],
  "verdict": "approve" | "approve_with_nits" | "request_changes"
}"""


def number_lines(code: str) -> str:
    return "\n".join(f"{i}: {line}" for i, line in enumerate(code.splitlines(), start=1))


def parse_model_json(raw: str) -> dict:
    """Parse model output, tolerating markdown fences and surrounding prose."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise json.JSONDecodeError("no JSON object found", cleaned, 0)
    return json.loads(cleaned[start : end + 1])


def validate_review(review: dict, total_lines: int) -> tuple[dict, list[str]]:
    """Deterministic post-validation of the model's claims.

    - Drops issues whose line references don't exist in the snippet.
    - Enforces the severity gate: any high-severity issue forces request_changes.
    Returns (validated_review, list_of_validation_notes).
    """
    notes = []
    valid_issues = []
    for issue in review.get("issues", []):
        start, end = issue.get("line_start", 0), issue.get("line_end", 0)
        if not (1 <= start <= total_lines and start <= end <= total_lines):
            notes.append(
                f"Dropped issue '{issue.get('title', '?')}' — referenced lines "
                f"{start}-{end} outside snippet ({total_lines} lines)."
            )
            continue
        valid_issues.append(issue)
    review["issues"] = valid_issues

    severities = {i["severity"] for i in valid_issues}
    if "high" in severities and review.get("verdict") != "request_changes":
        notes.append("Verdict escalated to request_changes due to high-severity issue.")
        review["verdict"] = "request_changes"
    if not valid_issues and review.get("verdict") == "request_changes":
        review["verdict"] = "approve"
    return review, notes


def run_review(code: str, language: str) -> tuple[dict, list[str]]:
    client, model = get_client()
    numbered = number_lines(code)
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Language: {language}\n\nCode:\n{numbered}"},
        ],
    )
    review = parse_model_json(response.choices[0].message.content)
    return validate_review(review, total_lines=len(code.splitlines()))


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

SEVERITY_BADGE = {"high": "🔴 HIGH", "medium": "🟠 MEDIUM", "low": "🟡 LOW"}
VERDICT_LABEL = {
    "approve": ("✅ Approve", "Ready for human review."),
    "approve_with_nits": ("🟨 Approve with nits", "Minor advisories; safe to proceed."),
    "request_changes": ("🟥 Request changes", "High-impact issues should be fixed first."),
}

st.set_page_config(page_title="Smart Code Reviewer", page_icon="🔍", layout="wide")
st.title("🔍 Smart Code Reviewer")
st.caption(
    "AI pre-review for readability, structure, and maintainability — "
    "schema-validated output with deterministic line-reference checking."
)

samples = {}
sample_dir = os.path.join(os.path.dirname(__file__), "samples")
if os.path.isdir(sample_dir):
    for fname in sorted(os.listdir(sample_dir)):
        with open(os.path.join(sample_dir, fname)) as f:
            samples[fname] = f.read()

col_left, col_right = st.columns([1, 1])
with col_left:
    language = st.selectbox("Language", ["Python", "C#", "TypeScript", "JavaScript", "Java", "Other"])
    sample_choice = st.selectbox("Load a sample snippet (optional)", ["—"] + list(samples))
    default_code = samples.get(sample_choice, "")
    code = st.text_area("Code to review", value=default_code, height=380, placeholder="Paste a snippet…")
    go = st.button("Run review", type="primary", disabled=not code.strip())

with col_right:
    if go and code.strip():
        with st.spinner("Reviewing…"):
            try:
                review, validation_notes = run_review(code, language)
            except json.JSONDecodeError:
                st.error("Model returned non-JSON output. Re-run the review.")
                st.stop()
            except Exception as exc:  # surface config errors clearly
                st.error(f"Review failed: {exc}")
                st.stop()

        label, sub = VERDICT_LABEL.get(review.get("verdict", ""), ("❓ Unknown verdict", ""))
        st.subheader(label)
        st.caption(sub)
        st.write(review.get("summary", ""))
        st.success(f"**What's done well:** {review.get('positive_note', '')}")

        for issue in review["issues"]:
            lines = (
                f"line {issue['line_start']}"
                if issue["line_start"] == issue["line_end"]
                else f"lines {issue['line_start']}–{issue['line_end']}"
            )
            with st.expander(
                f"{SEVERITY_BADGE.get(issue.get('severity', 'low'), '⚪')} · "
                f"{issue.get('dimension', '?')} · "
                f"{issue.get('title', 'Issue')} ({lines})",
                expanded=issue.get("severity") == "high",
            ):
                st.write(issue.get("explanation", ""))
                st.markdown("**Suggested fix**")
                st.code(issue.get("suggested_fix", ""), language=language.lower())

        if validation_notes:
            with st.expander("⚙️ Validation layer activity"):
                for note in validation_notes:
                    st.write(f"- {note}")
    else:
        st.info("Paste code (or load a sample) and click **Run review**.")