import os
import json
import datetime
from trending.config import HISTORY_FILE

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
