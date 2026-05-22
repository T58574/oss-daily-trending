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
    header = "⚡ <b>DEV DIGEST [Fallback]</b>\n"
    lines = [header, "───────\n🚀 <b>TECH &amp; AI NEWS</b>"]
    for i, s in enumerate(hn_stories[:3], 1):
        title = html.escape(s.get("title") or "")
        url = html.escape(s.get("url") or "")
        lines.append(f"{i}. <a href=\"{url}\">{title}</a>")
        
    lines.append("\n───────\n🤖 <b>AI MODELS &amp; HACKS</b>")
    for i, m in enumerate(hf_models[:2], 1):
        name = html.escape(m.get("repo_name") or "")
        url = f"https://huggingface.co/{name}"
        lines.append(f"{i}. <a href=\"{url}\">{name}</a> <code>{m.get('pipeline_tag')}</code>")
        
    lines.append("\n───────\n📦 <b>MCP &amp; OPEN SOURCE GOLD</b>")
    for i, r in enumerate(github_repos[:3], 1):
        name = html.escape(r.get("repo_name") or "")
        url = f"https://github.com/{name}"
        desc = html.escape((r.get("description") or "")[:80])
        lines.append(f"{i}. <a href=\"{url}\">{name}</a>\n   <i>{desc}</i>")
        
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
