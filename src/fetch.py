"""Step 1 (code, no model): turn a website address into clean text.

Why code and not the model: fetching, parsing and trimming is deterministic, free and fast.
The model only ever sees the trimmed text this file returns.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; opener-tool/0.1; +https://github.com/amustprocoder)"
TIMEOUT = 15
MAX_CHARS = 6000          # about 1,500 tokens: enough for a homepage, cheap to send
ABOUT_PATHS = ("/about", "/about-us", "/company")   # tried only when the homepage is thin
MIN_CHARS = 600           # below this the homepage was probably JS-only; try /about and a text proxy


def normalise(url: str) -> str:
    url = url.strip()
    if not re.match(r"^https?://", url, flags=re.I):
        url = "https://" + url
    return url


def _get(url: str) -> requests.Response | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
            return r
    except requests.RequestException:
        pass
    return None


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "iframe"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc = ""
    m = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if m and m.get("content"):
        desc = m["content"]
    body = soup.get_text("\n", strip=True)
    body = re.sub(r"\n{2,}", "\n", body)
    head = "\n".join(x for x in (title, desc) if x)
    return (head + "\n" + body).strip()


def _text_proxy(url: str) -> str:
    """Last resort for JavaScript-only sites: a public page-to-text service (no key, free)."""
    r = _get("https://r.jina.ai/" + url)
    if r is None:
        try:
            r2 = requests.get("https://r.jina.ai/" + url, headers={"User-Agent": UA}, timeout=TIMEOUT)
            return r2.text if r2.status_code == 200 else ""
        except requests.RequestException:
            return ""
    return r.text


def fetch_site_text(url: str) -> dict:
    """Return {"url", "final_url", "text", "source", "chars"}. Never raises; empty text means fetch failed."""
    url = normalise(url)
    r = _get(url)
    text, source, final_url = "", "none", url
    if r is not None:
        final_url = r.url
        text = html_to_text(r.text)
        source = "homepage"
        if len(text) < MIN_CHARS:
            for p in ABOUT_PATHS:
                r2 = _get(urljoin(final_url, p))
                if r2 is not None:
                    extra = html_to_text(r2.text)
                    if len(extra) > len(text):
                        text = text + "\n" + extra
                        source = "homepage+about"
                        break
    if len(text) < MIN_CHARS:
        proxy = _text_proxy(url)
        if len(proxy) > len(text):
            text, source = proxy, "text-proxy"
    text = text[:MAX_CHARS]
    return {"url": url, "final_url": final_url, "domain": urlparse(final_url).netloc,
            "text": text, "source": source, "chars": len(text)}
