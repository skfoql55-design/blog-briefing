"""
1단계 — 자료 수집
RSS 피드 + NAVER API HUB 뉴스 검색 API 에서 최근 기사를 모아
data/raw-YYYY-MM-DD.json 으로 저장.
LLM 을 전혀 쓰지 않으므로 토큰 비용 0.
"""
import os, re, json, html, csv, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urljoin, urlparse

import yaml, requests, feedparser

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (compatible; blog-briefing/1.0)"
CREATOR_ADVISOR_PATH = os.path.join(ROOT, "data", "creator_advisor_keywords.csv")


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def to_kst(entry):
    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            value = parsedate_to_datetime(raw)
            if value.tzinfo is None:
                value = value.replace(tzinfo=dt.timezone.utc)
            return value.astimezone(KST)
        except Exception:
            pass
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return dt.datetime(*parsed[:6], tzinfo=dt.timezone.utc).astimezone(KST)
    return None


def source_domain(link):
    """기사 링크에서 비교용 출처 도메인을 뽑는다."""
    try:
        host = urlparse(link).netloc.lower().split("@")[-1].split(":")[0]
        return host.removeprefix("www.")
    except Exception:
        return ""


def usable_link(link):
    """정적 사이트에서 안전하게 열 수 있는 HTTP(S) 링크만 허용한다."""
    try:
        parsed = urlparse(link)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def fetch_rss(url, cutoff):
    """피드 하나를 읽어 기사 리스트를 반환. 실패해도 예외를 던지지 않는다."""
    out = []
    try:
        res = requests.get(url, timeout=15, headers={"User-Agent": UA})
        res.raise_for_status()
        feed = feedparser.parse(res.content)
        source = clean(feed.feed.get("title", "")) or url.split("/")[2]
        for e in feed.entries:
            published = to_kst(e)
            if not published or published < cutoff:
                continue
            title = clean(e.get("title"))
            link = urljoin(url, e.get("link") or "")
            if not title or not usable_link(link):
                continue
            out.append({
                "title": title,
                "link": link,
                "summary": clean(e.get("summary"))[:400],
                "published": published.isoformat() if published else None,
                "published_label": published.strftime("%m/%d %H:%M") if published else "시각 미상",
                "source": source,
                "domain": source_domain(link),
                "origin": "rss",
            })
    except Exception as exc:
        print(f"  [skip] {url} — {type(exc).__name__}: {exc}")
    return out


def fetch_naver(query, cutoff, display=30):
    """NAVER API HUB 뉴스 검색. 키가 없으면 조용히 건너뛴다."""
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not (cid and secret):
        return []
    out = []
    try:
        res = requests.get(
            "https://naverapihub.apigw.ntruss.com/search/v1/news",
            params={"query": query, "display": display, "sort": "date", "format": "json"},
            headers={"X-NCP-APIGW-API-KEY-ID": cid,
                     "X-NCP-APIGW-API-KEY": secret, "User-Agent": UA},
            timeout=15,
        )
        res.raise_for_status()
        for item in res.json().get("items", []):
            try:
                published = parsedate_to_datetime(item["pubDate"]).astimezone(KST)
            except Exception:
                published = None
            if not published or published < cutoff:
                continue
            link = item.get("originallink") or item.get("link")
            if not usable_link(link):
                continue
            out.append({
                "title": clean(item["title"]),
                "link": link,
                "summary": clean(item.get("description"))[:400],
                "published": published.isoformat() if published else None,
                "published_label": published.strftime("%m/%d %H:%M") if published else "시각 미상",
                "source": "네이버뉴스",
                "domain": source_domain(link),
                "origin": f"naver:{query}",
            })
    except Exception as exc:
        print(f"  [skip] naver '{query}' — {type(exc).__name__}: {exc}")
    return out


def dedupe(articles):
    seen_links, seen_titles, out = set(), set(), []
    for a in articles:
        link_key = a["link"].split("#", 1)[0].rstrip("/")
        title_key = re.sub(r"[^가-힣a-zA-Z0-9]", "", a["title"]).lower()[:80]
        if link_key in seen_links or title_key in seen_titles:
            continue
        seen_links.add(link_key)
        seen_titles.add(title_key)
        out.append(a)
    return out


def load_creator_advisor_keywords(path, categories):
    """크리에이터 어드바이저에서 옮겨 적은 검색어를 카테고리별로 읽는다."""
    result = {key: [] for key in categories}
    if not os.path.exists(path):
        return result
    labels = {
        key: {key, str(value.get("label") or "").strip()}
        for key, value in categories.items()
    }
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                keyword = str(
                    row.get("키워드") or row.get("keyword") or ""
                ).strip()
                target = str(
                    row.get("카테고리키") or row.get("category_key") or
                    row.get("카테고리") or row.get("category") or ""
                ).strip()
                if not keyword or not target:
                    continue
                for key, candidates in labels.items():
                    if target in candidates or target == str(categories[key].get("category_name") or ""):
                        if keyword not in result[key]:
                            result[key].append(keyword)
                        break
    except (OSError, csv.Error):
        pass
    return result


def main():
    cfg = yaml.safe_load(open(os.path.join(ROOT, "sources.yaml"), encoding="utf-8"))
    now = dt.datetime.now(KST)
    result = {"generated_at": now.isoformat(), "date": now.strftime("%Y-%m-%d"), "categories": {}}
    advisor_keywords = load_creator_advisor_keywords(
        CREATOR_ADVISOR_PATH, cfg.get("categories", {})
    )
    advisor_count = sum(len(values) for values in advisor_keywords.values())
    if advisor_count:
        print(f"크리에이터 어드바이저 검색어 {advisor_count}개를 추가합니다.")

    for key, cat in cfg["categories"].items():
        freshness_hours = cat.get("freshness_hours", cfg.get("freshness_hours", 30))
        cutoff = now - dt.timedelta(hours=freshness_hours)
        print(f"[{cat['label']}] 수집 시작")
        jobs = []
        queries = list(cat.get("naver_queries", []))
        for query in advisor_keywords.get(key, []):
            if query not in queries:
                queries.append(query)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for url in cat.get("rss", []):
                jobs.append(pool.submit(fetch_rss, url, cutoff))
            for q in queries:
                jobs.append(pool.submit(fetch_naver, q, cutoff))
        articles = dedupe([a for j in jobs for a in j.result()])
        articles.sort(key=lambda a: a["published"] or "", reverse=True)

        block = {"label": cat["label"], "blog": cat.get("blog"),
                 "category_name": cat.get("category_name"), "articles": articles,
                 "creator_advisor_keywords": advisor_keywords.get(key, [])}

        celeb_cfg = cat.get("celeb")
        if celeb_cfg:
            with ThreadPoolExecutor(max_workers=6) as pool:
                cjobs = [pool.submit(fetch_naver, q, cutoff, 20)
                         for q in celeb_cfg.get("naver_queries", [])]
            celeb = dedupe([a for j in cjobs for a in j.result()])
            celeb.sort(key=lambda a: a["published"] or "", reverse=True)
            block["celeb_articles"] = celeb
            print(f"  연예인 건강 기사 {len(celeb)}건")

        print(f"  기사 {len(articles)}건")
        result["categories"][key] = block

    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    path = os.path.join(ROOT, "data", f"raw-{result['date']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {path}")


if __name__ == "__main__":
    main()
