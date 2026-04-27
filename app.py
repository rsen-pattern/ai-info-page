import json
import datetime
from pathlib import Path

import streamlit as st

from utils.bifrost import (
    get_api_key, get_client, load_models,
    call_with_fallback, call_parallel, parse_confidence_metadata,
)
from utils.scraper import (
    scrape_brand_site, scrape_external_sources,
    merge_scrape_results, format_sources_for_prompt,
)

st.set_page_config(page_title="AI Info Page Generator", page_icon="📋", layout="wide")

# ── session state defaults ────────────────────────────────────────────────────

_DEFAULTS = {
    "faq_suggestions": [],       # list[str] — LLM-suggested FAQ questions
    "await_faq_confirm": False,  # True when waiting for user to confirm FAQ selection
    "scraped_context": "",       # formatted text passed to LLM
    "scrape_result": None,       # ScrapeResult object for display
    "pipeline_output": None,     # dict with generation results
    "compare_results": {},       # {model_id: raw_output} for Compare mode
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── helpers ───────────────────────────────────────────────────────────────────

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text()


def build_generation_prompt(
    brand_input: str,
    extra_context: str,
    faq_questions: list[str],
    scraped_context: str,
) -> str:
    current_date = datetime.datetime.now().strftime("%B, %Y")
    faq_str = (
        "\n".join(f"- {q}" for q in faq_questions)
        if faq_questions
        else "None provided — generate 5 likely questions."
    )
    return load_prompt("generate_ai_info").format(
        brand_input=brand_input,
        extra_context=extra_context or "None provided.",
        faq_questions=faq_str,
        scraped_context=scraped_context or "No scraped content available — use training knowledge.",
        current_date=current_date,
    )


def render_confidence_panel(metadata: dict, scrape_result=None):
    st.subheader("🔍 Sources & Confidence")

    if not metadata:
        st.warning("No confidence metadata returned by the model. This can happen with smaller models.")
    else:
        sections = metadata.get("sections", {})

        def badge(score: float) -> str:
            if score >= 0.8:
                return "🟢"
            elif score >= 0.5:
                return "🟡"
            return "🔴"

        def label(score: float) -> str:
            if score >= 0.8:
                return "High confidence"
            elif score >= 0.5:
                return "Medium — verify"
            return "Low — manual check needed"

        for section_name, data in sections.items():
            score = data.get("score", 0)
            sources = data.get("sources", [])
            col_a, col_b = st.columns([3, 7])
            with col_a:
                st.markdown(f"**{section_name}**")
                st.markdown(f"{badge(score)} {label(score)} ({score:.0%})")
            with col_b:
                if sources:
                    for src in sources:
                        if src == "llm_knowledge":
                            st.caption("📚 LLM training knowledge")
                        else:
                            st.caption(f"🌐 {src}")
                else:
                    st.caption("No source recorded")
            st.divider()

    if scrape_result:
        with st.expander("📡 Scraping summary"):
            if scrape_result.failures:
                for f in scrape_result.failures:
                    st.warning(f"⚠️ {f}")
            if scrape_result.sources:
                st.success(
                    f"Successfully scraped {len(scrape_result.sources)} page(s) — "
                    f"{scrape_result.total_chars:,} characters of source material"
                )
                for s in scrape_result.sources:
                    st.caption(f"✅ {s.page_label} — {s.url}")
            if not scrape_result.sources and not scrape_result.failures:
                st.info("No scraping was attempted.")


def _run_scraping(brand_input: str, scrape_external: bool) -> tuple[str, object]:
    """Run scraping stages. Returns (scraped_context, merged ScrapeResult)."""
    brand_scrape = None
    external_scrape = None

    if brand_input and ("." in brand_input or brand_input.startswith("http")):
        st.write(f"Scraping {brand_input}…")
        brand_scrape = scrape_brand_site(brand_input)
        if brand_scrape.failures:
            for f in brand_scrape.failures:
                st.warning(f"⚠️ {f}")
        if brand_scrape.sources:
            st.write(f"✅ Scraped {len(brand_scrape.sources)} page(s) from brand site")
        else:
            st.warning("⚠️ Could not scrape brand site — continuing with LLM knowledge only")
    else:
        st.write("No URL detected — skipping brand site scrape")

    if scrape_external and brand_input:
        brand_name_for_external = (
            brand_input.split(".")[0].replace("-", " ").replace("_", " ").title()
        )
        st.write(f"Scraping external sources for '{brand_name_for_external}'…")
        external_scrape = scrape_external_sources(brand_name_for_external)
        if external_scrape.failures:
            for f in external_scrape.failures:
                st.warning(f"⚠️ {f}")
        if external_scrape.sources:
            st.write(f"✅ Found {len(external_scrape.sources)} external source(s)")

    to_merge = [r for r in [brand_scrape, external_scrape] if r is not None]
    merged = merge_scrape_results(*to_merge) if to_merge else None
    context = format_sources_for_prompt(merged) if merged else ""
    return context, merged


def _run_generation(
    client,
    selected_model: str,
    selected_label: str,
    gen_mode: str,
    models_cfg: dict,
    system_prompt: str,
    user_prompt: str,
    brand_input: str,
    scraped_context: str,
) -> dict | None:
    """Run generation and return a pipeline_output dict, or None on fatal error."""

    if gen_mode == "Auto (single best)":
        with st.spinner(f"Generating with {selected_label}…"):
            try:
                raw_result, used_model = call_with_fallback(
                    client, selected_model, system_prompt, user_prompt, max_tokens=3000
                )
                if used_model != selected_model:
                    st.info(f"ℹ️ Fell back to `{used_model}`")
            except Exception as e:
                st.error(f"Generation failed: {e}")
                return None
        clean_content, metadata = parse_confidence_metadata(raw_result)
        return {
            "mode": "auto",
            "clean_content": clean_content,
            "metadata": metadata,
        }

    # Compare or Synthesise — both need parallel results
    compare_models = models_cfg.get("compare_models", [selected_model])

    # Check if we already have cached parallel results
    if st.session_state.compare_results:
        results_map = st.session_state.compare_results
    else:
        with st.spinner(f"Running {len(compare_models)} models in parallel…"):
            parallel_results = call_parallel(
                client, compare_models, system_prompt, user_prompt, max_tokens=3000
            )
        if not parallel_results:
            st.error("All models failed during parallel generation.")
            return None
        results_map = {model: result for result, model in parallel_results}
        st.session_state.compare_results = results_map

    if gen_mode == "Compare (all models, you choose)":
        return {"mode": "compare", "results_map": results_map}

    # Synthesise
    with st.spinner(f"Synthesising with {selected_label}…"):
        model_ids = list(results_map.keys())
        drafts = list(results_map.values())

        def _draft(i):
            return drafts[i] if i < len(drafts) else ""

        def _mid(i):
            return model_ids[i] if i < len(model_ids) else f"Model {chr(65 + i)}"

        synth_prompt = load_prompt("synthesise").format(
            brand_input=brand_input,
            model_a=_mid(0), draft_a=_draft(0),
            model_b=_mid(1), draft_b=_draft(1),
            model_c=_mid(2), draft_c=_draft(2),
            scraped_context=scraped_context or "None",
        )
        try:
            raw_synth, _ = call_with_fallback(
                client, selected_model, system_prompt, synth_prompt, max_tokens=4000
            )
        except Exception as e:
            st.error(f"Synthesis failed: {e}")
            return None

    clean_content, metadata = parse_confidence_metadata(raw_synth)
    return {"mode": "synthesise", "clean_content": clean_content, "metadata": metadata}


def _render_output(output: dict, brand_input: str, scrape_result):
    mode = output["mode"]

    if mode == "compare":
        results_map = output["results_map"]
        st.subheader("🔀 Compare model outputs")
        st.caption("Review each model's output. Click 'Use this output' on the one you prefer.")

        model_tabs = st.tabs([m.split("/")[-1] for m in results_map])
        for tab, (model_id, raw) in zip(model_tabs, results_map.items()):
            with tab:
                clean, _ = parse_confidence_metadata(raw)
                st.markdown(clean)
                if st.button("Use this output", key=f"use_{model_id}"):
                    clean_final, meta = parse_confidence_metadata(raw)
                    st.session_state.pipeline_output = {
                        "mode": "auto",
                        "clean_content": clean_final,
                        "metadata": meta,
                    }
                    st.session_state.compare_results = {}
                    st.rerun()
        return  # stop here — re-render after user picks

    # Auto / Synthesise — show full output
    clean_content = output["clean_content"]
    metadata = output.get("metadata", {})

    st.success("✅ AI Info Page generated!")
    st.subheader("Your AI Info Page")

    tab_preview, tab_raw = st.tabs(["👁️ Preview", "📄 Raw Markdown"])
    with tab_preview:
        st.markdown(clean_content)
    with tab_raw:
        st.code(clean_content, language="markdown")
        fname = "".join(c if c.isalnum() else "-" for c in brand_input).strip("-").lower()
        st.download_button(
            "⬇️ Download as .md",
            data=clean_content,
            file_name=f"ai-info-{fname}.md",
            mime="text/markdown",
        )

    with st.expander("📄 HTML publishing guide"):
        current_date_str = datetime.datetime.now().strftime("%B %Y")
        html_boilerplate = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Official AI Information: {brand_input}</title>
  <meta name="description" content="Verified facts about {brand_input} for AI assistants and LLMs. Last updated {current_date_str}.">
</head>
<body>
  <!-- Convert the markdown above and paste here -->
  <!-- Publish at /ai-info — link from your footer — never redirect this URL -->
</body>
</html>"""
        st.markdown(
            "Publish at `/ai-info` on your domain. Requirements:\n"
            "- ✅ Standard indexable HTML (not `.txt`)\n"
            "- ✅ Clear `<title>` and `<meta description>`\n"
            "- ✅ Linked from site footer\n"
            "- ✅ Simple HTML — no heavy JavaScript\n"
            "- ✅ Stable URL — never redirect"
        )
        st.code(html_boilerplate, language="html")

    st.divider()
    render_confidence_panel(metadata, scrape_result)

    if st.button("🔄 Start over", type="secondary"):
        for k, v in _DEFAULTS.items():
            st.session_state[k] = v
        st.rerun()


# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Settings")

    api_key_input = st.text_input(
        "Bi Frost API Key (override)",
        type="password",
        placeholder="Using key from Streamlit secrets",
        help="Leave blank to use BIFROST_API_KEY from Streamlit secrets or environment.",
    )
    api_key = get_api_key(api_key_input)

    models_cfg = load_models()
    model_options = {m["label"]: m["id"] for m in models_cfg["models"]}
    selected_label = st.selectbox("Primary model", list(model_options.keys()))
    selected_model = model_options[selected_label]

    st.divider()
    st.subheader("Generation mode")
    gen_mode = st.radio(
        "How to generate",
        options=[
            "Auto (single best)",
            "Compare (all models, you choose)",
            "Synthesise (all models, auto-merged)",
        ],
        index=0,
        help=(
            "Auto: fastest, uses your selected model with fallback.\n"
            "Compare: runs all models in parallel, shows tabs — you pick the best.\n"
            "Synthesise: runs all models in parallel, then your selected model merges them."
        ),
    )

    st.divider()
    st.caption("Powered by Pattern Bi Frost · bifrost.pattern.com")

# ── main area ─────────────────────────────────────────────────────────────────

st.title("📋 AI Info Page Generator")
st.markdown(
    "Create a structured **AI Info Page** for any brand. "
    "Combines live web scraping with multi-model AI generation."
)

col_input, col_faq, col_help = st.columns([3, 3, 2], gap="large")

with col_input:
    st.subheader("Brand")
    brand_input = st.text_input(
        "Brand name or website URL",
        placeholder="e.g. rebelsport.com.au or Nike",
    )
    extra_context = st.text_area(
        "Additional context (optional)",
        placeholder="Paste founding story, key facts, or anything the scraper might miss…",
        height=100,
    )
    scrape_external = st.checkbox("Also scrape Wikipedia & Crunchbase", value=True)

with col_faq:
    st.subheader("FAQ Seeding")
    faq_mode = st.radio(
        "FAQ source",
        ["LLM-suggested", "Manual entry", "SEMrush CSV upload"],
        index=0,
    )

    faq_questions: list[str] = []

    if faq_mode == "Manual entry":
        manual_faqs = st.text_area(
            "Enter questions (one per line)",
            placeholder=(
                "Is rebel sport Australian owned?\n"
                "Where is rebel sport headquarters?\n"
                "Does rebel offer price matching?"
            ),
            height=150,
        )
        if manual_faqs.strip():
            faq_questions = [q.strip() for q in manual_faqs.strip().split("\n") if q.strip()]

    elif faq_mode == "SEMrush CSV upload":
        csv_file = st.file_uploader(
            "Upload SEMrush keyword export (.csv)",
            type=["csv"],
            help="Export keyword data from SEMrush. Question-type queries are extracted automatically.",
        )
        if csv_file:
            content = csv_file.read().decode("utf-8", errors="ignore")
            lines = content.split("\n")
            question_words = (
                "what", "who", "where", "when", "how", "why",
                "is ", "does ", "can ", "are ", "which",
            )
            extracted = []
            for line in lines[1:]:
                parts = line.split(",")
                if parts:
                    kw = parts[0].strip().strip('"').lower()
                    if any(kw.startswith(q) for q in question_words):
                        extracted.append(parts[0].strip().strip('"'))
            faq_questions = extracted[:15]
            if faq_questions:
                st.success(f"Extracted {len(faq_questions)} question queries from CSV")
                for q in faq_questions:
                    st.caption(f"• {q}")
            else:
                st.warning("No question-type queries found in CSV. Try manual entry instead.")

    else:  # LLM-suggested
        st.info("Questions will be suggested by the AI after scraping. You'll review them before generating.")

with col_help:
    st.info(
        "**After generating:**\n\n"
        "1. Publish at `/ai-info` on your domain\n"
        "2. Link from your footer\n"
        "3. Update 'Last updated' regularly\n\n"
        "🟢 Green = scraped source\n"
        "🟡 Yellow = LLM knowledge\n"
        "🔴 Red = inferred — verify"
    )

generate_btn = st.button(
    "✨ Generate AI Info Page",
    type="primary",
    disabled=not brand_input,
)

# ── generate button handler ───────────────────────────────────────────────────

if generate_btn:
    if not api_key:
        st.error(
            "No Bi Frost API key found. Add one in the sidebar or set `BIFROST_API_KEY`."
        )
        st.stop()

    # Reset previous output
    st.session_state.pipeline_output = None
    st.session_state.compare_results = {}
    st.session_state.faq_suggestions = []
    st.session_state.await_faq_confirm = False

    # Stage 1: Scraping
    with st.status("🌐 Scraping brand sources…", expanded=True) as scrape_status:
        scraped_context, scrape_result = _run_scraping(brand_input, scrape_external)
        st.session_state.scraped_context = scraped_context
        st.session_state.scrape_result = scrape_result
        scrape_status.update(label="✅ Scraping complete", state="complete")

    # Stage 2: FAQ suggestion (LLM-suggested only)
    if faq_mode == "LLM-suggested":
        with st.spinner("🤔 Generating FAQ suggestions…"):
            client = get_client(api_key)
            try:
                faq_prompt = load_prompt("faq_suggest").format(
                    brand_input=brand_input,
                    brand_type="unknown — infer from context",
                    scraped_context=scraped_context[:3000] if scraped_context else "None",
                )
                raw_faq, _ = call_with_fallback(
                    client, selected_model, "", faq_prompt, max_tokens=500
                )
                raw_faq = raw_faq.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                st.session_state.faq_suggestions = json.loads(raw_faq)
            except Exception as e:
                st.warning(f"Could not generate FAQ suggestions: {e}")
                st.session_state.faq_suggestions = []

        st.session_state.await_faq_confirm = True
        st.rerun()

    # Stages 3+: generation (non-LLM-suggested FAQ modes skip straight here)
    client = get_client(api_key)
    system_prompt = load_prompt("system_prompt")
    user_prompt = build_generation_prompt(brand_input, extra_context, faq_questions, scraped_context)

    output = _run_generation(
        client, selected_model, selected_label, gen_mode,
        models_cfg, system_prompt, user_prompt, brand_input, scraped_context,
    )
    if output:
        st.session_state.pipeline_output = output
        st.rerun()

# ── FAQ confirmation step (LLM-suggested) ────────────────────────────────────

if st.session_state.await_faq_confirm and st.session_state.faq_suggestions:
    st.subheader("📋 Suggested FAQ questions")
    st.caption("Select the questions you want answered in the AI Info Page, then click Confirm.")

    selected_faqs = []
    for q in st.session_state.faq_suggestions:
        if st.checkbox(q, value=True, key=f"faq_{q}"):
            selected_faqs.append(q)

    if st.button("Confirm FAQ selection and generate →", type="secondary"):
        if not api_key:
            st.error("No Bi Frost API key found.")
            st.stop()

        scraped_context = st.session_state.scraped_context
        client = get_client(api_key)
        system_prompt = load_prompt("system_prompt")
        user_prompt = build_generation_prompt(
            brand_input, extra_context, selected_faqs, scraped_context
        )

        output = _run_generation(
            client, selected_model, selected_label, gen_mode,
            models_cfg, system_prompt, user_prompt, brand_input, scraped_context,
        )
        st.session_state.await_faq_confirm = False
        st.session_state.faq_suggestions = []
        if output:
            st.session_state.pipeline_output = output
            st.rerun()
    else:
        st.stop()

# ── render output ─────────────────────────────────────────────────────────────

if st.session_state.pipeline_output:
    _render_output(
        st.session_state.pipeline_output,
        brand_input,
        st.session_state.scrape_result,
    )

# ── footer ────────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    "AI Info Page concept by Amin Foroutan · Popularised by Steve Toth · "
    "Built with Pattern Bi Frost"
)
