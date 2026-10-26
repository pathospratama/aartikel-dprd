"""Analisis sentimen — versi word-boundary (hindari false positive)."""
import re
from config import SENTIMENT_KEYWORDS


def _build_pattern(keyword: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(keyword) + r"\b", re.IGNORECASE)


_POS_PATTERNS = {kw: (w, _build_pattern(kw)) for kw, w in SENTIMENT_KEYWORDS["positif"].items()}
_NEG_PATTERNS = {kw: (w, _build_pattern(kw)) for kw, w in SENTIMENT_KEYWORDS["negatif"].items()}


def analyze_sentiment(article: dict) -> dict:
    text = " ".join(
        str(article.get(k, "") or "")
        for k in ("title", "summary", "content")
    )

    pos_score = 0
    neg_score = 0
    pos_hits = []
    neg_hits = []

    for kw, (w, pat) in _POS_PATTERNS.items():
        if pat.search(text):
            pos_score += w
            pos_hits.append(kw)

    for kw, (w, pat) in _NEG_PATTERNS.items():
        if pat.search(text):
            neg_score += w
            neg_hits.append(kw)

    if pos_score >= 3 and pos_score > neg_score:
        label = "positif"
    elif neg_score >= 3 and neg_score > pos_score:
        label = "negatif"
    else:
        label = "netral"

    return {
        "label": label,
        "positive_score": pos_score,
        "negative_score": neg_score,
        "positive_hits": pos_hits[:10],
        "negative_hits": neg_hits[:10],
    }


def add_sentiment_to_articles(articles: list[dict]) -> list[dict]:
    for a in articles:
        a["sentiment"] = analyze_sentiment(a)
    return articles
