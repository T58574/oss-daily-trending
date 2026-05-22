import httpx
import os
import json
import html
import re
import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("CHAT_ID", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"error loading history: {e}")
    return {"posted_repos": {}}

def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"error saving history: {e}")

def filter_new_repos(repos, history, days_threshold=7):
    now = datetime.datetime.now(datetime.timezone.utc)
    posted_repos = history.get("posted_repos", {})
    
    filtered = []
    for repo in repos:
        repo_name = repo.get("repo_name")
        if not repo_name:
            continue
            
        posted_at_str = posted_repos.get(repo_name)
        if posted_at_str:
            try:
                posted_at = datetime.datetime.fromisoformat(posted_at_str)
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=datetime.timezone.utc)
                age = now - posted_at
                if age.days < days_threshold:
                    print(f"skipping {repo_name} (posted {age.days} days ago)")
                    continue
            except Exception as e:
                print(f"error parsing date for {repo_name}: {e}")
                
        filtered.append(repo)
    return filtered

def extract_posted_repos(text, repos):
    posted_names = []
    for r in repos:
        name = r.get("repo_name")
        if not name:
            continue
        if name.lower() in text.lower():
            posted_names.append(name)
    return posted_names

def update_history(posted_repo_names, history):
    now = datetime.datetime.now(datetime.timezone.utc)
    posted_repos = history.get("posted_repos", {})
    
    for name in posted_repo_names:
        posted_repos[name] = now.isoformat()
        
    pruned_posted_repos = {}
    for name, date_str in posted_repos.items():
        try:
            posted_at = datetime.datetime.fromisoformat(date_str)
            if posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=datetime.timezone.utc)
            if (now - posted_at).days < 30:
                pruned_posted_repos[name] = date_str
            else:
                print(f"pruning old history entry from database: {name}")
        except Exception:
            pruned_posted_repos[name] = date_str
            
    history["posted_repos"] = pruned_posted_repos
    return history

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
        print(f"error fetching GitHub trending data: {e}")
        return []

def get_hn_stories():
    url = "https://hn.algolia.com/api/v1/search?tags=front_page"
    try:
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
    except Exception as e:
        print(f"error fetching HN stories: {e}")
        return []

def get_hf_models():
    url = "https://huggingface.co/api/trending"
    try:
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
    except Exception as e:
        print(f"error fetching HF models: {e}")
        return []

def summarize_with_groq(hn_stories, hf_models, github_repos):
    if not GROQ_API_KEY:
        print("!!! GROQ_API_KEY not set, skipping AI summary")
        return None

    url = "https://api.groq.com/openai/v1/chat/completions"
    
    print(f"--- sending digest to groq (HN: {len(hn_stories)}, HF: {len(hf_models)}, GitHub: {len(github_repos)}) ---")
    
    context = {
        "hacker_news": hn_stories,
        "hugging_face_models": hf_models,
        "github_trending": [
            {
                "name": r.get("repo_name"),
                "desc": r.get("description"),
                "lang": r.get("primary_language"),
                "stars": r.get("stars")
            }
            for r in github_repos
        ]
    }

    prompt = f"""
    Ты — элитный тех-блогер и эксперт по IT, ИИ и разработке.
    Ниже собрана самая актуальная информация за последние 24 часа из трех главных источников:
    1. Горячие новости и дискуссии разработчиков (с Hacker News)
    2. Взлетающие ИИ-модели (с Hugging Face)
    3. Трендовые репозитории GitHub (из OSSInsight)
    
    Твоя задача: Составить УМНЫЙ, СТИЛЬНЫЙ и супер-интересный ежедневный дайджест на РУССКОМ языке для Telegram-канала.
    
    ВАЖНОЕ ПРАВИЛО ПО ФОРМАТУ (Telegram HTML):
    - Используй ТОЛЬКО эти тэги: <b>текст</b> (жирный), <i>текст</i> (курсив), <a href="url">текст</a> (ссылка), <code>код</code>.
    - НЕ используй Markdown символы типа * или _ или ```.
    - Весь текст должен быть валидным HTML. Специальные символы <, >, & должны быть заменены на &lt;, &gt;, &amp;.
    
    Стиль:
    - Пиши емко, остроумно, без корпоративного пафоса и лишней "воды". Читатель должен сразу понять суть.
    - Разделяй блоки красивыми разделителями ───────
    - Используй фиксированные эмодзи для структуры:
      🚀 для главных технологических новостей и трендов
      🤖 для ИИ-моделей и прорывов в Machine Learning
      📦 для крутых Open-Source репозиториев
      
    Структура сообщения:
    1. Заголовок дня: ⚡ <b>DEV DIGEST: [Интригующий заголовок главного тренда дня]</b>
    
    2. Раздел 🚀 <b>TECH NEWS</b>
       Выдели 2-3 самых значимых новости/дискуссии с Hacker News.
       Каждый пункт: Название ссылки, емкая суть одной фразой (почему это важно/что случилось).
       Пример: <a href="URL">Title</a> — [Смысл]
       
    3. Раздел 🤖 <b>AI &amp; ML FRONT</b>
       Выдели 2 самых интересных релиза с Hugging Face.
       Каждый пункт: <a href="https://huggingface.co/id">id</a> — [Что делает модель и почему она взлетает]
       
    4. Раздел 📦 <b>OPEN SOURCE GOLD</b>
       Выдели 2-3 лучших репозитория с GitHub.
       Каждый пункт: <a href="https://github.com/name">Name</a> — [Суть проекта одной фразой]
       
    5. В конце — 💡 <b>INSIGHT OF THE DAY</b> (одна острая/умная мысль о сегодняшней повестке дня).
    
    Входные данные:
    {json.dumps(context, ensure_ascii=False)}
    
    Отвечай ТОЛЬКО готовым текстом сообщения в формате HTML. Не пиши преамбул.
    """

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "Ты эксперт, который пишет в Telegram на HTML. Используешь тэги <b>, <i>, <a>, <code>."},
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

def format_fallback_message(hn_stories, hf_models, github_repos):
    header = "⚡ <b>DEV DIGEST [Fallback]</b>\n"
    lines = [header, "───────\n🚀 <b>TECH NEWS</b>"]
    for i, s in enumerate(hn_stories[:3], 1):
        title = html.escape(s.get("title") or "")
        url = html.escape(s.get("url") or "")
        lines.append(f"{i}. <a href=\"{url}\">{title}</a>")
        
    lines.append("\n───────\n🤖 <b>AI &amp; ML FRONT</b>")
    for i, m in enumerate(hf_models[:2], 1):
        name = html.escape(m.get("repo_name") or "")
        url = f"https://huggingface.co/{name}"
        lines.append(f"{i}. <a href=\"{url}\">{name}</a> <code>{m.get('pipeline_tag')}</code>")
        
    lines.append("\n───────\n📦 <b>OPEN SOURCE GOLD</b>")
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

if __name__ == "__main__":
    print("--- starting dev daily digest collection ---")
    
    # 1. Fetch GitHub repos
    trending_repos = get_trending()
    print(f"fetched {len(trending_repos)} repos from ossinsight")
    
    # 2. Fetch Hacker News stories
    hn_stories = get_hn_stories()
    print(f"fetched {len(hn_stories)} stories from hacker news")
    
    # 3. Fetch Hugging Face models
    hf_models = get_hf_models()
    print(f"fetched {len(hf_models)} models from hugging face")
    
    # Load database history
    history = load_history()
    
    # Filter out recently posted repos (GitHub and HuggingFace both use repo_name key!)
    new_repos = filter_new_repos(trending_repos, history, days_threshold=7)
    print(f"after filtering duplicates, {len(new_repos)} GitHub repos remaining")
    
    new_models = filter_new_repos(hf_models, history, days_threshold=7)
    print(f"after filtering duplicates, {len(new_models)} Hugging Face models remaining")
    
    # Fallback to complete lists if too few new items to avoid dry digests
    repos_to_send = new_repos if len(new_repos) >= 3 else trending_repos
    models_to_send = new_models if len(new_models) >= 2 else hf_models
    stories_to_send = hn_stories # HN stories don't repeat, no filter needed
    
    message = summarize_with_groq(stories_to_send, models_to_send, repos_to_send)
    
    if message:
        print("validating and sanitizing AI generated message HTML")
        sanitized_message = safe_escape_html(message)
        print("sending AI generated message (Groq HTML)")
        send(sanitized_message)
        
        # Extract and update posted repositories and models (both use repo_name key)
        posted_repos = extract_posted_repos(sanitized_message, repos_to_send)
        posted_models = extract_posted_repos(sanitized_message, models_to_send)
        
        posted_all = posted_repos + posted_models
        if posted_all:
            print(f"marking items as posted in database: {posted_all}")
            history = update_history(posted_all, history)
            save_history(history)
    else:
        print("falling back to manual formatting")
        fallback = format_fallback_message(stories_to_send, models_to_send, repos_to_send)
        send(fallback)
