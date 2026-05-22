import traceback
from trending.fetchers import get_trending, get_hn_stories, get_hf_models
from trending.anti_fraud import is_suspicious
from trending.database import load_history, filter_new_repos, extract_posted_repos, update_history, save_history
from trending.summarizer import summarize_with_groq
from trending.telegram import safe_escape_html, send, send_error_alert, format_fallback_message

def main():
    try:
        print("--- starting modular dev daily digest collection ---")
        
        # 1. Fetch GitHub repos
        trending_repos = get_trending()
        print(f"fetched {len(trending_repos)} repos from ossinsight")
        
        # 2. Fetch Hacker News stories
        hn_stories = get_hn_stories()
        print(f"fetched {len(hn_stories)} stories from hacker news")
        
        # 3. Fetch Hugging Face models
        hf_models = get_hf_models()
        print(f"fetched {len(hf_models)} models from hugging face")
        
        # 4. Programmatic anti-fraud filtering
        trending_repos = [r for r in trending_repos if not (is_suspicious(r.get("repo_name")) or is_suspicious(r.get("description")))]
        hn_stories = [s for s in hn_stories if not (is_suspicious(s.get("title")) or is_suspicious(s.get("url")))]
        hf_models = [m for m in hf_models if not is_suspicious(m.get("repo_name"))]
        print(f"after anti-fraud filtering: {len(trending_repos)} repos, {len(hn_stories)} stories, {len(hf_models)} models")
        
        # 5. Load database history
        history = load_history()
        
        # 6. Filter out recently posted repos/models (GitHub and HuggingFace both use repo_name key!)
        new_repos = filter_new_repos(trending_repos, history, days_threshold=7)
        print(f"after filtering duplicates, {len(new_repos)} GitHub repos remaining")
        
        new_models = filter_new_repos(hf_models, history, days_threshold=7)
        print(f"after filtering duplicates, {len(new_models)} Hugging Face models remaining")
        
        # 7. Fallback to complete lists if too few new items to avoid dry digests
        repos_to_send = new_repos if len(new_repos) >= 3 else trending_repos
        models_to_send = new_models if len(new_models) >= 2 else hf_models
        stories_to_send = hn_stories # HN stories don't repeat, no filter needed
        
        # 8. Summarize with Groq
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
            
    except Exception as e:
        print(f"!!! critical crash in daily trending aggregator: {e}")
        tb_str = traceback.format_exc()
        print(tb_str)
        # Resilient error alert directly to developer telegram chat
        send_error_alert(tb_str)
        # Raise exception to fail the runner process properly
        raise
