"""Web scraper for brand sites and external sources."""
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import quote_plus, urlparse


@dataclass
class ScrapedSource:
    url: str
    source_type: Literal["first_party", "third_party"]
    page_label: str
    text: str
    success: bool = True


@dataclass
class ScrapeResult:
    sources: list[ScrapedSource] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    total_chars: int = 0


_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AIInfoBot/1.0)"}
_TIMEOUT = 8
_PAGE_CHAR_LIMIT = 2000
_MAX_PAGES = 6

_BRAND_PATHS = [
    "/",
    "/about", "/about-us", "/about-rebel", "/our-story",
    "/contact", "/contact-us",
    "/awards", "/press", "/media", "/news",
    "/team", "/leadership", "/people",
    "/services", "/products", "/what-we-do",
]


def _extract_text(html: str) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


def _normalise_url(url: str) -> str | None:
    url = url.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def scrape_brand_site(url: str) -> ScrapeResult:
    import requests

    base = _normalise_url(url)
    if not base:
        return ScrapeResult(failures=["Brand URL: Could not parse domain"])

    sources: list[ScrapedSource] = []
    failures: list[str] = []

    for path in _BRAND_PATHS:
        if len(sources) >= _MAX_PAGES:
            break
        full_url = base + path
        label = "Homepage" if path == "/" else path.strip("/").replace("-", " ").title() + " page"
        try:
            resp = requests.get(full_url, headers=_HEADERS, timeout=_TIMEOUT)
            if resp.status_code != 200:
                failures.append(f"{label}: HTTP {resp.status_code}")
                continue
            text = _extract_text(resp.text)[:_PAGE_CHAR_LIMIT]
            if len(text) < 50:
                continue
            sources.append(ScrapedSource(
                url=full_url,
                source_type="first_party",
                page_label=label,
                text=text,
            ))
        except requests.Timeout:
            failures.append(f"{label}: Request timed out")
        except Exception:
            failures.append(f"{label}: Could not parse page content")

    return ScrapeResult(
        sources=sources,
        failures=failures,
        total_chars=sum(len(s.text) for s in sources),
    )


def scrape_external_sources(brand_name: str) -> ScrapeResult:
    import requests

    sources: list[ScrapedSource] = []
    failures: list[str] = []

    # Wikipedia
    wiki_slug = quote_plus(brand_name.replace(" ", "_"))
    wiki_url = f"https://en.wikipedia.org/wiki/{wiki_slug}"
    try:
        resp = requests.get(wiki_url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            failures.append(f"Wikipedia: HTTP {resp.status_code}")
        else:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            content_div = soup.select("#mw-content-text p")
            paragraphs = [p.get_text(separator=" ").strip() for p in content_div[:3] if p.get_text().strip()]
            text = " ".join(paragraphs)[:_PAGE_CHAR_LIMIT]
            if text:
                sources.append(ScrapedSource(
                    url=wiki_url,
                    source_type="third_party",
                    page_label="Wikipedia",
                    text=text,
                ))
            else:
                failures.append("Wikipedia: No article content found")
    except requests.Timeout:
        failures.append("Wikipedia: Request timed out")
    except Exception:
        failures.append("Wikipedia: Could not parse page content")

    # Crunchbase — attempt but expect frequent blocks
    cb_slug = brand_name.lower().replace(" ", "-")
    cb_url = f"https://www.crunchbase.com/organization/{cb_slug}"
    try:
        resp = requests.get(cb_url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            failures.append(f"Crunchbase: HTTP {resp.status_code}")
        else:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            sections = soup.find_all("section")
            text = " ".join(s.get_text(separator=" ").strip() for s in sections)[:_PAGE_CHAR_LIMIT]
            if text:
                sources.append(ScrapedSource(
                    url=cb_url,
                    source_type="third_party",
                    page_label="Crunchbase",
                    text=text,
                ))
            else:
                failures.append("Crunchbase: No usable content (likely blocked)")
    except requests.Timeout:
        failures.append("Crunchbase: Request timed out")
    except Exception:
        failures.append("Crunchbase: Could not parse page content")

    # LinkedIn — always skipped
    failures.append("LinkedIn: Skipped — blocks all automated scrapers")

    return ScrapeResult(
        sources=sources,
        failures=failures,
        total_chars=sum(len(s.text) for s in sources),
    )


def merge_scrape_results(*results: ScrapeResult) -> ScrapeResult:
    sources: list[ScrapedSource] = []
    failures: list[str] = []
    for r in results:
        sources.extend(r.sources)
        failures.extend(r.failures)
    return ScrapeResult(
        sources=sources,
        failures=failures,
        total_chars=sum(len(s.text) for s in sources),
    )


def format_sources_for_prompt(result: ScrapeResult) -> str:
    if not result.sources:
        return ""
    blocks = []
    for s in result.sources:
        domain = urlparse(s.url).netloc
        blocks.append(
            f"--- SOURCE: {s.page_label} ({s.source_type}) | {domain}{urlparse(s.url).path} ---\n{s.text}"
        )
    return "\n\n".join(blocks)
