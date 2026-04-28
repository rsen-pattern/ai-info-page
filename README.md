# AI Info Page Generator

A Streamlit app that takes a brand name or website URL and generates a structured **AI Info Page** (also called an LLM Info Page) using Pattern's Bi Frost LLM gateway.

An AI Info Page is a factual, machine-readable reference document designed to be published on a brand's website at a stable URL (e.g. `/ai-info`) so that AI tools like ChatGPT, Claude, and Perplexity can accurately describe the brand — instead of hallucinating or citing unreliable third-party sources.

---

## Table of Contents

1. [What is an AI Info Page?](#what-is-an-ai-info-page)
2. [Project Structure](#project-structure)
3. [Local Setup](#local-setup)
4. [Streamlit Cloud Deploy](#streamlit-cloud-deploy)
5. [Using the App](#using-the-app)
6. [Generation Modes](#generation-modes)
7. [FAQ Seeding](#faq-seeding)
8. [Understanding the Confidence Panel](#understanding-the-confidence-panel)
9. [Publishing Your AI Info Page](#publishing-your-ai-info-page)
10. [Keeping It Fresh](#keeping-it-fresh)
11. [Adding Models](#adding-models)
12. [Bi Frost API](#bi-frost-api)

---

## What is an AI Info Page?

AI assistants like ChatGPT, Claude, and Perplexity are increasingly used as the first stop for brand research. When someone asks "What does [Brand] do?" or "Is [Brand] legit?", the AI draws on whatever it can find — which is often outdated training data, unreliable third-party reviews, or hallucinated details.

An AI Info Page solves this by giving AI tools a single, authoritative source they can read and cite. It is:

- **Factual, not promotional** — written like a Wikipedia entry, not a marketing brochure
- **Machine-readable** — structured with consistent headings so AI can parse it reliably
- **Stable** — published at a permanent URL that crawlers can revisit
- **Owned by the brand** — first-party information that corrects misconceptions at the source

Think of it as the brand's handshake with AI.

---

## Project Structure

```
ai-info-page-generator/
├── app.py                        # Main Streamlit application
├── config/
│   └── models.json               # Model registry and fallback chain
├── prompts/
│   ├── system_prompt.txt         # LLM system role instruction
│   ├── generate_ai_info.txt      # Main generation prompt template
│   ├── faq_suggest.txt           # FAQ suggestion prompt template
│   └── synthesise.txt            # Multi-model synthesis prompt template
├── utils/
│   ├── __init__.py
│   ├── bifrost.py                # Bi Frost gateway client
│   └── scraper.py                # Brand site and external source scraper
├── .streamlit/
│   └── secrets.toml.example      # API key template (safe to commit)
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

Or set the key via environment variable:

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
4. Deploy — the app reads the secret automatically; the sidebar API key field is for overrides only

---

## Using the App

### Step 1 — Enter your brand

In the **Brand** column, enter either:
- A domain: `rebelsport.com.au`, `nike.com`
- A brand name: `Nike`, `Rebel Sport`

If you enter a domain, the scraper will attempt to fetch your homepage, About, Contact, Press, and other key pages automatically. If you enter a name only, the app skips the brand site scrape and relies on LLM knowledge plus external sources.

**Additional context** (optional): paste any facts the scraper might miss — founding story, key personnel, recent news, or product details. This goes directly into the prompt.

Check **Also scrape Wikipedia & Crunchbase** to pull in external reference data. Wikipedia is usually the most useful; Crunchbase frequently blocks automated requests but is attempted gracefully.

### Step 2 — Seed your FAQs

Choose how questions are sourced for the FAQ section (see [FAQ Seeding](#faq-seeding) below).

### Step 3 — Choose a generation mode

Pick Auto, Compare, or Synthesise from the sidebar (see [Generation Modes](#generation-modes) below).

### Step 4 — Generate

Click **✨ Generate AI Info Page**. The app will:

1. Scrape the brand site and external sources
2. (If LLM-suggested FAQs) Generate 10 question suggestions for you to review
3. Build and send the prompt to Bi Frost
4. Parse the response and display the result in Preview and Raw Markdown tabs
5. Show the Confidence & Sources panel below the output

### Step 5 — Download and publish

Use the **Download as .md** button in the Raw Markdown tab, then follow the [Publishing](#publishing-your-ai-info-page) steps below.

---

## Generation Modes

### Auto (single best)
The fastest option. Uses your selected model with an automatic fallback chain. If the primary model fails, it tries the next in the chain (`models.json → fallback_chain`) until one succeeds. A banner appears if a fallback was used.

**Best for:** Quick drafts, single-brand runs, time-sensitive work.

### Compare (all models, you choose)
Runs all models in `compare_models` in parallel using threads, then displays each result in a separate tab. You review the outputs side by side and click **Use this output** on the one you prefer.

**Best for:** High-stakes brands where you want human judgment on which model produced the most accurate output.

### Synthesise (all models, auto-merged)
Runs all models in parallel, then sends all three drafts to your primary selected model with a synthesis prompt. The judge model picks the most accurate, specific, and well-supported content from each draft, flags conflicts with `[VERIFY]`, and produces a single merged page with a confidence score per section.

**Best for:** Maximum accuracy — takes longer but produces the most thorough output.

---

## FAQ Seeding

The FAQ section is one of the highest-value parts of an AI Info Page because it maps directly to the queries people type into AI assistants. Three seeding methods are available:

### LLM-suggested
After scraping, the app sends the brand context to the LLM and asks for 10 commonly searched questions. These appear as checkboxes — tick the ones you want answered, untick any that aren't relevant, then click **Confirm FAQ selection and generate**.

This is the recommended mode for most brands.

### Manual entry
Type your own questions, one per line. Useful when you already know the top queries from your SEO data or customer support logs.

### SEMrush CSV upload
Export a keyword report from SEMrush (Keyword Overview or Organic Research) and upload the `.csv`. The app scans every keyword and extracts question-type queries — those starting with "what", "who", "where", "when", "how", "why", "is", "does", "can", "are", or "which". Up to 15 questions are used.

**How to export from SEMrush:**
1. Go to **Keyword Overview** or **Organic Research → Keywords**
2. Filter by your brand name
3. Click **Export → CSV**
4. Upload the file to the app

---

## Understanding the Confidence Panel

After generation, the **Sources & Confidence** panel appears below the output. It shows a per-section confidence score driven by the `CONFIDENCE_METADATA` block the LLM appends to its response.

### Score guide

| Badge | Score | Meaning |
|---|---|---|
| 🟢 | 0.8 – 1.0 | High confidence — content came from scraped sources |
| 🟡 | 0.5 – 0.7 | Medium — LLM knowledge, likely correct but worth verifying |
| 🔴 | 0.0 – 0.4 | Low — inferred or uncertain; manually check before publishing |

### Score thresholds

| Score | Source |
|---|---|
| 1.0 | Directly scraped from the brand's own website |
| 0.8 | Confirmed by an external scraped source (Wikipedia, etc.) |
| 0.6 | Present in 2+ model drafts (Synthesise mode) or high-confidence LLM knowledge |
| 0.4 | Present in only 1 model draft, or LLM knowledge with uncertainty |
| 0.2 | Inferred — treat as a placeholder and verify |

### What to do with red sections

Any section scoring below 0.5 should be reviewed before publishing. Common causes:
- The brand has a limited online footprint (scraper found little)
- The brand name is ambiguous (shares a name with another entity)
- The data is genuinely uncertain (e.g. founding year not publicly confirmed)

For red sections, either verify the claim manually and update the markdown, or replace the content with hedged language ("reportedly", "approximately").

---

## Publishing Your AI Info Page

### Where to publish

Publish the page at a stable, permanent URL on your own domain:

```
yourdomain.com/ai-info
```

Other acceptable paths: `/llm-info`, `/ai-information`, `/about-ai`. Avoid paths that suggest the page is temporary or versioned (e.g. `/ai-info-v2`).

### Technical requirements

| Requirement | Why it matters |
|---|---|
| Standard HTML page | AI crawlers read HTML — PDFs and `.txt` files are often skipped |
| `<title>` tag | Signals the page purpose to crawlers |
| `<meta name="description">` | Provides a concise summary for indexing |
| Footer link | Ensures crawlers discover the page from your homepage |
| No JavaScript rendering required | Content must be visible in the raw HTML source |
| Stable, permanent URL | Never redirect this URL — AI tools cache source locations |

### HTML template

The app generates this boilerplate in the **HTML publishing guide** expander after generation. Copy and fill it in:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Official AI Information: Brand Name</title>
  <meta name="description" content="Verified facts about Brand Name for AI assistants and LLMs. Last updated Month Year.">
</head>
<body>
  <!-- Paste your generated AI Info Page content here -->
  <!-- Convert markdown headings to <h2> tags -->
  <!-- Convert bullet points to <ul><li> lists -->
</body>
</html>
```

### Converting markdown to HTML

The generated output uses `##` headings and bullet points. Most CMS platforms (WordPress, Webflow, Shopify) accept markdown directly or have a markdown block. For custom HTML, a simple conversion:

| Markdown | HTML |
|---|---|
| `## Section Title` | `<h2>Section Title</h2>` |
| `- Bullet point` | `<li>Bullet point</li>` (wrap in `<ul>`) |
| `**Bold**` | `<strong>Bold</strong>` |

### Footer link

Add a small, unobtrusive link in your site footer:

```html
<a href="/ai-info">AI Information</a>
```

Label options: "AI Info", "LLM Info", "AI Information", "Information for AI". Keep it factual — not "AI SEO" or similar.

---

## Keeping It Fresh

An AI Info Page is not a set-and-forget asset. Plan to update it when:

- Key personnel change
- You launch a major new product or service
- Your positioning or mission statement changes
- You receive significant press coverage or awards
- The "Last updated" date is more than 6 months old

When updating, regenerate the full page (new scrape + new generation), review the diff against your current published version, and increment the date.

A quarterly review cycle is a reasonable default for most brands.

---

## Adding Models

Edit `config/models.json` only — no Python changes required:

```json
{
  "models": [
    {
      "id": "provider/model-id",
      "label": "Display Name",
      "max_output": 8192,
      "role": "primary"
    }
  ],
  "default": "provider/model-id",
  "fallback_chain": ["provider/model-id", "..."],
  "compare_models": ["provider/model-id", "..."]
}
```

- `id`: format is `provider/model-id` (e.g. `anthropic/claude-sonnet-4-6`, `openai/gpt-4.1`)
- `role`: `"primary"` or `"secondary"` — informational only, not used by the app logic
- `fallback_chain`: ordered list of model IDs to try if the primary fails
- `compare_models`: models included in Compare and Synthesise modes

---

## Bi Frost API

Bi Frost is Pattern's LLM gateway at `https://bifrost.pattern.com`. It exposes an OpenAI-compatible API, so the app uses the OpenAI Python SDK with Bi Frost's base URL (`/v1`).

The app accepts the key under two environment variable names for backwards compatibility: `BIFROST_API_KEY` and `BIFROST_KEY`.

Key resolution order:
1. Value typed into the sidebar (override)
2. `BIFROST_API_KEY` / `BIFROST_KEY` in Streamlit secrets (`st.secrets`)
3. `BIFROST_API_KEY` / `BIFROST_KEY` environment variable

Contact Pattern for API key access.

---

*AI Info Page concept by Amin Foroutan · Popularised by Steve Toth · Built with Pattern Bi Frost*
