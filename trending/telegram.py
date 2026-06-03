import html
import re
import httpx
from trending.config import BOT_TOKEN, CHAT_ID

def safe_escape_html(text):
    tag_re = re.compile(r'(</?[a-zA-Z]+(?:\s+[a-zA-Z]+="[^"]*")*\s*/?>)')
    tokens = tag_re.split(text)
    result = []
    allowed_tag_names = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "span", "tg-spoiler", "a", "code", "pre"}
    open_tags = []
    
    for i, token in enumerate(tokens):
        if i % 2 == 1:
            tag_name_match = re.match(r'</?([a-zA-Z]+)', token)
            if tag_name_match:
                tag_name = tag_name_match.group(1).lower()
                if tag_name in allowed_tag_names:
                    if token.startswith("</"):
                        if open_tags and open_tags[-1] == tag_name:
                            open_tags.pop()
                            result.append(token)
                        else:
                            result.append(html.escape(token))
                    else:
                        if not token.endswith("/>"):
                            open_tags.append(tag_name)
                        result.append(token)
                else:
                    result.append(html.escape(token))
            else:
                result.append(html.escape(token))
        else:
            escaped = html.escape(token)
            escaped = escaped.replace("&amp;lt;", "&lt;").replace("&amp;gt;", "&gt;").replace("&amp;amp;", "&amp;").replace("&amp;quot;", "&quot;").replace("&amp;apos;", "&apos;")
            result.append(escaped)
            
    for tag in reversed(open_tags):
        result.append(f"</{tag}>")
        
    return "".join(result)

def format_fallback_message(hn_stories, hf_models, github_repos):
    lines = []

    # 1. GitHub Repo
    if github_repos:
        r = github_repos[0]
        name = html.escape(r.get("repo_name") or "")
        url = f"https://github.com/{name}"
        desc = html.escape((r.get("description") or "")[:150])
        lines.append("📁 категория: open source")
        lines.append(f"🔥 проект: {name}")
        lines.append(f"💡 суть: {desc}")
        lines.append("🛠 профит: Инструмент для разработчиков.")
        lines.append(f"🔗 <a href=\"{url}\">ссылка на репозиторий</a>")
        lines.append("──────")
        
    # 2. AI Model
    if hf_models:
        m = hf_models[0]
        name = html.escape(m.get("repo_name") or "")
        url = f"https://huggingface.co/{name}"
        lines.append("📁 категория: ai модели")
        lines.append(f"🔥 проект: {name}")
        lines.append(f"💡 суть: Модель {m.get('pipeline_tag')}")
        lines.append("🛠 профит: Запуск AI задач.")
        lines.append(f"🔗 <a href=\"{url}\">ссылка на модель</a>")
        lines.append("──────")

    # 3. Hacker News
    if hn_stories:
        s = hn_stories[0]
        title = html.escape(s.get("title") or "")
        url = html.escape(s.get("url") or "")
        lines.append("📁 категория: tech news")
        lines.append(f"🔥 проект: {title}")
        lines.append("💡 суть: Обсуждение в сообществе")
        lines.append("🛠 профит: Быть в курсе трендов.")
        lines.append(f"🔗 <a href=\"{url}\">ссылка на новость</a>")
        lines.append("──────")
        
    return "\n\n".join(lines)

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

def send_error_alert(traceback_str):
    if not BOT_TOKEN or not CHAT_ID:
        return
    
    alert_text = (
        f"🚨 <b>CRITICAL SYSTEM ALERT</b>\n"
        f"───────\n"
        f"<b>daily trending aggregator has crashed!</b>\n\n"
        f"<b>error traceback:</b>\n"
        f"<pre>{html.escape(traceback_str[:3500])}</pre>"
    )
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": alert_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        httpx.post(url, json=payload, timeout=20)
    except Exception as e:
        print(f"error sending alert to telegram: {e}")
