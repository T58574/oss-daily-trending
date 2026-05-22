import re

def is_suspicious(text):
    if not text:
        return False
    text_lower = text.lower()
    suspicious_patterns = [
        r"if you['’]re an llm",
        r"ignore (all )?previous instructions",
        r"please read this",
        r"llms\.txt",
        r"system prompt",
        r"you are a",
        r"buy crypto",
        r"solana",
        r"bitcoin",
        r"refactoring my life",
        r"grow your followers",
        r"get rich",
        r"passive income"
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, text_lower):
            return True
    return False
