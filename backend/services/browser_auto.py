import aiohttp
import asyncio
import time
import re
from html.parser import HTMLParser

TIMEOUT = 30
MAX_CONTENT = 5 * 1024 * 1024

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._result = []
        self._skip = False
        self._skip_tags = {"script", "style", "noscript"}
        self._links = []
        self._images = []
        self._title = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag in self._skip_tags:
            self._skip = True
        if tag == "a" and "href" in attrs_dict:
            self._links.append(attrs_dict["href"])
        if tag == "img" and "src" in attrs_dict:
            self._images.append(attrs_dict["src"])
        if tag == "title":
            self._title = ""

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self._result.append(text)

    def get_text(self):
        return " ".join(self._result)

class BrowserAutomation:
    def __init__(self):
        self._session = None

    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                headers={"User-Agent": "NexusAgent/1.0"}
            )
        return self._session

    async def navigate(self, url: str) -> dict:
        start = time.time()
        try:
            session = await self._get_session()
            async with session.get(url) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "text" not in content_type and "html" not in content_type and "json" not in content_type:
                    return {
                        "success": False,
                        "error": f"Tipo de conteúdo não suportado: {content_type}",
                        "elapsed_ms": int((time.time() - start) * 1000)
                    }
                text = await resp.text(errors="replace")
                text = text[:MAX_CONTENT]
                return {
                    "success": True,
                    "url": str(resp.url),
                    "status": resp.status,
                    "content": text,
                    "content_type": content_type,
                    "elapsed_ms": int((time.time() - start) * 1000)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "elapsed_ms": int((time.time() - start) * 1000)
            }

    async def extract_text(self, url: str) -> dict:
        start = time.time()
        try:
            session = await self._get_session()
            async with session.get(url) as resp:
                if resp.status != 200:
                    return {"success": False, "error": f"HTTP {resp.status}", "elapsed_ms": int((time.time() - start) * 1000)}
                html = await resp.text(errors="replace")
                html = html[:MAX_CONTENT]
                parser = HTMLTextExtractor()
                parser.feed(html)
                base_url = str(resp.url)
                links = [l if l.startswith("http") else base_url.rstrip("/") + "/" + l.lstrip("/") for l in parser._links[:100]]
                images = [i if i.startswith("http") else base_url.rstrip("/") + "/" + i.lstrip("/") for i in parser._images[:100]]
                title = parser._title
                if not title:
                    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
                    if m:
                        title = m.group(1).strip()
                return {
                    "success": True,
                    "title": title,
                    "text": parser.get_text()[:100000],
                    "links": links,
                    "images": images,
                    "url": str(resp.url),
                    "elapsed_ms": int((time.time() - start) * 1000)
                }
        except Exception as e:
            return {"success": False, "error": str(e), "elapsed_ms": int((time.time() - start) * 1000)}

    async def search(self, query: str) -> dict:
        try:
            session = await self._get_session()
            search_url = f"https://html.duckduckgo.com/html/?q={query}"
            async with session.get(search_url) as resp:
                html = await resp.text(errors="replace")
                results = []
                for m in re.finditer(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</span>', html, re.DOTALL):
                    url = m.group(1)
                    title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                    snippet = re.sub(r"<[^>]+>", "", m.group(3)).strip()
                    results.append({"title": title, "url": url, "snippet": snippet})
                    if len(results) >= 10:
                        break
                return {"success": True, "query": query, "results": results, "count": len(results)}
        except Exception as e:
            return {"success": False, "error": str(e), "results": []}

    async def screenshot(self, url: str) -> dict:
        return {
            "success": False,
            "error": "Screenshot requer Playwright (não disponível). Use extract_text.",
            "url": url
        }

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

browser_auto = BrowserAutomation()
