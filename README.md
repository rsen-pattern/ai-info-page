# AI Info Page Generator

A Streamlit app that takes a brand name or website URL and generates a structured **AI Info Page** (also called an LLM Info Page) using Pattern's Bi Frost LLM gateway.

An AI Info Page is a factual, machine-readable reference document designed to be published on a brand's website at a stable URL (e.g. `/ai-info`) so that AI tools like ChatGPT, Claude, and Perplexity can accurately describe the brand — instead of hallucinating or citing unreliable third-party sources.

---

## Project Structure

```
ai-info-page-generator/
├── app.py
├── config/
│   └── models.json
├── prompts/
│   ├── system_prompt.txt
│   └── generate_ai_info.txt
├── utils/
│   ├── __init__.py
│   └── bifrost.py
├── .streamlit/
│   └── secrets.toml.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Local Setup

```bash
git clone <repo-url>
cd ai-info-page-generator

pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml and add your Bi Frost API key

streamlit run app.py
```

You can also set the key via environment variable instead of secrets.toml:

```bash
export BIFROST_API_KEY="your-key-here"
streamlit run app.py
```

---

## Streamlit Cloud Deploy

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. In **App settings → Secrets**, add:
   ```toml
   BIFROST_API_KEY = "your-bifrost-key-here"
   ```
4. Deploy — no other configuration needed

---

## After Generating

To get the most value from your AI Info Page, publish it correctly:

- **Indexable HTML** — serve as plain HTML, not behind a login or JavaScript wall
- **Title tag** — `<title>AI Info — Brand Name</title>`
- **Meta description** — `<meta name="description" content="Official AI Info Page for Brand Name…">`
- **Footer link** — link to the page from your site footer so crawlers discover it
- **Simple HTML** — content must be readable without executing JavaScript
- **Stable URL** — publish at `/ai-info` and keep it permanently accessible; update the date regularly

---

## Adding Models

Edit `config/models.json` only — no Python changes required:

```json
{
  "models": [
    { "id": "provider/model-id", "label": "Display Name", "max_output": 8192 }
  ],
  "default": "provider/model-id",
  "fallback_chain": ["provider/model-id", ...]
}
```

Model IDs follow the format `provider/model-id` (e.g. `anthropic/claude-sonnet-4-6`).

---

## Bi Frost API

Bi Frost is Pattern's LLM gateway at `https://bifrost.pattern.com`. It exposes an OpenAI-compatible API, so the app uses the OpenAI Python SDK pointed at Bi Frost's base URL (`/v1`). Contact Pattern for API key access.
