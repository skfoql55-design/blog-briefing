"""
3단계 — 브리핑 사이트 생성
data/brief-*.json 을 읽어 docs/ 아래 날짜별 정적 HTML과 작성 관리 화면을 만든다.
"""
import csv
import datetime as dt
import glob
import hashlib
import json
import os
import re
from urllib.parse import urlparse

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
TOPICS_DIR = os.path.join(DOCS, "topics")
WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"]
ACCENT = {
    "economy_kr_stock": "#1d6f5c",
    "economy_us_stock": "#256d8a",
    "economy_finance": "#3f7d5a",
    "economy_policy": "#7a5b2b",
    "health_current": "#a33a5b",
    "health_info": "#c06a3a",
    "cartech_auto": "#2f5b9c",
    "cartech_it": "#5a55a5",
    "broadcast": "#8a4f9d",
    "sports": "#b36b00",
}

CSS = """
*{box-sizing:border-box}
:root{
  --bg:#f7f6f3; --card:#fff; --ink:#1a1a1a; --muted:#6b6b6b;
  --line:#e3e0da; --chip:#efece6;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#16171a; --card:#1e2024; --ink:#eceae6; --muted:#9a9a9a;
    --line:#2e3238; --chip:#282b30;
  }
}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",
  "Noto Sans KR",sans-serif;line-height:1.6;-webkit-text-size-adjust:100%}
.wrap{max-width:900px;margin:0 auto;padding:24px 18px 64px}
header.top{padding:14px 0 22px;border-bottom:1px solid var(--line);margin-bottom:26px}
h1{font-size:1.45rem;margin:0 0 4px;letter-spacing:-.02em}
.date{color:var(--muted);font-size:.88rem}
.nav{margin-top:14px;display:flex;gap:8px;flex-wrap:wrap}
.nav a{font-size:.8rem;text-decoration:none;color:var(--muted);
  background:var(--chip);padding:5px 11px;border-radius:99px}
.nav a:hover{color:var(--ink)}
section.cat{margin-bottom:38px}
.cathead{display:flex;align-items:baseline;gap:10px;margin-bottom:4px}
.cathead h2{font-size:1.12rem;margin:0;letter-spacing:-.01em}
.dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
.catmeta{color:var(--muted);font-size:.78rem;margin:0 0 16px 19px}
.topic{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:15px 17px;margin-bottom:11px}
.topic.completed{border-color:#76a987;background:linear-gradient(90deg,var(--card),rgba(118,169,135,.08))}
.topic.completed .ttitle{color:var(--muted)}
.tnum{font-size:.72rem;color:var(--muted);font-variant-numeric:tabular-nums}
.ttitle{font-size:1rem;font-weight:600;margin:3px 0 6px;letter-spacing:-.01em}
.tbasis{font-size:.87rem;color:var(--muted);margin:0 0 11px}
.topic-tools{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:2px 0 7px}
.complete-toggle{display:inline-flex;align-items:center;gap:6px;color:var(--muted);font-size:.78rem;cursor:pointer;user-select:none}
.complete-toggle input{width:16px;height:16px;accent-color:#3b8f5b;cursor:pointer}
.complete-note{color:var(--muted);font-size:.72rem}
.checkbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;
  background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 13px;margin:0 0 18px;font-size:.8rem;color:var(--muted)}
.checkbar strong{color:var(--ink)}
.checkbar button{border:1px solid var(--line);background:var(--chip);color:var(--muted);border-radius:7px;padding:5px 9px;cursor:pointer}
.checkbar button:hover{color:var(--ink)}
.arts{list-style:none;margin:0;padding:11px 0 0;border-top:1px dashed var(--line)}
.arts li{margin-bottom:7px;font-size:.83rem;line-height:1.5}
.arts li:last-child{margin-bottom:0}
.arts a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}
.arts a:hover{border-color:var(--muted)}
.amet{color:var(--muted);font-size:.76rem;white-space:nowrap}
.celeb{border-style:dashed}
.celebhead{font-size:.83rem;color:var(--muted);margin:22px 0 10px;
  padding-top:16px;border-top:1px solid var(--line)}
.empty{color:var(--muted);font-size:.88rem;background:var(--card);
  border:1px dashed var(--line);border-radius:12px;padding:16px}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);
  color:var(--muted);font-size:.78rem}
footer a{color:var(--muted)}
.arch{list-style:none;padding:0;margin:0}
.arch li{padding:11px 0;border-bottom:1px solid var(--line)}
.arch a{color:var(--ink);text-decoration:none;font-size:.95rem}
.tracker{width:100%;border-collapse:collapse;font-size:.78rem;background:var(--card)}
.tracker th,.tracker td{padding:8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.tracker th{color:var(--muted);font-weight:600;white-space:nowrap}
.tracker a{color:var(--ink)}
.status{white-space:nowrap;font-weight:600}
.detail-link{display:inline-block;margin:2px 0 10px;color:var(--muted);font-size:.78rem;text-decoration:none}
.detail-link:hover{color:var(--ink)}
.hero{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;margin-bottom:18px}
.hero h2{margin:0 0 8px;font-size:1.35rem;letter-spacing:-.02em}
.hero p{margin:0;color:var(--muted)}
.warning{background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;border-radius:10px;padding:13px 15px;margin:16px 0}
@media (prefers-color-scheme:dark){.warning{background:#2c2117;border-color:#7c4a20;color:#fdba74}}
.detail-section{margin:24px 0}
.detail-section h3{font-size:1rem;margin:0 0 9px}
.detail-section ul,.detail-section ol{margin:0;padding-left:22px}
.detail-section li{margin:6px 0}
.chips{display:flex;flex-wrap:wrap;gap:7px}
.chip{display:inline-block;background:var(--chip);border-radius:99px;padding:4px 10px;color:var(--muted);font-size:.78rem}
.sources{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
.source-card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.source-card a{color:var(--ink);font-weight:600;text-decoration:none}
.source-card p{font-size:.82rem;color:var(--muted);margin:6px 0 0}
.back{margin-bottom:16px;font-size:.82rem}
.back a{color:var(--muted);text-decoration:none}
"""

CHECK_SCRIPT = """<script>
(() => {
  const storageKey = 'blogBriefingCompletedTopics';
  const read = () => {
    try { return JSON.parse(localStorage.getItem(storageKey) || '{}'); }
    catch (_) { return {}; }
  };
  const write = (value) => {
    try { localStorage.setItem(storageKey, JSON.stringify(value)); }
    catch (_) {}
  };
  const refresh = () => {
    const saved = read();
    let done = 0;
    document.querySelectorAll('.topic-check').forEach((input) => {
      const checked = Boolean(saved[input.dataset.topicId]);
      input.checked = checked;
      const card = input.closest('.topic');
      if (card) card.classList.toggle('completed', checked);
      if (checked) done += 1;
    });
    document.querySelectorAll('[data-check-summary]').forEach((el) => {
      el.textContent = `완료 ${done} / 전체 ${document.querySelectorAll('.topic-check').length}`;
    });
  };
  document.querySelectorAll('.topic-check').forEach((input) => {
    input.addEventListener('change', () => {
      const saved = read();
      if (input.checked) saved[input.dataset.topicId] = true;
      else delete saved[input.dataset.topicId];
      write(saved);
      refresh();
    });
  });
  document.querySelectorAll('[data-reset-checks]').forEach((button) => {
    button.addEventListener('click', () => {
      if (!window.confirm('이 페이지의 완료 표시를 모두 지울까요?')) return;
      const saved = read();
      document.querySelectorAll('.topic-check').forEach((input) => delete saved[input.dataset.topicId]);
      write(saved);
      refresh();
    });
  });
  refresh();
})();
</script>"""


def esc(value):
    return (str(value or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def safe_href(url):
    try:
        parsed = urlparse(str(url or ""))
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return esc(url)
    except Exception:
        pass
    return "#"


def date_label(value):
    date = dt.datetime.strptime(value, "%Y-%m-%d")
    return f"{date.year}년 {date.month}월 {date.day}일 ({WEEKDAY[date.weekday()]})"


def topic_page_id(date, category_key, topic):
    value = topic.get("topic_id") or "|".join([
        date,
        category_key,
        str(topic.get("topic", "")),
        *sorted(str(a.get("link", "")) for a in topic.get("articles", [])),
    ])
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_-]{1,40}", text):
        return text
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def landing_value(topic, field, fallback=None):
    landing = topic.get("landing") or {}
    value = landing.get(field)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback if fallback is not None else []


def render_list(items, ordered=False):
    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(f"<li>{esc(item)}</li>" for item in items) + f"</{tag}>"


def render_topic(idx, topic, detail_href=None, check_id=None):
    arts = "".join(
        f'<li><a href="{safe_href(article.get("link"))}" target="_blank" rel="noopener">'
        f'{esc(article.get("title"))}</a>'
        f' <span class="amet">· {esc(article.get("source"))} '
        f'{esc(article.get("published_label"))}</span></li>'
        for article in topic.get("articles", [])
    )
    detail = f'<a class="detail-link" href="{esc(detail_href)}">상세 조사 정리 →</a>' if detail_href else ""
    check = render_completion_control(check_id) if check_id else ""
    return f"""<article class="topic">
<div class="tnum">{idx:02d}</div>
{check}
<div class="ttitle">{esc(topic.get("topic"))}</div>
<p class="tbasis">{esc(topic.get("basis"))}</p>
{detail}
<ul class="arts">{arts}</ul>
</article>"""


def render_completion_control(check_id):
    return f'''<div class="topic-tools"><label class="complete-toggle">
<input class="topic-check" type="checkbox" data-topic-id="{esc(check_id)}">
<span>완료 표시</span></label><span class="complete-note">이 브라우저에 저장</span></div>'''


def render_topic_page(brief, category_key, category, topic, is_celeb=False):
    date = brief["date"]
    page_id = topic_page_id(date, category_key, topic)
    landing = topic.get("landing") or {}
    lead = landing_value(topic, "lead", topic.get("basis", ""))
    verification = landing_value(
        topic,
        "verification_note",
        "기사 원문 3개를 확인한 뒤 날짜·수치·대상을 확정하세요.",
    )
    facts = landing_value(topic, "confirmed_facts", [])
    steps = landing_value(topic, "reader_steps", [])
    practical = landing_value(topic, "practical_points", [])
    structure = landing_value(topic, "writing_structure", [])
    headlines = landing_value(topic, "headline_options", [topic.get("topic", "")])
    keywords = landing_value(topic, "keywords", [topic.get("topic", "")])
    internal = landing_value(topic, "internal_link_ideas", [])
    cautions = landing_value(topic, "cautions", [])
    section = "연예인 건강" if is_celeb else category.get("label", category_key)
    facts = facts or [article.get("summary") or article.get("title") for article in topic.get("articles", [])]
    steps = steps or [
        "관련 기사 3개의 원문을 확인합니다.",
        "공통 사실과 기사별 추가 정보를 나눠 적습니다.",
        "수치·날짜·대상은 공식 자료로 다시 확인합니다.",
    ]
    structure = structure or ["뉴스 리드", "핵심 팩트", "기사별 차이", "독자용 체크리스트", "마무리"]
    source_cards = []
    for index, article in enumerate(topic.get("articles", []), 1):
        source_cards.append(
            f'<article class="source-card"><div class="tnum">출처 {index} · '
            f'{esc(article.get("source"))} {esc(article.get("published_label"))}</div>'
            f'<a href="{safe_href(article.get("link"))}" target="_blank" rel="noopener">'
            f'{esc(article.get("title"))}</a>'
            f'<p>{esc(article.get("summary") or "원문에서 세부 내용을 확인하세요.")}</p></article>'
        )
    warning = f'<div class="warning"><strong>작성 전 확인</strong><br>{esc(verification)}</div>'
    caution_block = (
        f'<div class="detail-section"><h3>주의할 점</h3>{render_list(cautions)}</div>'
        if cautions else ""
    )
    internal_block = (
        f'<div class="detail-section"><h3>내부링크 아이디어</h3>{render_list(internal)}</div>'
        if internal else ""
    )
    completion = render_completion_control(f"{date}:{page_id}")
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="briefing-date" content="{esc(date)}">
<meta name="description" content="{esc(str(lead)[:150])}">
<title>{esc(topic.get("topic"))} | 블로그 브리핑</title>
<style>{CSS}</style></head><body><div class="wrap">
<div class="back"><a href="../{esc(date)}.html">← {date_label(date)} 브리핑으로 돌아가기</a></div>
<div class="hero"><div class="date">{esc(category.get("label"))} · {esc(section)}</div>
{completion}<h2>{esc(topic.get("topic"))}</h2><p>{esc(lead)}</p>{warning}</div>
<section class="detail-section"><h3>핵심 팩트</h3>{render_list(facts)}</section>
<section class="detail-section"><h3>독자용 확인법·체크리스트</h3>{render_list(steps, ordered=True)}</section>
<section class="detail-section"><h3>독자에게 실익이 있는 포인트</h3>{render_list(practical)}</section>
{caution_block}
<section class="detail-section"><h3>관련 기사 3개</h3><div class="sources">{"".join(source_cards)}</div></section>
<section class="detail-section"><h3>블로그 글 구성안</h3>{render_list(structure, ordered=True)}</section>
<section class="detail-section"><h3>제목 후보</h3>{render_list(headlines)}</section>
<section class="detail-section"><h3>검색 키워드</h3><div class="chips">{"".join(f'<span class="chip">{esc(item)}</span>' for item in keywords)}</div></section>
{internal_block}
<footer>기사 원문을 확인한 뒤 미확정 정보와 수치를 보완해 발행하세요.<br>
<a href="../tracker.html">작성 관리표 보기</a></footer>
</div>{CHECK_SCRIPT}</body></html>"""


def render_day(brief, prev_date=None, next_date=None):
    generated = dt.datetime.fromisoformat(brief["generated_at"]).strftime("%H:%M")
    body = []
    for key, category in brief["categories"].items():
        color = ACCENT.get(key, "#666")
        meta = esc(category.get("category_name") or "")
        if category.get("blog"):
            meta += f' · blog.naver.com/{esc(category["blog"])}'
        parts = [
            f'<section class="cat"><div class="cathead">'
            f'<span class="dot" style="background:{color}"></span>'
            f'<h2>{esc(category.get("label"))}</h2></div>'
            f'<p class="catmeta">{meta}</p>'
        ]
        if category.get("topics"):
            parts += [
                render_topic(
                    i + 1,
                    topic,
                    f'topics/{topic_page_id(brief["date"], key, topic)}.html',
                    f'{brief["date"]}:{topic_page_id(brief["date"], key, topic)}',
                )
                for i, topic in enumerate(category["topics"])
            ]
        else:
            parts.append('<p class="empty">오늘 새로 잡힌 주제가 없습니다. '
                         '출처나 검색 키워드를 점검해보세요.</p>')
        if category.get("celeb_topics"):
            parts.append('<p class="celebhead">연예인 건강 이슈</p>')
            parts += [
                render_topic(
                    i + 1,
                    topic,
                    f'topics/{topic_page_id(brief["date"], key, topic)}.html',
                    f'{brief["date"]}:{topic_page_id(brief["date"], key, topic)}',
                ).replace('class="topic"', 'class="topic celeb"')
                for i, topic in enumerate(category["celeb_topics"])
            ]
        parts.append("</section>")
        body.append("".join(parts))

    nav = [
        '<a href="./">최신</a>',
        '<a href="archive.html">지난 브리핑</a>',
        '<a href="tracker.html">작성 관리</a>',
    ]
    if prev_date:
        nav.insert(0, f'<a href="{prev_date}.html">← {prev_date[5:]}</a>')
    if next_date:
        nav.append(f'<a href="{next_date}.html">{next_date[5:]} →</a>')

    checkbar = '<div class="checkbar"><strong data-check-summary>완료 0 / 전체 0</strong><span>주제 카드의 완료 표시는 이 브라우저에 저장됩니다.</span><button type="button" data-reset-checks>이 페이지 체크 지우기</button></div>'
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="briefing-date" content="{esc(brief["date"])}">
<title>{date_label(brief["date"])} 블로그 브리핑</title>
<style>{CSS}</style></head><body><div class="wrap">
<header class="top"><h1>오늘의 블로그 브리핑</h1>
<div class="date">{date_label(brief["date"])} · {generated} 생성</div>
<nav class="nav">{"".join(nav)}</nav></header>
{checkbar}
{"".join(body)}
<footer>기사 원문 링크는 새 탭에서 열립니다. 발행 시각은 한국 시간 기준.<br>
기사 1개당 서로 다른 관련 기사 3개를 우선 연결합니다.</footer>
</div>{CHECK_SCRIPT}</body></html>"""


def render_archive(dates):
    items = []
    for value in dates:
        items.append(f'<li><a href="{value}.html">{date_label(value)}</a></li>')
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>지난 브리핑</title><style>{CSS}</style></head><body><div class="wrap">
<header class="top"><h1>지난 브리핑</h1>
<div class="date">{len(dates)}일치</div>
<nav class="nav"><a href="./">최신으로</a><a href="tracker.html">작성 관리</a></nav></header>
<ul class="arch">{"".join(items)}</ul></div></body></html>"""


def render_tracker(rows):
    body = []
    for row in rows:
        published_url = row.get("발행 URL", "")
        published = (
            f'<a href="{safe_href(published_url)}" target="_blank" rel="noopener">'
            f'{esc(published_url)}</a>' if published_url else ""
        )
        body.append(
            "<tr>"
            f"<td>{esc(row.get('날짜'))}</td>"
            f"<td>{esc(row.get('카테고리'))}<br>{esc(row.get('구분'))}</td>"
            f"<td>{esc(row.get('주제'))}</td>"
            f"<td class=\"status\">{esc(row.get('작성 여부'))}</td>"
            f"<td class=\"status\">{esc(row.get('발행 여부'))}</td>"
            f"<td>{published}</td>"
            "</tr>"
        )
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>블로그 작성 관리</title><style>{CSS}</style></head><body><div class="wrap">
<header class="top"><h1>블로그 작성 관리</h1>
<div class="date">Excel 또는 Google Sheets에서 editorial_tracker.csv를 수정하세요.</div>
<nav class="nav"><a href="./">최신 브리핑</a><a href="archive.html">지난 브리핑</a>
<a href="editorial_tracker.csv">CSV 내려받기</a></nav></header>
<table class="tracker"><thead><tr><th>날짜</th><th>카테고리</th><th>주제</th>
<th>작성 여부</th><th>발행 여부</th><th>발행 URL</th></tr></thead>
<tbody>{"".join(body) or '<tr><td colspan="6">아직 주제가 없습니다.</td></tr>'}</tbody></table>
</div></body></html>"""


def main():
    os.makedirs(DOCS, exist_ok=True)
    os.makedirs(TOPICS_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(ROOT, "data", "brief-*.json")))
    if not files:
        print("brief-*.json 이 없습니다. process.py 를 먼저 돌리세요.")
        return
    dates = [os.path.basename(path)[6:-5] for path in files]

    for i, path in enumerate(files):
        with open(path, encoding="utf-8") as f:
            brief = json.load(f)
        for category_key, category in brief.get("categories", {}).items():
            for topic in category.get("topics", []):
                page_id = topic_page_id(brief["date"], category_key, topic)
                with open(os.path.join(TOPICS_DIR, f"{page_id}.html"), "w", encoding="utf-8") as topic_file:
                    topic_file.write(render_topic_page(brief, category_key, category, topic))
            for topic in category.get("celeb_topics", []):
                page_id = topic_page_id(brief["date"], category_key, topic)
                with open(os.path.join(TOPICS_DIR, f"{page_id}.html"), "w", encoding="utf-8") as topic_file:
                    topic_file.write(render_topic_page(brief, category_key, category, topic, is_celeb=True))
        html = render_day(
            brief,
            prev_date=dates[i - 1] if i > 0 else None,
            next_date=dates[i + 1] if i < len(dates) - 1 else None,
        )
        with open(os.path.join(DOCS, f"{dates[i]}.html"), "w", encoding="utf-8") as f:
            f.write(html)
        if i == len(files) - 1:
            with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
                f.write(html)

    with open(os.path.join(DOCS, "archive.html"), "w", encoding="utf-8") as f:
        f.write(render_archive(list(reversed(dates))))

    tracker_path = os.path.join(ROOT, "data", "editorial_tracker.csv")
    if os.path.exists(tracker_path):
        with open(tracker_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        with open(os.path.join(DOCS, "tracker.html"), "w", encoding="utf-8") as f:
            f.write(render_tracker(rows))

    with open(os.path.join(DOCS, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")
    print(f"사이트 생성 완료 - {len(dates)}일치, 최신 {dates[-1]}")


if __name__ == "__main__":
    main()
