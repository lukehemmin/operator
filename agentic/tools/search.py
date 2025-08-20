from __future__ import annotations

import urllib.parse
import urllib.request
import re
from typing import Dict, Any, List


def web_search(query: str, max_results: int = 5, timeout: int = 30) -> Dict[str, Any]:
    url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return {"query": query, "error": str(e)}
    # crude parse
    results: List[Dict[str, Any]] = []
    for m in re.finditer(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
        href = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2))
        results.append({"title": title.strip(), "url": href})
        if len(results) >= max_results:
            break
    return {"query": query, "results": results}

