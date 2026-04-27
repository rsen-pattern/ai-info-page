import datetime
from pathlib import Path

import streamlit as st

from utils.bifrost import get_api_key, get_client, load_models, call_with_fallback

st.set_page_config(
    page_title="AI Info Page Generator",
    page_icon="📄",
    layout="wide",
)

# ── helpers ──────────────────────────────────────────────────────────────────

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text()


def build_user_prompt(brand_input: str, extra_context: str) -> str:
    template = load_prompt("generate_ai_info.txt")
    current_date = datetime.datetime.now().strftime("%B, %Y")
    return template.format(
        brand_input=brand_input,
        extra_context=extra_context or "None provided.",
        current_date=current_date,
    )


# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Settings")
    api_key_input = st.text_input(
        "Bi Frost API Key",
        type="password",
        placeholder="Paste key or set BIFROST_API_KEY env var",
        help="Leave blank if BIFROST_API_KEY is set in your environment or Streamlit secrets.",
    )

    models_cfg = load_models()
    model_options = {m["id"]: m["label"] for m in models_cfg["models"]}
    selected_model = st.selectbox(
        "Model",
        options=list(model_options.keys()),
        format_func=lambda x: model_options[x],
        index=list(model_options.keys()).index(models_cfg["default"]),
    )

    st.divider()
    st.caption("Powered by Pattern Bi Frost · bifrost.pattern.com")

# ── main layout ───────────────────────────────────────────────────────────────

st.title("📄 AI Info Page Generator")
st.markdown(
    "Generate a structured, machine-readable **AI Info Page** that helps AI assistants "
    "accurately describe your brand."
)

left_col, right_col = st.columns([3, 2])

with left_col:
    brand_input = st.text_input(
        "Brand name or website URL",
        placeholder="e.g. rebelsport.com.au or Nike",
    )
    extra_context = st.text_area(
        "Additional context (optional)",
        placeholder="Add any extra facts, founding story, key products, or details you want included.",
        height=120,
    )
    generate_clicked = st.button(
        "✨ Generate AI Info Page",
        type="primary",
        disabled=not brand_input.strip(),
    )

with right_col:
    st.info(
        "**What is an AI Info Page?**\n\n"
        "An AI Info Page (also called an LLM Info Page) is a factual, machine-readable "
        "reference document published on your website at a stable URL (e.g. `/ai-info`) "
        "so that AI tools like ChatGPT, Claude, and Perplexity can accurately describe your brand.\n\n"
        "**After generating:**\n"
        "1. Publish the page at a stable URL (e.g. `yourdomain.com/ai-info`)\n"
        "2. Link to it from your site footer\n"
        "3. Update the date regularly to keep it fresh"
    )

# ── generation logic ──────────────────────────────────────────────────────────

if generate_clicked:
    resolved_key = get_api_key(api_key_input)
    if not resolved_key:
        st.error(
            "No API key found. Enter one in the sidebar, set the `BIFROST_API_KEY` "
            "environment variable, or add it to `.streamlit/secrets.toml`."
        )
        st.stop()

    system_prompt = load_prompt("system_prompt.txt")
    user_prompt = build_user_prompt(brand_input, extra_context)

    with st.spinner("Generating your AI Info Page via Bi Frost…"):
        try:
            client = get_client(resolved_key)
            result, used_model = call_with_fallback(
                client, selected_model, system_prompt, user_prompt, max_tokens=3000
            )
        except RuntimeError as exc:
            st.error(f"Generation failed: {exc}")
            st.stop()

    if used_model != selected_model:
        st.info(
            f"Primary model `{selected_model}` was unavailable. "
            f"Result generated with `{used_model}`."
        )

    st.success("AI Info Page generated!")

    preview_tab, raw_tab = st.tabs(["Preview", "Raw Markdown"])

    with preview_tab:
        st.markdown(result)

    with raw_tab:
        st.code(result, language="markdown")
        safe_brand = "".join(c if c.isalnum() else "-" for c in brand_input.strip()).strip("-").lower()
        filename = f"ai-info-{safe_brand}.md"
        st.download_button(
            label="⬇️ Download .md file",
            data=result,
            file_name=filename,
            mime="text/markdown",
        )

    with st.expander("📄 Convert to HTML for publishing"):
        st.markdown(
            "**Technical requirements for your published AI Info Page:**\n\n"
            "- Serve as indexable HTML (not behind a login or JavaScript wall)\n"
            "- Include a descriptive `<title>` tag\n"
            "- Include a `<meta name=\"description\">` tag\n"
            "- Link to the page from your site footer\n"
            "- Use simple, clean HTML — no heavy JavaScript required to read the content\n"
            "- Publish at a stable URL (e.g. `/ai-info`) and keep it permanently accessible"
        )

        current_date_str = datetime.datetime.now().strftime("%B %Y")
        html_boilerplate = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI Info — {brand_input}</title>
  <meta name="description" content="Official AI Info Page for {brand_input}. Structured reference for AI assistants. Last updated {current_date_str}." />
</head>
<body>
  <main>
    <!-- Paste your generated AI Info Page content here as plain text or rendered markdown -->
  </main>
</body>
</html>"""
        st.code(html_boilerplate, language="html")

# ── footer ────────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    "AI Info Page concept by Amin Foroutan · Popularised by Steve Toth · "
    "Built with Pattern Bi Frost"
)
