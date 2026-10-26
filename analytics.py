"""Statistik agregat dashboard; artikel dideduplikasi berdasarkan URL."""
from collections import Counter
from urllib.parse import urlsplit, urlunsplit


def _canonical_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        parts = urlsplit(value)
        # Abaikan fragment dan query tracking yang tidak mengubah artikel.
        host = parts.netloc.lower().removeprefix("www.")
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), host, path, "", ""))
    except Exception:
        return value


def compute_stats(all_results: list[dict]) -> dict:
    sources, sentiments, dates, keywords = Counter(), Counter(), Counter(), Counter()
    total = official_count = media_count = legislative = non_legislative = 0
    seen_urls: set[str] = set()

    for result in all_results or []:
        source_name = str(result.get("source") or "Tidak diketahui")
        is_official = bool(result.get("is_official"))
        for article in result.get("filtered", []) or []:
            url = _canonical_url(str(article.get("link") or article.get("url") or ""))
            if not url or url in seen_urls:
                continue
            title = str(article.get("title") or article.get("judul") or "").strip()
            if not title:
                continue
            seen_urls.add(url)
            total += 1
            sources[source_name] += 1
            if is_official:
                official_count += 1
                if article.get("is_legislative_work"):
                    legislative += 1
                else:
                    non_legislative += 1
            else:
                media_count += 1

            sentiment = article.get("sentiment") or {}
            label = str(sentiment.get("label") or "netral").lower()
            if label not in {"positif", "negatif", "netral"}:
                label = "netral"
            sentiments[label] += 1

            date_value = str(article.get("date") or "")
            if len(date_value) >= 7 and date_value[4:5] == "-":
                dates[date_value[:7]] += 1

            cats = article.get("category") or []
            if isinstance(cats, str):
                cats = [cats]
            for category in cats:
                category = str(category).strip().lower()
                if category:
                    keywords[category] += 1

    return {
        "total": total,
        "official_count": official_count,
        "media_count": media_count,
        "legislative_work_count": legislative,
        "non_legislative_work_count": non_legislative,
        "sources": dict(sources.most_common()),
        "sentiments": {key: sentiments.get(key, 0) for key in ("positif", "negatif", "netral")},
        "dates": dict(sorted(dates.items())),
        "top_keywords": dict(keywords.most_common(10)),
        "_sentiment_validation_ok": sum(sentiments.values()) == total,
    }
