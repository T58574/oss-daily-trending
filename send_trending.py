import httpx
import os
import json
import html

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

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

def summarize_with_groq(repos):
    if not GROQ_API_KEY:
        print("!!! GROQ_API_KEY not set, skipping AI summary")
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    
    print(f"--- sending {len(repos)} repos to groq (llama-3.3-70b) ---")
    
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
    
    ВАЖНОЕ ПРАВИЛО ПО ФОРМАТУ (Telegram HTML):
    - Используй ТОЛЬКО эти тэги: <b>текст</b> (жирный), <i>текст</i> (курсив), <a href="url">текст</a> (ссылка).
    - НЕ используй Markdown символы типа * или _.
    - Весь текст должен быть валидным HTML. Специальные символы <, >, & должны быть заменены на &lt;, &gt;, &amp; (но нейронка может просто писать обычный текст, я его экранирую).
    
    Структура сообщения:
    1. Заголовок: 🔥 <b>GitHub Trending (24h)</b>
    2. Выдели 5-7 самых мощных проектов. 
    3. Для каждого: <a href="https://github.com/название">Название</a>, суть одной фразой и кратко почему это круто.
    4. В конце — краткий итог: главный тренд дня.
    
    Данные:
    {json.dumps(repos_context, ensure_ascii=False)}
    
    Отвечай ТОЛЬКО готовым текстом сообщения в формате HTML. Не пиши преамбул.
    """

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Ты эксперт, который пишет в Telegram на HTML. Используешь тэги <b>, <i>, <a>."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2048
    }

    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=60)
        print(f"groq status code: {r.status_code}")
        r.raise_for_status()
        result = r.json()
        
        content = result['choices'][0]['message']['content']
        print("--- groq response received successfully ---")
        return content.strip()
    except Exception as e:
        print(f"!!! groq error: {e}")
        return None

def format_fallback_message(repos):
    header = "🔥 <b>GitHub Trending (24h) [Fallback]</b>\n"
    lines = [header]
    for i, repo in enumerate(repos[:10], 1):
        name = html.escape(repo.get("repo_name") or "unknown/repo")
        desc = html.escape((repo.get("description") or "")[:100])
        stars = repo.get("stars") or 0
        lang = html.escape(repo.get("primary_language") or "—")
        link = f"https://github.com/{name}"
        
        line = f"{i}. <a href=\"{link}\">{name}</a> ⭐{stars} <code>{lang}</code>"
        lines.append(line)
        if desc:
            lines.append(f"   <i>{desc}</i>")
    return "\n".join(lines)

def send(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("error: BOT_TOKEN or CHAT_ID not set")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        r = httpx.post(url, json=payload, timeout=20)
        if r.status_code != 200:
            print(f"error sending message: {r.text}")
        else:
            print("message sent successfully")
    except Exception as e:
        print(f"error sending message: {e}")

if __name__ == "__main__":
    trending_repos = get_trending()
    print(f"fetched {len(trending_repos)} repos from ossinsight")
    
    message = summarize_with_groq(trending_repos)
    
    if message:
        print("sending AI generated message (Groq HTML)")
        send(message)
    else:
        print("falling back to manual formatting")
        fallback = format_fallback_message(trending_repos)
        send(fallback)
