import httpx
import os
import re

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def escape_markdown(text):
    """
    Helper function to escape telegram markdown v2 special characters.
    """
    if not text:
        return ""
    # Characters that must be escaped in MarkdownV2
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

def get_trending():
    # using ossinsight api for top trending repos (24h)
    url = "https://api.ossinsight.io/v1/trends/repos/"
    try:
        r = httpx.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        # ossinsight response structure: {"data": {"rows": [...], ...}}
        if isinstance(data, dict) and "data" in data:
            rows = data["data"].get("rows", [])
            return rows[:10]
        return []
    except Exception as e:
        print(f"error fetching data: {e}")
        return []

def format_message(repos):
    if not repos:
        return "⚠️ *не удалось получить тренды сегодня*"

    lines = ["🔥 *GitHub Trending (24h)*\n"]
    for i, repo in enumerate(repos, 1):
        # ossinsight keys: repo_name, description, stars, primary_language
        name = repo.get("repo_name") or "unknown/repo"
        desc = repo.get("description") or ""
        # truncate description
        if len(desc) > 100:
            desc = desc[:97] + "..."
        
        stars = repo.get("stars") or 0
        lang = repo.get("primary_language") or "—"
        
        # escaping for markdownv2
        safe_name = escape_markdown(name)
        safe_desc = escape_markdown(desc)
        safe_lang = escape_markdown(lang)
        
        link = f"https://github.com/{name}"
        
        line = f"{i}\\. [{safe_name}]({link}) ⭐{stars} `{safe_lang}`"
        lines.append(line)
        if safe_desc:
            lines.append(f"   _{safe_desc}_")
            
    return "\n".join(lines)

def send(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("error: BOT_TOKEN or CHAT_ID not set")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True
    }
    
    try:
        r = httpx.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print("message sent successfully")
    except Exception as e:
        print(f"error sending message: {e}")
        if r := getattr(e, 'response', None):
            print(f"telegram response: {r.text}")

if __name__ == "__main__":
    trending_repos = get_trending()
    message = format_message(trending_repos)
    send(message)
