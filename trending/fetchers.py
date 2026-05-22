import time
import httpx

def with_retry(retries=3, backoff_factor=2):
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = 1.0
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except httpx.HTTPError as e:
                    if attempt == retries - 1:
                        print(f"!!! all attempts failed for {func.__name__}: {e}")
                        raise
                    print(f"--- network error in {func.__name__} (attempt {attempt + 1}/{retries}): {e}. retrying in {delay}s...")
                    time.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator

@with_retry(retries=3)
def get_trending():
    url = "https://api.ossinsight.io/v1/trends/repos/"
    r = httpx.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "data" in data:
        rows = data["data"].get("rows", [])
        return rows[:15]
    return []

@with_retry(retries=3)
def get_hn_stories():
    url = "https://hn.algolia.com/api/v1/search?tags=front_page"
    r = httpx.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    hits = data.get("hits", [])
    stories = []
    for h in hits[:15]:
        title = h.get("title")
        story_url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        points = h.get("points") or 0
        if title:
            stories.append({
                "title": title,
                "url": story_url,
                "points": points
            })
    return stories

@with_retry(retries=3)
def get_hf_models():
    url = "https://huggingface.co/api/trending"
    r = httpx.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    models = []
    if isinstance(data, dict):
        trending_list = data.get("recentlyTrending", [])
        for item in trending_list:
            if item.get("repoType") == "model":
                repo_data = item.get("repoData", {})
                model_id = repo_data.get("id")
                if model_id:
                    models.append({
                        "repo_name": model_id,
                        "likes": repo_data.get("likes") or 0,
                        "downloads": repo_data.get("downloads") or 0,
                        "pipeline_tag": repo_data.get("pipeline_tag") or "—"
                    })
    return models[:15]
