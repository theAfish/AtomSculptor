"""DuckDuckGo search tools for the agent team."""

from ddgs import DDGS
from ddgs.exceptions import DDGSException


def web_search(query: str, max_results: int = 5, region: str = "us-en", timelimit: str | None = None) -> dict:
    """Search the web using DuckDuckGo.

    Args:
        query: Search query keywords.
        max_results: Maximum number of results to return. Defaults to 5.
        region: Region for search results (e.g. us-en, uk-en, ru-ru). Defaults to "us-en".
        timelimit: Time limit for results - "d" (day), "w" (week), "m" (month), "y" (year). Defaults to None.

    Returns:
        Dict with search results list containing title, href, and body for each result.
    """
    try:
        results = list(DDGS().text(
            query,
            region=region,
            max_results=max_results,
            timelimit=timelimit,
        ))
    except DDGSException as e:
        return {"results": [], "error": str(e)}
    return {"results": results}


def web_search_news(query: str, max_results: int = 5, region: str = "us-en", timelimit: str | None = None) -> dict:
    """Search for recent news articles using DuckDuckGo.

    Args:
        query: Search query keywords.
        max_results: Maximum number of results to return. Defaults to 5.
        region: Region for news results (e.g. us-en, uk-en, ru-ru). Defaults to "us-en".
        timelimit: Time limit for results - "d" (day), "w" (week), "m" (month). Defaults to None.

    Returns:
        Dict with news results list containing date, title, body, url, and source for each result.
    """
    try:
        results = list(DDGS().news(
            query,
            region=region,
            max_results=max_results,
            timelimit=timelimit,
        ))
    except DDGSException as e:
        return {"results": [], "error": str(e)}
    return {"results": results}
