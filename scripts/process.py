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
import html
import json
import os
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

import requests
import yaml

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.getenv("OPENROUTER_MODEL", "z-ai/glm-5.3-flash")
MAX_HEADLINES = 60
TREND_URL = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
BLOG_URL = "https://naverapihub.apigw.ntruss.com/search/v1/blog"
TITLE_PROMPT_FILE = os.path.join(ROOT, "prompts", "home_title_prompt.txt")
RUNS_DIR = os.path.join(ROOT, "data", "runs")
BLOG_API_AVAILABLE = None

STOP = set("""기자 뉴스 종합 속보 단독 오늘 내일 올해 지난 대한 위해 관련 대해 통해 있다 없다
그리고 하지만 이번 지난해 우리 국내 이날 대비 중인 것으로 밝혔다 전했다 나타났다""".split())


def load_title_prompt():
    """사용자가 교체할 수 있는 홈판 제목 생성 프롬프트를 읽는다."""
    if os.path.exists(TITLE_PROMPT_FILE):
        try:
            text = open(TITLE_PROMPT_FILE, encoding="utf-8").read().strip()
            if text:
                return text
        except OSError:
            pass
    return (
        "사실을 과장하거나 확인되지 않은 숫자를 만들지 말고, 검색자가 궁금해할 질문형·혜택형·"
        "확인형 제목을 섞어 정확히 30개 만든다. 제목끼리 표현과 각도를 반복하지 않는다. "
        "홈판용이므로 짧고 자연스러운 한국어로 쓴다."
    )


def fallback_headlines(topic, label=""):
    """LLM을 사용할 수 없을 때도 30개 제목 후보를 제공한다."""
    templates = [
        f"{topic}, 지금 확인해야 할 핵심 3가지",
        f"{topic} 한눈에 정리… 놓치기 쉬운 포인트는",
        f"{topic} 관련 소식, 달라지는 점을 쉽게 정리했습니다",
        f"{topic} 사실과 오해를 구분해 봤습니다",
        f"{topic} 기사 3개를 비교해 보니 공통점은",
        f"{topic} 발표 내용, 내 생활에 미치는 영향은",
        f"{topic} 대상이라면 먼저 확인할 내용",
        f"{topic} 오늘 나온 소식에서 꼭 봐야 할 부분",
        f"{topic} 언제부터 적용될까? 일정과 대상 정리",
        f"{topic} 핵심 내용만 1분 만에 확인하기",
        f"{topic} 숫자로 정리한 변화와 영향",
        f"{topic} 지금 검색하는 사람이 많은 이유",
        f"{topic} 직접 확인하는 방법과 주의점",
        f"{topic} 내 경우에도 해당되는지 확인해 보세요",
        f"{topic} 전문가들이 공통으로 짚은 내용",
        f"{topic} 달라지는 기준과 확인할 서류",
        f"{topic} 실제로 도움이 되는 체크리스트",
        f"{topic} 잘못 알려진 정보는 무엇일까",
        f"{topic} 오늘의 이슈를 독자 관점에서 정리",
        f"{topic} 기사마다 달랐던 내용까지 비교했습니다",
        f"{topic} 알아두면 손해를 줄일 수 있는 정보",
        f"{topic} 시작 전에 확인할 5가지",
        f"{topic} 지금 알아야 할 변화와 다음 일정",
        f"{topic} 초보자도 이해하기 쉽게 정리",
        f"{topic} 중요한 내용만 골라서 확인하세요",
        f"{topic} 관련 공식 발표와 보도 내용 비교",
        f"{topic} 궁금했던 내용을 질문과 답으로 정리",
        f"{topic} 실제 적용 전 꼭 확인할 조건",
        f"{topic} 검색 전 알아두면 좋은 핵심 용어",
        f"{topic} 오늘의 브리핑: 사실·영향·확인법",
    ]
    seen = set()
    return [item for item in templates if not (item in seen or seen.add(item))][:30]


def fallback_top_n_judgment(label):
    """뉴스·정책·리콜처럼 순위보다 확인 절차가 중요한 주제의 기본 판단."""
    lowered = str(label or "")
    if any(word in lowered for word in ("정책", "리콜", "최신 이슈", "방송연예", "스포츠")):
        return {
            "result": "부분 적합(소제목용)",
            "recommended_number": None,
            "type": "뉴스·변경형",
            "reason": "확정된 대상·일정·영향을 먼저 확인하는 주제라 TOP N은 본문 소제목에 더 적합합니다.",
        }
    return {
        "result": "부분 적합(소제목용)",
        "recommended_number": None,
        "type": "독자 실익형",
        "reason": "기사 원문과 공식 자료를 확인한 뒤 여러 항목으로 나눌 수 있을 때 TOP N을 사용합니다.",
    }


def fallback_headline_metadata(headlines, label=""):
    news_labels = ("정책", "리콜", "최신 이슈", "방송연예", "스포츠", "뉴스")
    frame = "뉴스·변경형" if any(word in str(label or "") for word in news_labels) else "실행형"
    return [
        {
            "title": title,
            "frame": frame,
            "source_article_ids": [],
            "evidence_status": "원문 확인 필요",
        }
        for title in headlines[:30]
    ]


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
    headlines = fallback_headlines(topic, label)
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
        "top_n_judgment": fallback_top_n_judgment(label),
        "headline_options": headlines,
        "headline_metadata": fallback_headline_metadata(headlines, label),
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
        "keywords", "internal_link_ideas", "cautions",
    }
    for field in list_fields:
        items = value.get(field)
        if isinstance(items, list):
            clean = [str(item).strip() for item in items if str(item).strip()]
            if clean:
                result[field] = clean[:8]
    raw_headlines = value.get("headline_options")
    if isinstance(raw_headlines, list):
        headlines = []
        metadata = []
        for item in raw_headlines:
            if isinstance(item, dict):
                title = str(item.get("title") or item.get("headline") or "").strip()
                frame = str(item.get("frame") or "").strip()
                refs = item.get("source_article_ids") or item.get("article_ids") or []
                refs = [int(ref) for ref in refs if isinstance(ref, int) and not isinstance(ref, bool)]
                evidence = str(item.get("evidence_status") or "원문 확인 필요").strip()
            else:
                title = str(item or "").strip()
                frame, refs, evidence = "", [], "원문 확인 필요"
            if title and title not in headlines:
                headlines.append(title)
                metadata.append({
                    "title": title,
                    "frame": frame or "정보형",
                    "source_article_ids": refs[:3],
                    "evidence_status": evidence,
                })
            if len(headlines) >= 30:
                break
        if headlines:
            result["headline_options"] = headlines
            result["headline_metadata"] = metadata
    if isinstance(value.get("headline_metadata"), list):
        for item in value["headline_metadata"]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            for meta in result.get("headline_metadata", []):
                if meta.get("title") == title:
                    meta["frame"] = str(item.get("frame") or meta.get("frame") or "정보형").strip()
                    meta["evidence_status"] = str(
                        item.get("evidence_status") or meta.get("evidence_status") or "원문 확인 필요"
                    ).strip()
                    break
    judgment = value.get("top_n_judgment")
    if isinstance(judgment, dict):
        recommended = judgment.get("recommended_number")
        if isinstance(recommended, str) and recommended.strip().isdigit():
            recommended = int(recommended.strip())
        result["top_n_judgment"] = {
            "result": str(judgment.get("result") or "부분 적합(소제목용)").strip(),
            "recommended_number": recommended if recommended in (3, 5) else None,
            "type": str(judgment.get("type") or "정보형").strip(),
            "reason": str(judgment.get("reason") or "원문 확인 후 TOP N 적용 여부를 판단하세요.").strip(),
        }
    if len(result.get("headline_options", [])) < 30:
        existing = result.get("headline_options", [])
        existing_meta = result.setdefault("headline_metadata", [])
        for item in fallback_headlines(topic, label):
            if item not in existing:
                existing.append(item)
                existing_meta.append({
                    "title": item,
                    "frame": "뉴스·변경형" if any(
                        word in str(label or "")
                        for word in ("정책", "리콜", "최신 이슈", "방송연예", "스포츠", "뉴스")
                    ) else "실행형",
                    "source_article_ids": [],
                    "evidence_status": "원문 확인 필요",
                })
            if len(existing) >= 30:
                break
        result["headline_options"] = existing[:30]
        result["headline_metadata"] = existing_meta[:30]
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
이 분야에서 검색어트렌드로 확인된 관심 키워드는 다음과 같다: {trend_context}
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
  - "top_n_judgment": TOP N 적합성 판단 객체. "result"는 "적합", "부분 적합(소제목용)", "부적합" 중 하나.
    "recommended_number"는 3, 5, 또는 null. "type"은 TOP N 유형이나 "뉴스·변경형".
    기사에 실제로 확인되는 항목이 충분하지 않으면 부적합 또는 부분 적합으로 판단한다.
  - "headline_options": 홈판 제목 후보 정확히 30개. 각 항목은
    {{"title":"...","frame":"이득형|위협형|궁금형|비교형|반전형|실행형|뉴스·변경형",
    "source_article_ids":[0,2],"evidence_status":"확정 팩트 기반|원문 확인 필요"}} 형식.
    후보마다 검색 의도와 각도를 다르게 한다.
  - "keywords": 검색 키워드 3~6개.
  - "internal_link_ideas": 연결하면 좋은 글 아이디어 1~3개.
  - "cautions": 단정하면 안 되는 내용이나 확인 주의사항.

기사 묶음 규칙:
- 기사 URL이 서로 달라야 한다.
- 같은 사건·정책·발표를 다룬 기사 {per}개는 하나의 글감과 하나의 블로그 주제 근거로 유지한다. 기사별로 쪼개지 않는다.
- 같은 통신사 보도자료를 복사한 기사만 3개 고르지 말고, 서로 다른 출처 도메인 3개를 우선한다.
- 같은 사건을 다루되 발표, 수치, 일정, 영향 등 서로 다른 정보가 있는 기사를 우선한다.
- 기사 요약문에 없는 사실이나 숫자를 만들지 않는다.

지켜야 할 것:
- 수식어를 넣지 말고 사실만 쓴다.
- 번역투를 쓰지 않는다.
- 형용사 대신 숫자를 쓴다.
- 확인되지 않은 건강·연예인 소문을 사실처럼 쓰지 않는다.
- 건강 기사는 진단이나 치료 조언으로 확장하지 않는다.
- 건강 제목은 질병을 진단하는 것처럼 단정하지 말고 "겹칠 수 있는 신호", "확인할 증상"처럼 쓴다.
- 경제·정책·리콜 제목은 대상·시행일·조건이 확인되지 않으면 숫자와 범위를 제목에 넣지 않는다.
- "이 번호", "이 돈", "이것"처럼 가린 표현은 브리프 안에 실제 답이 있을 때만 사용한다.
- 숫자만으로 대조 항목이 부족하면 TOP N을 쓰지 않는다.
- 뉴스·정책·리콜은 필요하면 TOP N 대신 뉴스·변경형 제목을 우선한다.
- RSS 제목·검색 결과 요약만 근거로 삼은 제목은 `원문 확인 필요`로 표시하고, 원문이나 공식 자료를 실제로 받은 경우에만 `확정 팩트 기반`으로 표시한다.
- `source_article_ids`는 입력 기사 배열의 0부터 시작하는 번호를 사용한다.
- 아래 '이미 쓴 글' 및 '이번 실행에서 이미 고른 주제'와 겹치면 고르지 않는다.
- 광고성 기사, 단순 인사·행사 기사는 제외한다.

[홈판 제목 생성 지침]
{title_prompt}

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


def ask_llm(label, articles, n, per, past_titles, min_sources, focus="", trend_context=""):
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
        trend_context=trend_context or "검색어트렌드 미연결. 검색 키워드를 과장해 추정하지 않는다.",
        title_prompt=load_title_prompt(),
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


def topic_keywords(topic):
    """검색어트렌드와 블로그 검색에 사용할 주제별 검색어를 정리한다."""
    values = [topic.get("topic", "")]
    values.extend((topic.get("landing") or {}).get("keywords", []))
    out = []
    for value in values:
        value = re.sub(r"\s+", " ", str(value or "")).strip()
        if value and value not in out:
            out.append(value)
    return out[:20]


def fetch_trend_scores(topics):
    """NAVER DataLab 상대 검색지수를 주제별로 가져온다.

    Search Trend API는 한 번에 주제어 5개까지 비교할 수 있어 카테고리 단위로 호출한다.
    API를 신청하지 않았거나 호출에 실패하면 빈 결과를 반환해 휴리스틱으로 대체한다.
    """
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not (cid and secret) or not topics:
        return {}
    groups = []
    for topic in topics[:5]:
        key = str(topic.get("topic_id") or topic.get("topic", ""))[:40]
        keywords = topic_keywords(topic)
        if not keywords:
            continue
        groups.append({"groupName": key, "keywords": keywords})
    if not groups:
        return {}
    today = dt.datetime.now(KST).date()
    body = {
        "startDate": (today - dt.timedelta(days=30)).isoformat(),
        "endDate": today.isoformat(),
        "timeUnit": "date",
        "keywordGroups": groups,
    }
    try:
        res = requests.post(
            TREND_URL,
            headers={
                "X-NCP-APIGW-API-KEY-ID": cid,
                "X-NCP-APIGW-API-KEY": secret,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=20,
        )
        res.raise_for_status()
        scores = {}
        for result in res.json().get("results", []):
            data = result.get("data") or []
            ratios = [float(item.get("ratio", 0)) for item in data[-7:] if item.get("ratio") is not None]
            if ratios:
                scores[result.get("title", "")] = round(sum(ratios) / len(ratios), 1)
        if scores:
            print(f"  네이버 검색어트렌드 비교 완료 - {len(scores)}개 주제")
        return scores
    except Exception as exc:
        print(f"  [검색어트렌드 생략] {type(exc).__name__}: {exc}")
        return {}


def fetch_keyword_trend_context(queries):
    """카테고리의 기본 검색어 관심도를 제목 생성 전에 조회한다."""
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    clean_queries = []
    for query in queries or []:
        query = re.sub(r"\s+", " ", str(query or "")).strip()
        if query and query not in clean_queries:
            clean_queries.append(query)
    if not (cid and secret) or not clean_queries:
        return []
    groups = [
        {"groupName": query[:40], "keywords": [query]}
        for query in clean_queries[:5]
    ]
    today = dt.datetime.now(KST).date()
    try:
        res = requests.post(
            TREND_URL,
            headers={
                "X-NCP-APIGW-API-KEY-ID": cid,
                "X-NCP-APIGW-API-KEY": secret,
                "Content-Type": "application/json",
            },
            json={
                "startDate": (today - dt.timedelta(days=30)).isoformat(),
                "endDate": today.isoformat(),
                "timeUnit": "date",
                "keywordGroups": groups,
            },
            timeout=20,
        )
        res.raise_for_status()
        values = []
        for result in res.json().get("results", []):
            ratios = [float(item.get("ratio", 0)) for item in (result.get("data") or [])[-7:]]
            if ratios:
                values.append({
                    "keyword": result.get("title", ""),
                    "score": round(sum(ratios) / len(ratios), 1),
                })
        return sorted(values, key=lambda item: item["score"], reverse=True)
    except Exception as exc:
        print(f"  [카테고리 검색어트렌드 생략] {type(exc).__name__}: {exc}")
        return []


def format_trend_context(values):
    if not values:
        return "검색어트렌드 자료 없음"
    return ", ".join(f'{item["keyword"]}({item["score"]})' for item in values)


def fallback_interest_score(topic):
    """검색어트렌드가 없을 때 기사 최신성·출처 확산으로 관심도를 추정한다."""
    now = dt.datetime.now(KST)
    recencies = []
    for article in topic.get("articles", []):
        try:
            published = dt.datetime.fromisoformat(str(article.get("published")))
            if published.tzinfo is None:
                published = published.replace(tzinfo=KST)
            hours = max(0.0, (now - published.astimezone(KST)).total_seconds() / 3600)
            recencies.append(max(0.0, 1.0 - min(hours, 72.0) / 72.0))
        except Exception:
            pass
    recency = (sum(recencies) / len(recencies) if recencies else 0.35) * 50
    sources = len(topic.get("source_domains") or {article_domain(a) for a in topic.get("articles", [])})
    source_score = min(sources, 3) / 3 * 25
    keyword_score = min(len(topic_keywords(topic)), 6) / 6 * 15
    title_score = min(len(stems(topic.get("topic", ""))), 6) / 6 * 10
    return int(round(recency + source_score + keyword_score + title_score))


def rank_topics(topics):
    """주제를 관심도 높은 순서로 정렬하고 순위·근거를 저장한다."""
    trend_scores = fetch_trend_scores(topics)
    for topic in topics:
        key = str(topic.get("topic_id") or topic.get("topic", ""))[:40]
        if key in trend_scores:
            score = trend_scores[key]
            method = "NAVER 검색어트렌드 상대지수"
        else:
            score = fallback_interest_score(topic)
            method = "기사 최신성·출처 확산 추정"
        topic["interest"] = {
            "score": score,
            "method": method,
            "keywords": topic_keywords(topic),
        }
    topics.sort(key=lambda item: (-item.get("interest", {}).get("score", 0), item.get("topic", "")))
    for index, topic in enumerate(topics, 1):
        topic.setdefault("interest", {})["rank"] = index
    return topics


def normalized_title(value):
    value = html.unescape(re.sub(r"<[^>]+>", "", str(value or ""))).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", value)


def title_similarity(left, right):
    """블로그 제목 간 단어 형태가 흔들려도 비교할 수 있는 문자 n-gram 유사도."""
    left = normalized_title(left)
    right = normalized_title(right)
    if not left or not right:
        return 0.0
    if left == right:
        return 100.0
    grams_left = {left[index:index + 2] for index in range(max(1, len(left) - 1))}
    grams_right = {right[index:index + 2] for index in range(max(1, len(right) - 1))}
    union = grams_left | grams_right
    jaccard = len(grams_left & grams_right) / len(union) if union else 0
    sequence = SequenceMatcher(None, left, right).ratio()
    return round((jaccard * 0.7 + sequence * 0.3) * 100, 1)


def fetch_blog_similarity(topic):
    """주제당 네이버 블로그 검색 1회로 추천 제목 30개의 유사도를 추정한다."""
    global BLOG_API_AVAILABLE
    headlines = ((topic.get("landing") or {}).get("headline_options") or [])[:30]
    query = str(topic.get("topic", "")).strip()
    if not headlines:
        headlines = fallback_headlines(query)
    if not query:
        return {"status": "unavailable", "note": "검색할 주제가 없습니다.", "candidates": []}
    cid, secret = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not (cid and secret) or BLOG_API_AVAILABLE is False:
        return {
            "status": "unavailable",
            "query": query,
            "note": "NAVER API HUB의 블로그 검색 서비스를 신청하면 자동 비교됩니다.",
            "candidates": [],
        }
    try:
        res = requests.get(
            BLOG_URL,
            params={"query": query, "display": 100, "sort": "sim", "format": "json"},
            headers={
                "X-NCP-APIGW-API-KEY-ID": cid,
                "X-NCP-APIGW-API-KEY": secret,
            },
            timeout=20,
        )
        if res.status_code in {400, 401, 403, 404}:
            BLOG_API_AVAILABLE = False
        res.raise_for_status()
        BLOG_API_AVAILABLE = True
        items = res.json().get("items", [])
        candidates = []
        for headline in headlines:
            best = {"score": 0.0, "title": "", "link": ""}
            for item in items:
                score = title_similarity(headline, item.get("title", ""))
                if score > best["score"]:
                    best = {
                        "score": score,
                        "title": html.unescape(re.sub(r"<[^>]+>", "", str(item.get("title", "")))),
                        "link": item.get("link", ""),
                    }
            candidates.append({"title": headline, "score": best["score"], "match": best})
        return {
            "status": "ok",
            "query": query,
            "checked_count": len(items),
            "note": "네이버 블로그 검색 상위 결과 제목과 비교한 추정치입니다. 높을수록 유사한 제목이 있다는 뜻입니다.",
            "candidates": candidates,
        }
    except Exception as exc:
        print(f"  [블로그 제목 유사도 생략] {type(exc).__name__}: {exc}")
        return {
            "status": "error",
            "query": query,
            "note": "네이버 블로그 검색을 완료하지 못했습니다. 검색 API 권한과 키를 확인하세요.",
            "candidates": [],
        }


def enrich_blog_similarity(topics):
    for index, topic in enumerate(topics, 1):
        topic["naver_blog_similarity"] = fetch_blog_similarity(topic)
        if topic["naver_blog_similarity"].get("status") == "ok":
            print(f"  블로그 제목 유사도 확인 {index}/{len(topics)}")
    return topics


def build(label, articles, n, per, min_sources, past_titles, excluded_links=(), focus="", trend_context=""):
    excluded = set(excluded_links)
    articles = [a for a in articles if a.get("link") not in excluded]
    if len(articles) < per:
        return []
    blocked = set(excluded)
    topics = ask_llm(label, articles, n, per, past_titles, min_sources, focus, trend_context)
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
        trend_values = fetch_keyword_trend_context(category_cfg.get("naver_queries", []))
        trend_context = format_trend_context(trend_values)
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
            trend_context,
        )
        topics = enrich_blog_similarity(rank_topics(topics))
        selected_links.update(a.get("link") for t in topics for a in t["articles"] if a.get("link"))
        selected_titles.extend(t["topic"] for t in topics)
        print(f"  주제 {len(topics)}개")

        out = {
            "label": block["label"],
            "blog": block.get("blog"),
            "category_name": block.get("category_name"),
            "trend_summary": trend_values,
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
                trend_context,
            )
            out["celeb_topics"] = enrich_blog_similarity(rank_topics(out["celeb_topics"]))
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
    run_id = dt.datetime.now(KST).strftime("%Y-%m-%d-%H%M%S")
    brief["run_id"] = run_id
    with open(path, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)
    print(f"저장: {path}")

    # 같은 날짜에 다시 실행해도 이전 결과가 사라지지 않도록 실행별 스냅샷을 보관한다.
    os.makedirs(RUNS_DIR, exist_ok=True)
    run_path = os.path.join(RUNS_DIR, f"brief-{run_id}.json")
    with open(run_path, "w", encoding="utf-8") as f:
        json.dump(brief, f, ensure_ascii=False, indent=2)
    print(f"실행 기록 저장: {run_path}")


if __name__ == "__main__":
    main()
