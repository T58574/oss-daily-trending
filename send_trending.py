import httpx
import os
import re
import json

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

def escape_markdown(text):
    if not text:
        return ""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    res = ""
    for c in str(text):
        if c in escape_chars:
            res += "\\" + c
        else:
            res += c
    return res

def get_trending():
    url = "https://api.ossinsight.io/v1/trends/repos/"
    try:
        r = httpx.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "data" in data:
            rows = data["data"].get("rows", [])
            return rows[:15]
        return []
    except Exception as e:
        print(f"error fetching data: {e}")
        return []

def summarize_with_gemini(repos):
    if not GEMINI_API_KEY:
        print("!!! GEMINI_API_KEY not set, skipping AI summary")
        return None

    # используем актуальную модель gemini-2.0-flash
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    
    print(f"--- sending {len(repos)} repos to gemini-2.0-flash ---")
    
    repos_context = []
    for r in repos:
        repos_context.append({
            "name": r.get("repo_name"),
            "desc": r.get("description"),
            "lang": r.get("primary_language"),
            "stars": r.get("stars")
        })

    prompt = f"""
    Ты — эксперт по Open Source и крутой тех-блогер. 
    Ниже список трендовых репозиториев GitHub за последние 24 часа.
    
    Твоя задача: Составь ИНТЕРЕСНЫЙ и СТИЛЬНЫЙ дайджест на РУССКОМ языке.
    
    ВАЖНОЕ ПРАВИЛО ПО ФОРМАТУ (Telegram MarkdownV2):
    - Экранируй ВСЕ спецсимволы: _ * [ ] ( ) ~ ` > # + - = | {{ }} . ! (используй обратный слэш \\)
    - Пример: [Ссылка](url), заголовок: *Заголовок*, список: 1\\. Элемент
    
    Структура сообщения:
    1. Заголовок: 🔥 GitHub Trending (24h)
    2. Выдели 5 самых мощных проектов. 
    3. Для каждого: [Название](https://github.com/название), суть одной фразой и почему это "маст-хэв".
    4. В конце — краткий итог: какой тренд сегодня (например, "AI всё еще захватывает мир").
    
    Данные:
    {json.dumps(repos_context, ensure_ascii=False)}
    
    Отвечай ТОЛЬКО готовым текстом сообщения, который я могу сразу отправить в Telegram.
    """

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        r = httpx.post(url, json=payload, timeout=60)
        print(f"gemini status code: {r.status_code}")
        r.raise_for_status()
        result = r.json()
        
        if 'candidates' in result and result['candidates']:
            content = result['candidates'][0]['content']['parts'][0]['text']
            print("--- gemini response received successfully ---")
            return content.strip()
        else:
            print(f"!!! gemini returned unexpected structure: {result}")
            return None
    except Exception as e:
        print(f"!!! gemini error: {e}")
        if r := getattr(e, 'response', None):
            print(f"gemini full response: {r.text}")
        return None

def format_fallback_message(repos):
    header = escape_markdown("🔥 GitHub Trending (24h) [Fallback]")
    lines = [f"*{header}*\n"]
    for i, repo in enumerate(repos[:10], 1):
        name = repo.get("repo_name") or "unknown/repo"
        desc = repo.get("description") or ""
        stars = repo.get("stars") or 0
        lang = repo.get("primary_language") or "—"
        
        safe_name = escape_markdown(name)
        safe_desc = escape_markdown(desc[:100])
        safe_lang = escape_markdown(lang)
        safe_stars = escape_markdown(str(stars))
        link = f"https://github.com/{name}".replace("\\", "\\\\").replace(")", "\\)")
        
        line = f"{escape_markdown(str(i))}\\. [{safe_name}]({link}) ⭐{safe_stars} `{safe_lang}`"
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
        r = httpx.post(url, json=payload, timeout=20)
        r.raise_for_status()
        print("message sent successfully")
    except Exception as e:
        print(f"error sending message: {e}")
        if r := getattr(e, 'response', None):
            print(f"telegram response: {r.text}")

if __name__ == "__main__":
    trending_repos = get_trending()
    print(f"fetched {len(trending_repos)} repos from ossinsight")
    
    message = summarize_with_gemini(trending_repos)
    
    if message:
        print("sending AI generated message")
        send(message)
    else:
        print("falling back to manual formatting")
        fallback = format_fallback_message(trending_repos)
        send(fallback)
