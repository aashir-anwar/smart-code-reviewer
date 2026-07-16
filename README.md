# 🔍 Smart Code Reviewer

An LLM-powered pre-review tool that checks code for **readability, structure, and maintainability** before it reaches a human reviewer — with schema-validated output and deterministic verification of every claim the model makes.

## Why

AI code review tools tend to fail in two predictable ways:

1. **Unstructured output.** A wall of prose that a human has to re-read and re-interpret — and that no tooling can consume.
2. **Hallucinated references.** The model confidently flags "line 42" in a 30-line snippet, and trust in the whole review collapses.

Smart Code Reviewer is designed around fixing both. The model is constrained to an explicit rubric and a strict JSON schema, and everything it claims about the code is then verified deterministically in plain Python before being shown to the user.

## How it works

```
paste code ──> line-number the snippet ──> LLM review against explicit rubric
                                                 │  (strict JSON schema)
                                                 ▼
                              deterministic validation layer (Python)
                              • drops issues citing non-existent lines
                              • escalates verdict if any high-severity issue
                                                 ▼
                              verdict + severity-badged issues + positive note
```

Each review returns:

- A **verdict**: `approve`, `approve_with_nits`, or `request_changes`
- Up to six **issues**, each with a line range, dimension, severity, explanation, and a concrete suggested fix
- One specific **positive note** — reviews that only criticize get ignored

## Design decisions

**Rubric, not vibes.** The prompt defines exactly three review dimensions (readability, structure, maintainability) and what each severity level means, with examples. Constraining the model this way produces consistent, comparable reviews instead of freeform opinion.

**Structured output.** The model must return schema-shaped JSON. This makes the output consumable by tooling — the same review could gate a CI pipeline, not just render in a UI.

**Deterministic validation, not a second LLM pass.** The classic failure mode of AI code review is hallucinated line references. Instead of asking the model to self-check (slow, costly, still fallible), the app numbers the input lines and verifies every referenced line exists — in plain Python. Never use an LLM for something code can check.

**Severity gate.** Any high-severity issue forces a `request_changes` verdict, enforced in code even if the model was lenient. Style nits alone never block.

**Single-pass review.** An agentic multi-turn reviewer would be more thorough, but at PR scale latency and cost matter; one well-constrained call covers the pre-review use case.

**Provider-agnostic.** Works with any OpenAI-compatible endpoint — OpenAI, Groq, Google Gemini, or Azure OpenAI — selected purely through environment variables. No code changes to switch providers.

## Quick start

```bash
git clone https://github.com/aashir-anwar/smart-code-reviewer.git
cd smart-code-reviewer
pip install -r requirements.txt
```

Configure a provider (pick one):

**Groq (free tier):**

```bash
export OPENAI_API_KEY=gsk_...
export OPENAI_BASE_URL=https://api.groq.com/openai/v1
export OPENAI_MODEL=llama-3.3-70b-versatile
```

**OpenAI:**

```bash
export OPENAI_API_KEY=sk-...
# defaults: https://api.openai.com/v1, gpt-4o-mini
```

**Azure OpenAI:**

```bash
export AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_DEPLOYMENT=<deployment-name>
```

Then run:

```bash
streamlit run app.py
```

On Windows PowerShell, use `$env:OPENAI_API_KEY = "..."` instead of `export`, and `python -m streamlit run app.py` if `streamlit` isn't on your PATH.

## Configuration reference

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENAI_API_KEY` | yes* | — | API key for any OpenAI-compatible provider |
| `OPENAI_BASE_URL` | no | `https://api.openai.com/v1` | Endpoint (e.g. Groq, Gemini) |
| `OPENAI_MODEL` | no | `gpt-4o-mini` | Model name |
| `AZURE_OPENAI_ENDPOINT` | yes* | — | Switches the app to Azure OpenAI mode |
| `AZURE_OPENAI_API_KEY` | with Azure | — | Azure key |
| `AZURE_OPENAI_DEPLOYMENT` | with Azure | `gpt-4o-mini` | Azure deployment name |
| `AZURE_OPENAI_API_VERSION` | no | `2024-06-01` | Azure API version |

\* Provide either the OpenAI-compatible key **or** the Azure trio.

## Deploy on Streamlit Community Cloud

1. Fork or push this repo to GitHub (public).
2. On [share.streamlit.io](https://share.streamlit.io): **New app** → select the repo, branch `main`, file `app.py`.
3. Under **Advanced settings → Secrets**, add your provider variables in TOML form:

   ```toml
   OPENAI_API_KEY = "gsk_..."
   OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
   OPENAI_MODEL = "llama-3.3-70b-versatile"
   ```

4. Deploy. Secrets are injected as environment variables — no code changes needed.

## Sample snippets

The `samples/` directory contains three self-created, deliberately flawed snippets for demoing the reviewer:

| File | Language | Planted issues |
|---|---|---|
| `01_swallowed_exception.py` | Python | bare `except: pass`, mutable default arguments, unguarded dict access |
| `02_god_method.cs` | C# | one method doing validation + pricing + persistence + email, SQL built by string concatenation, hardcoded credentials |
| `03_duplicated_logic.ts` | TypeScript | the same filter logic duplicated across three functions, `any` types, loose equality |

## Project structure

```
├── app.py              # Streamlit UI, prompt, API call, validation layer
├── requirements.txt
├── samples/            # deliberately flawed demo snippets
└── README.md
```

## Limitations & possible extensions

- Reviews a single snippet per call; it doesn't see the wider codebase, so cross-file concerns (dead public APIs, architectural drift) are out of scope.
- Line-reference validation checks *existence*, not *relevance* — a model could cite a real but wrong line. A stricter check could verify the cited lines contain the tokens the issue mentions.
- Natural extensions: a GitHub Action that runs the same prompt + validation on PR diffs and posts findings as review comments; per-repo rubric overrides via a config file; caching reviews by snippet hash.

## License

MIT