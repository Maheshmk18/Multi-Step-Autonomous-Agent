import ipaddress
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from tavily import TavilyClient

from app.config import settings


mcp = FastMCP("search")


def _client() -> TavilyClient:
    if not settings.tavily_api_key:
        raise RuntimeError("Tavily is not configured. Set TAVILY_API_KEY in backend/.env.")
    return TavilyClient(api_key=settings.tavily_api_key)


@mcp.tool(
    name="web_search",
    description="Search the public web and return titles, URLs, and short source excerpts.",
)
def web_search(query: str, max_results: int = 5) -> dict[str, object]:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("Search query cannot be empty.")
    result = _client().search(
        query=normalized_query,
        max_results=max(1, min(max_results, 10)),
        include_answer=False,
        include_raw_content=False,
    )
    return {
        "results": [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score"),
            }
            for item in result.get("results", [])
        ]
    }


@mcp.tool(
    name="fetch_page",
    description="Extract readable text from one public HTTP or HTTPS page URL.",
)
def fetch_page(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must use HTTP or HTTPS and include a host.")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Local network URLs are not supported.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Local network URLs are not supported.")
    response = _client().extract(urls=[url])
    pages = response.get("results", [])
    if not pages:
        return {"url": url, "content": "", "error": "No readable page content was returned."}
    page = pages[0]
    return {
        "url": page.get("url", url),
        "content": str(page.get("raw_content", ""))[:20000],
    }


if __name__ == "__main__":
    mcp.run()
