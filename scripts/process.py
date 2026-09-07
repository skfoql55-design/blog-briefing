"""
2단계 — 주제 묶기 + 요약

수집된 기사 제목과 RSS/검색 요약문을 LLM에 넘겨
 (1) 같은 사건끼리 묶고
 (2) 블로그 글 주제로 다듬고
 (3) 제공된 근거 안에서 한 줄 근거를 붙이고
 (4) 주제마다 서로 다른 기사 3개를 연결하고
 (5) 이미 쓴 글과 같은 실행에서 고른 다른 주제를 제외한다.

OPENROUTER_API_KEY 가 없거나 LLM 응답이 검증에 실패하면
기사 제목 기반 폴백으로 동작한다. 폴백도 기사 수와 출처 수를 검증한다.
"""
import datetime as dt
import hashlib
import json
import os
import re
from urllib.parse import urlparse

import requests
import yaml

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.getenv("OPENROUTER_MODEL", "z-ai/glm-5.3-flash")
MAX_HEADLINES = 60

STOP = set("""기자 뉴스 종합 속보 단독 오늘 내일 올해 지난 대한 위해 관련 대해 통해 있다 없다
그리고 하지만 이번 지난해 우리 국내 이날 대비 중인 것으로 밝혔다 전했다 나타났다""".split())


def stems(title):
    words = re.findall(r"[가-힣]{2,}|[A-Za-z]{3,}|\d{2,}", str(title or ""))
    return {w[:2] for w in words if w not in STOP}


def article_domain(article):
    value = article.get("domain") or urlparse(article.get("link", "")).netloc
    return value.lower().removeprefix("www.").split(":")[0]


def topic_id(label, topic, articles):
    key = "|".join([
        str(label),
        str(topic),
        *sorted(str(a.get("link", "")) for a in articles),
    ])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def usable_topic(topic, per_topic, min_sources):
    articles = topic.get("articles") or []
    links = [a.get("link") for a in articles if a.get("link")]
    domains = {article_domain(a) for a in articles if article_domain(a)}
    return (
        isinstance(topic.get("topic"), str)
        and bool(topic["topic"].strip())
        and len(articles) == per_topic
        and len(set(links)) == per_topic
        and len(domains) >= min_sources
    )


def default_landing(label, topic, basis, articles):
    facts = []
    for article in articles:
        summary = str(article.get("summary") or article.get("title") or "").strip()
        if summary:
            facts.append(summary[:220])
    cautions = ["기사 3개 원문을 직접 확인한 뒤 날짜·수치·대상을 확정하세요."]
    if "건강" in label:
        cautions += [
            "건강 정보는 공식 기관·의료기관 자료를 우선 확인하세요.",
            "진단·치료 효과를 단정하거나 확인되지 않은 소문을 사실처럼 쓰지 마세요.",
        ]
    return {
        "lead": basis or topic,
        "verification_note": "기사 요약만으로 확정하기 어려운 내용은 원문과 공식 공시를 먼저 확인하세요.",
        "confirmed_facts": facts[:5],
        "reader_steps": [
            "관련 기사 3개의 원문을 차례로 확인합니다.",
            "세 기사에 공통으로 확인되는 사실과 기사별 추가 정보를 나눠 적습니다.",
            "수치·날짜·대상은 공식 발표나 원문에서 다시 확인합니다.",
        ],
        "practical_points": [
            "독자가 바로 확인하거나 실행할 수 있는 항목을 앞부분에 배치합니다.",
            "기사마다 다른 정보가 무엇인지 비교해 설명합니다.",
        ],
        "writing_structure": [
            "뉴스 리드: 지금 이 주제가 나온 이유",
            "핵심 팩트: 세 기사에서 공통으로 확인되는 내용",
            "추가 확인: 기사별로 다른 수치·일정·영향",
            "독자용 체크리스트와 마무리",
        ],
        "headline_options": [topic, f"{topic} 확인 포인트"],
        "keywords": [topic],
        "internal_link_ideas": [],
        "cautions": cautions,
    }


def normalize_landing(label, topic, basis, articles, value):
    """LLM의 부가 필드를 안전한 랜딩페이지용 구조로 정리한다."""
    result = default_landing(label, topic, basis, articles)
    if not isinstance(value, dict):
        return result
    list_fields = {
        "confirmed_facts", "reader_steps", "practical_points", "writing_structure",
        "headline_options", "keywords", "internal_link_ideas", "cautions",
    }
    for field in list_fields:
        items = value.get(field)
        if isinstance(items, list):
            clean = [str(item).strip() for item in items if str(item).strip()]
            if clean:
                result[field] = clean[:8]
    for field in ("lead", "verification_note"):
        if isinstance(value.get(field), str) and value[field].strip():
            result[field] = value[field].strip()
    return result


def make_topic(label, topic, basis, articles, per_topic, min_sources, landing=None):
    topic = str(topic or "").strip()
    basis = str(basis or "").strip()
    picked = []
    seen_links = set()
    for article in articles:
        link = article.get("link")
        if not link or link in seen_links:
            continue
        picked.append(article)
        seen_links.add(link)
        if len(picked) == per_topic:
            break
    if not topic or not usable_topic({"topic": topic, "articles": picked}, per_topic, min_sources):
        return None
    domains = sorted({article_domain(a) for a in picked if article_domain(a)})
    return {
        "topic_id": topic_id(label, topic, picked),
        "topic": topic,
        "basis": basis or f"{len(domains)}개 출처에서 관련 내용 확인",
        "source_domains": domains,
        "landing": normalize_landing(label, topic, basis, picked, landing),
        "articles": picked,
    }


# ── 폴백용 간이 클러스터링 ────────────────────────────────
def naive_cluster(articles, max_topics, per_topic, min_sources=2, label=""):
    pool = [dict(a, _s=stems(a.get("title"))) for a in articles]
    used, groups = set(), []
    for i, seed in enumerate(pool):
        if i in used:
            continue
        group = [seed]
        selected = {i}
        domains = {article_domain(seed)}
        candidates = sorted(
            enumerate(pool),
            key=lambda item: (
                len(seed["_s"] & item[1]["_s"]),
                item[1].get("published") or "",
            ),
            reverse=True,
        )

        # 먼저 다른 출처를 확보하고, 그래도 부족할 때 같은 출처를 보충한다.
        for prefer_new_domain in (True, False):
            for j, other in candidates:
                if j in used or j in selected or len(group) >= per_topic:
                    continue
                if len(seed["_s"] & other["_s"]) < 2:
                    continue
                domain = article_domain(other)
                if prefer_new_domain and domain in domains:
                    continue
                group.append(other)
                selected.add(j)
                domains.add(domain)
            if len(group) >= per_topic:
                break

        clean_group = [{k: v for k, v in a.items() if k != "_s"} for a in group]
        candidate = make_topic(
            label,
            clean_group[0].get("title", ""),
            f"{clean_group[0].get('source', '출처')} 등 {len(clean_group)}개 기사",
            clean_group,
            per_topic,
            min_sources,
        )
        if candidate:
            groups.append(candidate)
            used.update(selected)
        else:
            # 충분한 기사와 출처가 없는 seed만 소비하고 나머지는 다른 주제의 seed로 남긴다.
            used.add(i)

        if len(groups) >= max_topics:
            break
    return groups


# ── LLM 기반 주제 선정 ───────────────────────────────────
PROMPT = """너는 네이버 블로그 정보성 글의 주제를 고르는 편집자다.

아래는 오늘 '{label}' 분야에 올라온 기사 목록이다.
이 분야의 편집 방향은 다음과 같다: {focus}
같은 사건이나 흐름을 다루면서도 서로 다른 정보가 있는 기사 {per}개를 한 묶음으로 만들어,
블로그 글로 쓸 주제 {n}개를 골라라.

각 주제마다:
- "topic": 블로그 글 주제 (20자 내외). 검색해서 들어올 사람이 궁금해할 형태로.
- "basis": 제공된 기사 내용으로만 쓴 한 줄 근거 (40자 내외).
- "ids": 그 주제에 묶이는 기사 번호. 정확히 {per}개.
- "landing": 아래 랜딩페이지용 부가 정보 객체.
  - "lead": 2~3문장 리드. 제공된 자료 밖의 사실은 넣지 않는다.
  - "verification_note": 글 작성 전에 확인할 미확정 정보나 주의점.
  - "confirmed_facts": 기사 요약에서 직접 확인되는 사실 3~5개.
  - "reader_steps": 독자가 따라 할 확인법·체크리스트 3~5개.
  - "practical_points": 독자에게 실익이 있는 포인트 2~4개.
  - "writing_structure": 블로그 글 구성 3~6개.
  - "headline_options": 제목 후보 2~3개.
  - "keywords": 검색 키워드 3~6개.
  - "internal_link_ideas": 연결하면 좋은 글 아이디어 1~3개.
  - "cautions": 단정하면 안 되는 내용이나 확인 주의사항.

기사 묶음 규칙:
- 기사 URL이 서로 달라야 한다.
- 같은 통신사 보도자료를 복사한 기사만 3개 고르지 말고, 서로 다른 출처 도메인 3개를 우선한다.
- 같은 사건을 다루되 발표, 수치, 일정, 영향 등 서로 다른 정보가 있는 기사를 우선한다.
- 기사 요약문에 없는 사실이나 숫자를 만들지 않는다.

지켜야 할 것:
- 수식어를 넣지 말고 사실만 쓴다.
- 번역투를 쓰지 않는다.
- 형용사 대신 숫자를 쓴다.
- 확인되지 않은 건강·연예인 소문을 사실처럼 쓰지 않는다.
- 건강 기사는 진단이나 치료 조언으로 확장하지 않는다.
- 아래 '이미 쓴 글' 및 '이번 실행에서 이미 고른 주제'와 겹치면 고르지 않는다.
- 광고성 기사, 단순 인사·행사 기사는 제외한다.

{past_block}
[오늘 기사]
{headlines}

JSON 배열로만 답하라. 다른 말은 쓰지 마라.
[{{"topic":"...","basis":"...","ids":[0,3,7],"landing":{{"lead":"...","verification_note":"...","confirmed_facts":["..."],"reader_steps":["..."],"practical_points":["..."],"writing_structure":["..."],"headline_options":["..."],"keywords":["..."],"internal_link_ideas":["..."],"cautions":["..."]}}}}]"""


def extract_json_array(text):
    start = str(text or "").find("[")
    if start < 0:
        raise ValueError("JSON 배열이 없습니다")
    value, _ = json.JSONDecoder().raw_decode(str(text)[start:])
    if not isinstance(value, list):
        raise ValueError("JSON 배열이 아닙니다")
    return value


def ask_llm(label, articles, n, per, past_titles, min_sources, focus=""):
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    sample = articles[:MAX_HEADLINES]
    headlines = "\n".join(
        f'{i}. 제목: {a["title"]} | 요약: {a.get("summary", "")[:320]} '
        f'| 출처: {a["source"]} ({a.get("domain", "")}) | {a["published_label"]}'
        for i, a in enumerate(sample)
    )
    past_block = ""
    if past_titles:
        past_block = "[이미 쓴 글·이번 실행에서 이미 고른 주제 — 겹치면 제외]\n" + \
            "\n".join(f"- {t}" for t in past_titles[-120:]) + "\n\n"

    prompt = PROMPT.format(
        label=label,
        focus=focus or "제공된 기사에서 독자에게 가장 유용한 세부 주제를 찾는다.",
        n=n,
        per=per,
        past_block=past_block,
        headlines=headlines,
    )
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=240,
        )
        res.raise_for_status()
        text = res.json()["choices"][0]["message"]["content"]
        items = extract_json_array(text)
    except Exception as exc:
        print(f"  [LLM 실패 → 폴백] {type(exc).__name__}: {exc}")
        return None

    topics = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ids = item.get("ids")
        if not isinstance(ids, list):
            continue
        picked = []
        seen_ids = set()
        for value in ids:
            if isinstance(value, bool) or not isinstance(value, int):
                continue
            if value in seen_ids or not 0 <= value < len(sample):
                continue
            picked.append(sample[value])
            seen_ids.add(value)
            if len(picked) == per:
                break
        candidate = make_topic(
            label,
            item.get("topic"),
            item.get("basis"),
            picked,
            per,
            min_sources,
            landing=item.get("landing"),
        )
        if candidate:
            topics.append(candidate)
        if len(topics) >= n:
            break
    return topics or None


def overlaps_past(topic, past_stems):
    """이미 쓴 글과 핵심 단어가 3개 이상 겹치면 중복으로 본다."""
    articles = topic.get("articles") or []
    first_title = articles[0].get("title", "") if articles else ""
    tok = stems(topic.get("topic", "")) | stems(first_title)
    for title, ps in past_stems:
        if len(tok & ps) >= 3:
            return title
    return None


def drop_duplicates(topics, past_titles, blocked=None, quiet=False):
    """중복 주제를 걸러내고, 걸러진 기사 링크를 blocked 에 모아둔다."""
    if not past_titles:
        return topics
    past_stems = [(t, stems(t)) for t in past_titles]
    kept = []
    for topic in topics:
        hit = overlaps_past(topic, past_stems)
        if hit:
            if not quiet:
                print(f'  [중복 제외] {topic["topic"][:28]}  ← 기존: {hit[:28]}')
            if blocked is not None:
                blocked.update(a.get("link") for a in topic.get("articles", []) if a.get("link"))
            continue
        kept.append(topic)
    return kept


def drop_internal_duplicates(topics):
    """같은 실행 안에서 제목이 겹치거나 같은 기사를 재사용한 주제를 제거한다."""
    kept = []
    seen_titles = []
    used_links = set()
    for topic in topics:
        links = {a.get("link") for a in topic.get("articles", []) if a.get("link")}
        duplicate_title = overlaps_past(topic, [(title, stems(title)) for title in seen_titles])
        duplicate_article = bool(used_links & links)
        if duplicate_title or duplicate_article:
            print(f'  [이번 실행 중복 제외] {topic.get("topic", "")[:28]}')
            continue
        kept.append(topic)
        seen_titles.append(topic.get("topic", ""))
        used_links.update(links)
    return kept


def fill_up(topics, articles, n, per, min_sources, blocked=()):
    """주제가 부족할 때 아직 쓰지 않은 기사에서 검증 가능한 묶음을 보충한다."""
    if len(topics) >= n:
        return topics
    used = {a.get("link") for t in topics for a in t.get("articles", [])} | set(blocked)
    leftover = [a for a in articles if a.get("link") not in used]
    extra = naive_cluster(
        leftover,
        (n - len(topics)) * 2,
        per,
        min_sources,
        label="보충 주제",
    )[: n - len(topics)]
    if extra:
        print(f"  주제가 {len(topics)}개라 남은 기사에서 {len(extra)}개 보충")
    return topics + extra


def build(label, articles, n, per, min_sources, past_titles, excluded_links=(), focus=""):
    excluded = set(excluded_links)
    articles = [a for a in articles if a.get("link") not in excluded]
    if len(articles) < per:
        return []
    blocked = set(excluded)
    topics = ask_llm(label, articles, n, per, past_titles, min_sources, focus)
    if topics is None:
        topics = naive_cluster(articles, n * 3, per, min_sources, label=label)
    topics = [t for t in topics if usable_topic(t, per, min_sources)]
    topics = drop_duplicates(topics, past_titles, blocked)[:n]
    topics = drop_internal_duplicates(topics)
    topics = fill_up(topics, articles, n, per, min_sources, blocked)
    topics = [t for t in topics if usable_topic(t, per, min_sources)]
    topics = drop_duplicates(topics, past_titles, blocked, quiet=True)
    topics = drop_internal_duplicates(topics)
    if len(topics) < n:
        print(f"  ! 주제가 {len(topics)}개뿐입니다 (목표 {n}개). "
              f"기사 {per}개와 출처 {min_sources}개 조건을 만족하는 묶음이 부족합니다.")
    return topics[:n]


def main():
    cfg = yaml.safe_load(open(os.path.join(ROOT, "sources.yaml"), encoding="utf-8"))
    date = dt.datetime.now(KST).strftime("%Y-%m-%d")
    raw = json.load(open(os.path.join(ROOT, "data", f"raw-{date}.json"), encoding="utf-8"))

    past_path = os.path.join(ROOT, cfg.get("past_titles_file", "past_titles.txt"))
    past_titles = []
    if os.path.exists(past_path):
        past_titles = [line.strip() for line in open(past_path, encoding="utf-8") if line.strip()]
    print(f"기존 글 {len(past_titles)}개를 중복 회피 목록으로 넘깁니다.\n")

    global_n = cfg.get("topics_per_category", 5)
    global_per = cfg.get("articles_per_topic", 3)
    global_min_sources = cfg.get("min_unique_sources_per_topic", 3)
    selected_links = set()
    selected_titles = []
    brief = {"date": date, "generated_at": raw["generated_at"], "categories": {}}

    for key, block in raw["categories"].items():
        category_cfg = cfg["categories"].get(key, {})
        n = category_cfg.get("topics_per_category", global_n)
        per = category_cfg.get("articles_per_topic", global_per)
        min_sources = category_cfg.get("min_unique_sources_per_topic", global_min_sources)
        available = [a for a in block["articles"] if a.get("link") not in selected_links]
        print(f"[{block['label']}] 기사 {len(available)}건")
        topics = build(
            block["label"],
            available,
            n,
            per,
            min_sources,
            past_titles + selected_titles,
            selected_links,
            category_cfg.get("focus", ""),
        )
        selected_links.update(a.get("link") for t in topics for a in t["articles"] if a.get("link"))
        selected_titles.extend(t["topic"] for t in topics)
        print(f"  주제 {len(topics)}개")

        out = {
            "label": block["label"],
            "blog": block.get("blog"),
            "category_name": block.get("category_name"),
            "articles_per_topic": per,
            "topics": topics,
        }

        celeb_cfg = category_cfg.get("celeb")
        if celeb_cfg and block.get("celeb_articles"):
            celeb_n = celeb_cfg.get("count", 3)
            celeb_per = celeb_cfg.get("articles_per_topic", per)
            celeb_min_sources = celeb_cfg.get("min_unique_sources_per_topic", min_sources)
            celeb_available = [
                a for a in block["celeb_articles"] if a.get("link") not in selected_links
            ]
            out["celeb_topics"] = build(
                f"{block['label']} — 연예인 건강 이슈",
                celeb_available,
                celeb_n,
                celeb_per,
                celeb_min_sources,
                past_titles + selected_titles,
                selected_links,
                celeb_cfg.get("focus", "연예인의 건강 공개·회복·생활 습관 관련 이슈"),
            )
            selected_links.update(
                a.get("link")
                for t in out["celeb_topics"]
                for a in t["articles"]
                if a.get("link")
            )
            selected_titles.extend(t["topic"] for t in out["celeb_topics"])
            print(f"  연예인 주제 {len(out['celeb_topics'])}개")

        brief["categories"][key] = out
        print()

    path = os.path.join(ROOT, "data", f"brief-{date}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)
    print(f"저장: {path}")


if __name__ == "__main__":
    main()
