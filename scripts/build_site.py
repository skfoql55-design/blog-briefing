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
from urllib.parse import quote, urlparse

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
TOPICS_DIR = os.path.join(DOCS, "topics")
RUNS_DOCS_DIR = os.path.join(DOCS, "runs")
WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"]
ACCENT = {
    "economy_kr_stock": "#1d6f5c",
    "economy_us_stock": "#256d8a",
    "economy_finance": "#3f7d5a",
    "economy_policy": "#7a5b2b",
    "economy_property": "#8a5a44",
    "health_current": "#a33a5b",
    "health_info": "#c06a3a",
    "living": "#6b7d3e",
    "cartech_auto": "#2f5b9c",
    "cartech_it": "#5a55a5",
    "paleontology": "#7c6650",
    "broadcast": "#8a4f9d",
    "sports": "#b36b00",
    "fashion_beauty": "#b04e78",
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
.interest-badge{display:inline-block;margin-left:7px;background:var(--chip);border-radius:99px;padding:2px 7px;color:var(--muted);font-size:.68rem;font-weight:500;vertical-align:1px}
.ttitle{font-size:1rem;font-weight:600;margin:3px 0 6px;letter-spacing:-.01em}
.tbasis{font-size:.87rem;color:var(--muted);margin:0 0 11px}
.topic-tools{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:2px 0 7px}
.complete-toggle{display:inline-flex;align-items:center;gap:6px;color:var(--muted);font-size:.78rem;cursor:pointer;user-select:none}
.complete-toggle input{width:16px;height:16px;accent-color:#3b8f5b;cursor:pointer}
.complete-note{color:var(--muted);font-size:.72rem}
.trend-summary{color:var(--muted);font-size:.75rem;margin:4px 0 0 19px}
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
.dashboard-tools{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}
.dashboard-tools input,.dashboard-tools select{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:8px 10px;font:inherit;font-size:.82rem}
.category-table{width:100%;border-collapse:collapse;font-size:.78rem;background:var(--card);border:1px solid var(--line)}
.category-table th,.category-table td{padding:9px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.category-table th{color:var(--muted);font-weight:600;white-space:nowrap}
.category-table a{color:var(--ink);font-weight:600;text-decoration:none}
.category-table a:hover{text-decoration:underline}
.tag{display:inline-block;background:var(--chip);border-radius:99px;padding:2px 7px;color:var(--muted);font-size:.7rem;white-space:nowrap}
.dashboard-check{white-space:nowrap;color:var(--muted);font-size:.75rem}
.dashboard-check input{accent-color:#3b8f5b}
@media (max-width:700px){.category-table{display:block;overflow-x:auto;white-space:nowrap}.category-table td.topic-cell{white-space:normal;min-width:230px}}
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
.table-scroll{overflow-x:auto}
.comparison{width:100%;border-collapse:collapse;font-size:.78rem;background:var(--card)}
.comparison th,.comparison td{padding:8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.comparison th{color:var(--muted);font-weight:600;white-space:nowrap}
.comparison a{color:var(--ink)}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:0 0 18px}
.stat-card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px}
.stat-card strong{display:block;font-size:1.35rem}
.stat-card span{color:var(--muted);font-size:.76rem}
.headline-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px}
.headline-option{display:flex;gap:8px;align-items:flex-start;background:var(--card);border:1px solid var(--line);border-radius:9px;padding:9px 10px;cursor:pointer}
.headline-option:has(input:checked){border-color:#3b8f5b;box-shadow:0 0 0 1px #3b8f5b inset}
.headline-option input{margin-top:4px;accent-color:#3b8f5b}
.headline-option span{font-size:.83rem;line-height:1.45}
.frame-tag{display:inline-block;margin-right:6px;color:var(--muted);font-size:.7rem;background:var(--chip);border-radius:99px;padding:1px 6px}
.headline-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 10px}
.headline-actions button{border:1px solid var(--line);background:var(--chip);color:var(--muted);border-radius:7px;padding:6px 10px;cursor:pointer}
.headline-actions button:hover{color:var(--ink)}
.selected-headline{color:var(--muted);font-size:.8rem}
.similarity-list{display:grid;gap:7px}
.similarity-row{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:9px 11px}
.similarity-row.high{border-color:#e09a87;background:#fff8f5}
.similarity-row.low{border-color:#8bb99a}
@media (prefers-color-scheme:dark){.similarity-row.high{background:#2b211d}.similarity-row.low{background:#1b2920}}
.similarity-row summary{cursor:pointer;display:flex;justify-content:space-between;gap:10px;list-style:none;font-size:.83rem}
.similarity-row summary::-webkit-details-marker{display:none}
.similarity-score{white-space:nowrap;color:var(--muted);font-size:.75rem}
.similarity-row p{font-size:.78rem;color:var(--muted);margin:8px 0 0}
.similarity-row a{color:var(--ink)}
.method-note{color:var(--muted);font-size:.78rem;margin:0 0 10px}
.judgment{background:var(--chip);border-radius:9px;padding:10px 12px;font-size:.82rem;margin-bottom:10px}
.judgment strong{margin-right:5px}
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
  document.querySelectorAll('[data-title-picker]').forEach((picker) => {
    const selected = picker.querySelector('[data-selected-title]');
    const copyButton = picker.querySelector('[data-copy-title]');
    const inputs = picker.querySelectorAll('input[name="headline"]');
    inputs.forEach((input) => input.addEventListener('change', () => {
      if (selected) selected.textContent = input.value;
    }));
    if (copyButton) copyButton.addEventListener('click', async () => {
      const input = picker.querySelector('input[name="headline"]:checked');
      if (!input) { if (selected) selected.textContent = '먼저 제목을 선택하세요.'; return; }
      try {
        await navigator.clipboard.writeText(input.value);
        if (selected) selected.textContent = '복사 완료: ' + input.value;
      } catch (_) {
        if (selected) selected.textContent = '복사할 제목: ' + input.value;
      }
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


def run_label(run_id, brief):
    value = str(brief.get("generated_at") or "")
    try:
        generated = dt.datetime.fromisoformat(value)
        return f"{date_label(brief['date'])} · {generated.strftime('%H:%M:%S')} 실행"
    except ValueError:
        return f"{date_label(brief['date'])} · {run_id} 실행"


CATEGORY_TAXONOMY = {
    "economy_kr_stock": ("경제", "한국 주식"),
    "economy_us_stock": ("경제", "미국 주식"),
    "economy_finance": ("경제", "재테크"),
    "economy_policy": ("경제", "한국 정책 이슈"),
    "economy_property": ("경제", "부동산"),
    "health_current": ("건강", "최신 건강 이슈"),
    "health_info": ("건강", "생활 건강 정보"),
    "health_celebrity": ("건강", "연예인 건강"),
    "living": ("리빙", "생활 꿀팁"),
    "cartech_auto": ("카테크·IT", "자동차"),
    "cartech_it": ("카테크·IT", "컴퓨터·IT"),
    "paleontology": ("고생물", "공룡·화석·고대 생명"),
    "broadcast": ("방송연예", "드라마·예능·OTT"),
    "sports": ("스포츠", "국내·해외 스포츠"),
    "fashion_beauty": ("패션뷰티", "패션·뷰티"),
}


def category_info(category_key, category):
    if category_key in CATEGORY_TAXONOMY:
        return CATEGORY_TAXONOMY[category_key]
    label = str(category.get("label") or category_key)
    if "·" in label:
        parent, child = [part.strip() for part in label.split("·", 1)]
        return parent, child
    return label, str(category.get("category_name") or label)


def topic_content_type(topic, category_key):
    value = str(topic.get("content_type") or "").strip()
    if value:
        return value
    text = " ".join([
        str(topic.get("topic") or ""),
        str(topic.get("basis") or ""),
        str(category_key or ""),
    ]).lower()
    if any(word in text for word in ("리콜", "보안", "개인정보", "사기", "위험", "결함", "안전")):
        return "주의·안전"
    if any(word in text for word in ("방법", "꿀팁", "관리", "설정", "확인법", "습관", "체크")):
        return "꿀팁·실행"
    if any(word in text for word in ("비교", "가격", "구매", "추천", "중고차", "제품")):
        return "비교·구매"
    if any(word in text for word in ("정책", "발표", "시행", "이슈", "변경", "결과", "신작", "경기")):
        return "뉴스·변경"
    return "뉴스·정보"


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


def interest_badge(topic):
    interest = topic.get("interest") or {}
    score = interest.get("score")
    if score is None:
        return ""
    method = "검색 트렌드" if "NAVER" in str(interest.get("method", "")) else "기사 기반"
    return f'<span class="interest-badge">관심도 {esc(score)} · {method}</span>'


def render_headline_picker(headlines, page_id, metadata=None):
    metadata = {item.get("title"): item for item in (metadata or []) if isinstance(item, dict)}
    options = []
    for index, headline in enumerate(headlines[:30], 1):
        meta = metadata.get(headline, {})
        frame = f'<span class="frame-tag">{esc(meta.get("frame") or "정보형")}</span>'
        options.append(
            f'<label class="headline-option"><input type="radio" name="headline" '
            f'value="{esc(headline)}"><span>{index:02d}. {frame}{esc(headline)}</span></label>'
        )
    return f'''<div data-title-picker>
<div class="headline-actions"><button type="button" data-copy-title>선택 제목 복사</button>
<span class="selected-headline" data-selected-title>제목을 하나 선택하세요.</span></div>
<div class="headline-grid">{"".join(options)}</div></div>'''


def naver_blog_search_url(query):
    return f"https://search.naver.com/search.naver?where=blog&query={quote(str(query or ''))}"


def render_similarity(topic):
    similarity = topic.get("naver_blog_similarity") or {}
    status = similarity.get("status")
    query = similarity.get("query") or topic.get("topic", "")
    if status != "ok":
        note = similarity.get("note") or "네이버 블로그 검색 결과를 아직 확인하지 못했습니다."
        return (
            f'<p class="method-note">{esc(note)} '
            f'<a href="{esc(naver_blog_search_url(query))}" target="_blank" rel="noopener">'
            f'네이버 블로그에서 직접 검색 →</a></p>'
        )
    candidates = similarity.get("candidates") or []
    if not candidates:
        return f'<p class="method-note">{esc(similarity.get("note"))}</p>'
    rows = []
    for candidate in candidates:
        score = float(candidate.get("score") or 0)
        level = "high" if score >= 70 else ("low" if score < 45 else "")
        match = candidate.get("match") or {}
        match_title = match.get("title") or "유사 제목을 찾지 못했습니다."
        match_link = safe_href(match.get("link"))
        match_html = (
            f'<a href="{match_link}" target="_blank" rel="noopener">{esc(match_title)}</a>'
            if match.get("link") else esc(match_title)
        )
        rows.append(
            f'<details class="similarity-row {level}"><summary>'
            f'<span>{esc(candidate.get("title"))}</span>'
            f'<span class="similarity-score">유사도 추정 {score:.1f}%</span></summary>'
            f'<p>가장 가까운 검색 결과: {match_html}</p></details>'
        )
    return (
        f'<p class="method-note">{esc(similarity.get("note"))} '
        f'(검색 결과 {esc(similarity.get("checked_count", 0))}개 비교)</p>'
        f'<div class="similarity-list">{"".join(rows)}</div>'
    )


def render_top_n_judgment(topic):
    judgment = (topic.get("landing") or {}).get("top_n_judgment") or {}
    if not judgment:
        return ""
    result = judgment.get("result") or "확인 필요"
    number = judgment.get("recommended_number")
    number_text = f"TOP{number}" if number else "해당 없음"
    return (
        f'<div class="judgment"><strong>TOP N 판단</strong>'
        f'{esc(result)} · 권장 숫자: {esc(number_text)} · 유형: {esc(judgment.get("type") or "정보형")}<br>'
        f'<span>{esc(judgment.get("reason") or "원문 확인 후 판단하세요.")}</span></div>'
    )


CELEBRITY_PROFILE_FIELDS = ("나이", "혈액형", "MBTI", "고향", "학력", "재산", "활동")


def render_celebrity_profile(topic):
    profile = ((topic.get("landing") or {}).get("celebrity_profile") or {})
    name = profile.get("name") or "인물명 확인 필요"
    fields = profile.get("fields") or {}
    rows = []
    for field_name in CELEBRITY_PROFILE_FIELDS:
        item = fields.get(field_name) or {}
        value = item.get("value") or "미공개·확인 필요"
        status = item.get("status") or "원문 확인 필요"
        refs = item.get("source_article_ids") or []
        ref_text = " · 근거 연결" if refs else ""
        rows.append(
            f'<tr><th>{esc(field_name)}</th><td>{esc(value)}'
            f'<br><span class="amet">{esc(status)}{ref_text}</span></td></tr>'
        )
    if not rows:
        rows.append('<tr><td colspan="2">프로필 정보는 공식 자료 확인 후 입력됩니다.</td></tr>')
    return (
        f'<section class="detail-section"><h3>연예인 프로필 확인</h3>'
        f'<p class="method-note"><strong>{esc(name)}</strong> · 기사 근거가 없는 나이·MBTI·재산 등은 추정하지 않습니다.</p>'
        f'<div class="table-scroll"><table class="comparison"><thead><tr><th>항목</th><th>확인 내용</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div></section>'
    )


def render_celebrity_blog_references(topic):
    references = topic.get("celebrity_blog_references") or {}
    query = references.get("query") or topic.get("topic", "")
    if references.get("status") != "ok":
        note = references.get("note") or "네이버 블로그 참고글을 아직 확인하지 못했습니다."
        return (
            f'<section class="detail-section"><h3>네이버 블로그 참고글</h3>'
            f'<p class="method-note">{esc(note)} '
            f'<a href="{safe_href(naver_blog_search_url(query))}" target="_blank" rel="noopener">직접 검색 →</a></p></section>'
        )
    candidates = references.get("candidates") or []
    cards = []
    for index, item in enumerate(candidates[:3], 1):
        hits = item.get("keyword_hits") or []
        cards.append(
            f'<article class="source-card"><div class="tnum">참고글 {index} · '
            f'키워드 포함도 {esc(item.get("match_score"))}% · {esc(item.get("postdate"))}</div>'
            f'<a href="{safe_href(item.get("link"))}" target="_blank" rel="noopener">{esc(item.get("title"))}</a>'
            f'<p>{esc(item.get("bloggername"))} · 검색 확인 키워드: {esc(", ".join(hits) or "없음")}</p>'
            f'<p>{esc(item.get("description") or "검색 요약문이 없습니다. 원문에서 확인하세요.")}</p></article>'
        )
    cards_html = "".join(cards) or '<p class="empty">참고글이 없습니다.</p>'
    return (
        f'<section class="detail-section"><h3>네이버 블로그 참고글 3개</h3>'
        f'<p class="method-note">{esc(references.get("note"))} · 검색 결과 {esc(references.get("checked_count", 0))}개 확인</p>'
        f'<div class="sources">{cards_html}</div></section>'
    )


def render_celebrity_keyword_ideas(topic):
    profile = ((topic.get("landing") or {}).get("celebrity_profile") or {})
    ideas = profile.get("category_keyword_ideas") or {}
    if not ideas:
        return ""
    rows = []
    for category, keywords in ideas.items():
        links = []
        for keyword in keywords[:8]:
            links.append(
                f'<a class="chip" href="{safe_href(naver_blog_search_url(keyword))}" '
                f'target="_blank" rel="noopener">{esc(keyword)}</a>'
            )
        rows.append(
            f'<tr><th>{esc(category)}</th><td><div class="chips">{"".join(links)}</div></td></tr>'
        )
    return (
        '<section class="detail-section"><h3>카테고리별 연예인 키워드 추천</h3>'
        '<p class="method-note">키워드를 누르면 네이버 블로그 검색으로 이동합니다. 출연료·재산·몸무게 등은 공식 공개 자료가 있을 때만 본문 근거로 사용하세요.</p>'
        f'<div class="table-scroll"><table class="comparison"><thead><tr><th>카테고리</th><th>추천 검색 키워드</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>'
    )


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
<div class="tnum">{idx:02d}{interest_badge(topic)}</div>
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


def render_article_comparison(articles):
    rows = []
    for index, article in enumerate(articles[:3], 1):
        link = safe_href(article.get("link"))
        title = esc(article.get("title"))
        title_html = f'<a href="{link}" target="_blank" rel="noopener">{title}</a>'
        rows.append(
            f'<tr><td>{index}</td><td>{esc(article.get("source"))}<br>'
            f'<span class="amet">{esc(article.get("published_label"))}</span></td>'
            f'<td>{title_html}</td><td>{esc(article.get("summary") or "원문 확인 필요")}</td></tr>'
        )
    return (
        '<div class="table-scroll"><table class="comparison"><thead><tr>'
        '<th>번호</th><th>출처·발행</th><th>기사 제목</th><th>수집된 요약</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


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
    headline_metadata = landing.get("headline_metadata") or []
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
    celebrity_profile_block = render_celebrity_profile(topic) if is_celeb else ""
    celebrity_blog_block = render_celebrity_blog_references(topic) if is_celeb else ""
    celebrity_keyword_block = render_celebrity_keyword_ideas(topic) if is_celeb else ""
    completion = render_completion_control(f"{date}:{page_id}")
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="briefing-date" content="{esc(date)}">
<meta name="description" content="{esc(str(lead)[:150])}">
<title>{esc(topic.get("topic"))} | 블로그 브리핑</title>
<style>{CSS}</style></head><body><div class="wrap">
<div class="back"><a href="../{esc(date)}.html">← {date_label(date)} 브리핑으로 돌아가기</a> · <a href="../celebrity.html">연예인 정보 탭</a></div>
<div class="hero"><div class="date">{esc(category.get("label"))} · {esc(section)} {interest_badge(topic)}</div>
{completion}<h2>{esc(topic.get("topic"))}</h2><p>{esc(lead)}</p>{warning}</div>
<section class="detail-section"><h3>핵심 팩트</h3>{render_list(facts)}</section>
<section class="detail-section"><h3>독자용 확인법·체크리스트</h3>{render_list(steps, ordered=True)}</section>
<section class="detail-section"><h3>독자에게 실익이 있는 포인트</h3>{render_list(practical)}</section>
{caution_block}
<section class="detail-section"><h3>관련 기사 3개</h3><div class="sources">{"".join(source_cards)}</div></section>
<section class="detail-section"><h3>기사 3개 비교표</h3><p class="method-note">아래 요약은 수집된 기사 정보이며, 발행 전에는 각 원문을 직접 확인하세요.</p>{render_article_comparison(topic.get("articles", []))}</section>
{celebrity_profile_block}
{celebrity_keyword_block}
{celebrity_blog_block}
<section class="detail-section"><h3>블로그 글 구성안</h3>{render_list(structure, ordered=True)}</section>
<section class="detail-section"><h3>홈판 제목 추천 30개</h3>
<p class="method-note">제목을 하나 선택한 뒤 복사해서 블로그 초안에 사용하세요.</p>
{render_top_n_judgment(topic)}
{render_headline_picker(headlines, page_id, headline_metadata)}</section>
<section class="detail-section"><h3>네이버 블로그 제목 유사도 조사</h3>
<p class="method-note">네이버 블로그 검색 결과 제목과 비교한 참고용 추정치입니다. 실제 검색 노출 순위나 표절 여부를 확정하는 값은 아닙니다.</p>
{render_similarity(topic)}</section>
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
        trend_summary = category.get("trend_summary") or []
        if trend_summary:
            trend_text = " · ".join(
                f'{esc(item.get("keyword"))} {esc(item.get("score"))}'
                for item in trend_summary[:5]
            )
            meta += f'<div class="trend-summary">검색 관심 키워드: {trend_text}</div>'
        shopping_summary = category.get("shopping_summary") or []
        if shopping_summary:
            shopping_text = " · ".join(
                f'{esc(item.get("keyword"))} {esc(item.get("score"))} '
                f'(변화 {float(item.get("momentum", 0)):+g})'
                for item in shopping_summary[:5]
            )
            meta += f'<div class="trend-summary">쇼핑 클릭 관심도(상대지수): {shopping_text}</div>'
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
        '<a href="keywords/">키워드 연구</a>',
        '<a href="archive.html">지난 브리핑</a>',
        '<a href="category.html">카테고리별</a>',
        '<a href="celebrity.html">연예인 정보</a>',
        '<a href="stats.html">통계</a>',
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


def render_run_page(brief, run_id):
    generated = dt.datetime.fromisoformat(brief["generated_at"]).strftime("%H:%M:%S")
    body = []
    for key, category in brief.get("categories", {}).items():
        color = ACCENT.get(key, "#666")
        parts = [
            f'<section class="cat"><div class="cathead">'
            f'<span class="dot" style="background:{color}"></span>'
            f'<h2>{esc(category.get("label"))}</h2></div>'
        ]
        topics = category.get("topics") or []
        if topics:
            parts += [
                render_topic(
                    i + 1,
                    topic,
                    None,
                    f'{run_id}:{key}:{topic_page_id(brief["date"], key, topic)}',
                )
                for i, topic in enumerate(topics)
            ]
        else:
            parts.append('<p class="empty">이 실행에서는 선정된 주제가 없습니다.</p>')
        if category.get("celeb_topics"):
            parts.append('<p class="celebhead">연예인 건강 이슈</p>')
            parts += [
                render_topic(
                    i + 1,
                    topic,
                    None,
                    f'{run_id}:{key}:celeb:{topic_page_id(brief["date"], key, topic)}',
                ).replace('class="topic"', 'class="topic celeb"')
                for i, topic in enumerate(category["celeb_topics"])
            ]
        parts.append("</section>")
        body.append("".join(parts))

    checkbar = '<div class="checkbar"><strong data-check-summary>완료 0 / 전체 0</strong><span>이 실행 기록의 완료 표시는 이 브라우저에 저장됩니다.</span><button type="button" data-reset-checks>이 페이지 체크 지우기</button></div>'
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{date_label(brief["date"])} {generated} 실행 기록</title><style>{CSS}</style></head><body><div class="wrap">
<header class="top"><h1>브리핑 실행 기록</h1>
<div class="date">{date_label(brief["date"])} · {generated} 실행</div>
<nav class="nav"><a href="../">최신 브리핑</a><a href="../keywords/">키워드 연구</a><a href="../archive.html">날짜별 보관</a><a href="../category.html">카테고리별</a><a href="../celebrity.html">연예인 정보</a><a href="../stats.html">통계</a><a href="../tracker.html">작성 관리</a></nav></header>
{checkbar}
{"".join(body)}
<footer>같은 날짜에 다시 실행된 브리핑도 이 페이지에서 확인할 수 있습니다.</footer>
</div>{CHECK_SCRIPT}</body></html>"""


def render_archive(dates, runs=None):
    items = []
    for value in dates:
        items.append(f'<li><a href="{value}.html">{date_label(value)}</a></li>')
    run_items = []
    for run_id, brief in (runs or []):
        topic_count = sum(
            len(block.get("topics", [])) + len(block.get("celeb_topics", []))
            for block in brief.get("categories", {}).values()
        )
        run_items.append(
            f'<li><a href="runs/{esc(run_id)}.html">{esc(run_label(run_id, brief))}</a>'
            f' <span class="amet">· 주제 {topic_count}개</span></li>'
        )
    run_section = (
        '<h2>실행 기록</h2><p class="date">같은 날짜에 다시 실행한 결과도 시간별로 보관됩니다.</p>'
        f'<ul class="arch">{"".join(run_items) or "<li>아직 실행 기록이 없습니다.</li>"}</ul>'
    )
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>지난 브리핑</title><style>{CSS}</style></head><body><div class="wrap">
<header class="top"><h1>지난 브리핑</h1>
<div class="date">{len(dates)}일치</div>
<nav class="nav"><a href="./">최신으로</a><a href="keywords/">키워드 연구</a><a href="category.html">카테고리별</a><a href="celebrity.html">연예인 정보</a><a href="stats.html">통계</a><a href="tracker.html">작성 관리</a></nav></header>
<h2>날짜별 브리핑</h2><ul class="arch">{"".join(items) or "<li>아직 날짜별 브리핑이 없습니다.</li>"}</ul>
{run_section}</div></body></html>"""


def render_category_dashboard(brief, tracker_rows=None):
    tracker_map = {row.get("topic_id"): row for row in (tracker_rows or []) if row.get("topic_id")}
    rows = []
    category_options = []
    seen_categories = set()
    total = written_count = published_count = 0
    for category_key, category in brief.get("categories", {}).items():
        parent, subcategory = category_info(category_key, category)
        if parent not in seen_categories:
            category_options.append(parent)
            seen_categories.add(parent)
        all_topics = [(topic, "일반") for topic in category.get("topics", [])]
        all_topics += [(topic, "연예인 건강") for topic in category.get("celeb_topics", [])]
        for topic, section in all_topics:
            page_id = topic_page_id(brief["date"], category_key, topic)
            topic_id = topic.get("topic_id") or page_id
            tracker = tracker_map.get(topic_id, {})
            written = tracker.get("작성 여부") or "미작성"
            published = tracker.get("발행 여부") or "미발행"
            content_type = topic_content_type(topic, category_key)
            interest = (topic.get("interest") or {}).get("score")
            interest_text = f"관심도 {interest}" if interest is not None else "관심도 미산정"
            shopping_interest = topic.get("shopping_interest") or {}
            if shopping_interest:
                interest_text += (
                    f' · 쇼핑 {shopping_interest.get("score")} '
                    f'(변화 {shopping_interest.get("momentum", 0):+})'
                )
            total += 1
            if "작성완료" in str(written).replace(" ", ""):
                written_count += 1
            if "발행완료" in str(published).replace(" ", "") or tracker.get("발행 URL"):
                published_count += 1
            row_subcategory = "연예인 건강" if section == "연예인 건강" else subcategory
            search_text = " ".join([
                parent, row_subcategory, section, content_type,
                str(topic.get("topic") or ""), str(topic.get("basis") or ""),
                str(shopping_interest.get("keyword") or ""),
            ])
            rows.append(
                f'<tr data-parent="{esc(parent)}" data-search="{esc(search_text.lower())}">'
                f'<td>{esc(parent)}</td><td><span class="tag">{esc(row_subcategory)}</span>'
                f'<br><span class="amet">{esc(section)}</span></td>'
                f'<td><span class="tag">{esc(content_type)}</span><br>'
                f'<span class="amet">{esc(interest_text)}</span></td>'
                f'<td class="topic-cell"><a href="topics/{esc(page_id)}.html">{esc(topic.get("topic"))}</a>'
                f'<br><span class="amet">{esc(topic.get("basis"))}</span></td>'
                f'<td class="status">{esc(written)}<br>{esc(published)}</td>'
                f'<td class="dashboard-check"><label><input class="topic-check" type="checkbox" '
                f'data-topic-id="{esc(brief["date"] + ":" + page_id)}"> 완료</label></td></tr>'
            )
    options = ''.join(f'<option value="{esc(value)}">{esc(value)}</option>' for value in category_options)
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>카테고리별 블로그 브리핑</title><style>{CSS}</style></head><body><div class="wrap">
<header class="top"><h1>카테고리별 블로그 브리핑</h1>
<div class="date">{date_label(brief["date"])} · 오늘 주제 {total}개 · 작성 완료 {written_count}개 · 발행 완료 {published_count}개</div>
<nav class="nav"><a href="./">오늘의 브리핑</a><a href="keywords/">키워드 연구</a><a href="archive.html">날짜별 보관</a><a href="category.html">카테고리별</a><a href="celebrity.html">연예인 정보</a><a href="stats.html">통계</a><a href="tracker.html">작성 관리</a></nav></header>
<div class="dashboard-tools"><select id="parent-filter"><option value="">전체 대분류</option>{options}</select>
<input id="topic-search" type="search" placeholder="주제·세부 카테고리 검색"></div>
<p class="date">세부 카테고리와 콘텐츠 유형을 확인하고, 상세 조사·작성 상태를 한눈에 관리할 수 있습니다.</p>
<table class="category-table"><thead><tr><th>대분류</th><th>세부 카테고리</th><th>콘텐츠 유형·관심도</th><th>주제</th><th>작성·발행</th><th>완료</th></tr></thead>
<tbody id="category-rows">{"".join(rows) or '<tr><td colspan="6">오늘 주제가 없습니다.</td></tr>'}</tbody></table>
<footer>완료 체크는 이 브라우저에 저장됩니다. 작성·발행 상태를 여러 기기에서 유지하려면 작성 관리표를 수정해 커밋하세요.</footer>
</div>{CHECK_SCRIPT}<script>
(() => {{
  const filter = document.getElementById('parent-filter');
  const search = document.getElementById('topic-search');
  const rows = [...document.querySelectorAll('#category-rows tr[data-parent]')];
  const apply = () => {{
    const parent = filter.value;
    const query = search.value.trim().toLowerCase();
    rows.forEach(row => {{
      const matchesParent = !parent || row.dataset.parent === parent;
      const matchesSearch = !query || (row.dataset.search || '').includes(query);
      row.style.display = matchesParent && matchesSearch ? '' : 'none';
    }});
  }};
  filter.addEventListener('change', apply);
  search.addEventListener('input', apply);
}})();
</script></body></html>"""


def render_celebrity_dashboard(brief):
    cards = []
    total = 0
    for category_key, category in brief.get("categories", {}).items():
        for topic in category.get("celeb_topics", []) or []:
            total += 1
            page_id = topic_page_id(brief["date"], category_key, topic)
            profile = ((topic.get("landing") or {}).get("celebrity_profile") or {})
            name = profile.get("name") or topic.get("topic") or "인물명 확인 필요"
            check_id = brief["date"] + ":" + page_id
            cards.append(
                f'<article class="topic celeb"><div class="tnum">{esc(category.get("label"))}</div>'
                f'{render_completion_control(check_id)}'
                f'<div class="ttitle">{esc(name)}</div><p class="tbasis">{esc(topic.get("topic"))}</p>'
                f'<a class="detail-link" href="topics/{esc(page_id)}.html">기사·프로필·참고글 상세 보기 →</a>'
                f'{render_celebrity_profile(topic)}{render_celebrity_keyword_ideas(topic)}'
                f'{render_celebrity_blog_references(topic)}</article>'
            )
    content = "".join(cards) or '<p class="empty">현재 연예인 정보 주제가 없습니다.</p>'
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>연예인 정보 브리핑</title><style>{CSS}</style></head><body><div class="wrap">
<header class="top"><h1>연예인 정보</h1>
<div class="date">{date_label(brief["date"])} · 현재 이슈 {total}개</div>
<nav class="nav"><a href="./">오늘의 브리핑</a><a href="keywords/">키워드 연구</a><a href="archive.html">날짜별 보관</a><a href="category.html">카테고리별</a><a href="celebrity.html">연예인 정보</a><a href="stats.html">통계</a><a href="tracker.html">작성 관리</a></nav></header>
<div class="checkbar"><strong data-check-summary>완료 0 / 전체 0</strong><span>프로필 확인과 블로그 참고글 조사가 끝난 주제를 체크하세요.</span><button type="button" data-reset-checks>이 페이지 체크 지우기</button></div>
<p class="method-note">프로필은 기사·공식 자료에 근거한 내용만 표시합니다. 네이버 블로그 참고글은 조회수 순위가 아니라 검색 정확도와 요약문 키워드 포함도 기준입니다.</p>
{"".join(cards) or '<p class="empty">현재 연예인 정보 주제가 없습니다.</p>'}
<footer>재산·MBTI·혈액형 등은 공식 공개 자료가 없으면 미공개·확인 필요로 표시합니다.</footer>
</div>{CHECK_SCRIPT}</body></html>"""


def render_stats_page(briefs, tracker_rows=None):
    tracker_map = {row.get("topic_id"): row for row in (tracker_rows or []) if row.get("topic_id")}
    category_stats = {}
    daily_stats = []
    total = written = published = 0

    for brief in briefs[-7:]:
        day_total = 0
        for category_key, category in brief.get("categories", {}).items():
            parent, subcategory = category_info(category_key, category)
            topics = list(category.get("topics", [])) + list(category.get("celeb_topics", []))
            stat = category_stats.setdefault(
                (parent, subcategory), {"topics": 0, "written": 0, "published": 0}
            )
            for topic in topics:
                day_total += 1
                total += 1
                topic_id = topic.get("topic_id") or topic_page_id(brief["date"], category_key, topic)
                row = tracker_map.get(topic_id, {})
                writing = str(row.get("작성 여부") or "").replace(" ", "")
                pub = str(row.get("발행 여부") or "").replace(" ", "")
                is_written = "작성완료" in writing
                is_published = "발행완료" in pub or bool(str(row.get("발행 URL") or "").strip())
                stat["topics"] += 1
                if is_written:
                    stat["written"] += 1
                    written += 1
                if is_published:
                    stat["published"] += 1
                    published += 1
        daily_stats.append((brief["date"], day_total))

    category_rows = "".join(
        f'<tr><td>{esc(parent)}</td><td>{esc(subcategory)}</td><td>{values["topics"]}</td>'
        f'<td>{values["written"]}</td><td>{values["published"]}</td></tr>'
        for (parent, subcategory), values in sorted(category_stats.items())
    )
    daily_rows = "".join(
        f'<tr><td><a href="{esc(date)}.html">{esc(date)}</a></td><td>{count}</td></tr>'
        for date, count in reversed(daily_stats)
    )
    period = (
        f'{briefs[max(0, len(briefs) - 7)]["date"]} ~ {briefs[-1]["date"]}'
        if briefs else "자료 없음"
    )
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>브리핑 통계</title><style>{CSS}</style></head><body><div class="wrap">
<header class="top"><h1>브리핑 통계</h1><div class="date">최근 7일 · {esc(period)}</div>
<nav class="nav"><a href="./">오늘의 브리핑</a><a href="keywords/">키워드 연구</a><a href="archive.html">날짜별 보관</a><a href="category.html">카테고리별</a><a href="celebrity.html">연예인 정보</a><a href="stats.html">통계</a><a href="tracker.html">작성 관리</a></nav></header>
<div class="stats-grid"><div class="stat-card"><strong>{total}</strong><span>최근 7일 주제</span></div>
<div class="stat-card"><strong>{written}</strong><span>작성 완료</span></div>
<div class="stat-card"><strong>{published}</strong><span>발행 완료</span></div>
<div class="stat-card"><strong>{len(category_stats)}</strong><span>세부 카테고리</span></div></div>
<section class="detail-section"><h2>세부 카테고리별</h2>
<table class="category-table"><thead><tr><th>대분류</th><th>세부 카테고리</th><th>주제</th><th>작성 완료</th><th>발행 완료</th></tr></thead>
<tbody>{category_rows or '<tr><td colspan="5">아직 통계가 없습니다.</td></tr>'}</tbody></table></section>
<section class="detail-section"><h2>날짜별 주제 수</h2>
<table class="category-table"><thead><tr><th>날짜</th><th>주제 수</th></tr></thead><tbody>
{daily_rows or '<tr><td colspan="2">아직 통계가 없습니다.</td></tr>'}</tbody></table></section>
</div></body></html>"""


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
<nav class="nav"><a href="./">최신 브리핑</a><a href="keywords/">키워드 연구</a><a href="archive.html">지난 브리핑</a><a href="category.html">카테고리별</a><a href="celebrity.html">연예인 정보</a><a href="stats.html">통계</a>
<a href="editorial_tracker.csv">CSV 내려받기</a></nav></header>
<table class="tracker"><thead><tr><th>날짜</th><th>카테고리</th><th>주제</th>
<th>작성 여부</th><th>발행 여부</th><th>발행 URL</th></tr></thead>
<tbody>{"".join(body) or '<tr><td colspan="6">아직 주제가 없습니다.</td></tr>'}</tbody></table>
</div></body></html>"""


def main():
    os.makedirs(DOCS, exist_ok=True)
    os.makedirs(TOPICS_DIR, exist_ok=True)
    os.makedirs(RUNS_DOCS_DIR, exist_ok=True)
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
        run_files = sorted(glob.glob(os.path.join(ROOT, "data", "runs", "brief-*.json")), reverse=True)
        runs = []
        for run_path in run_files:
            with open(run_path, encoding="utf-8") as run_file:
                run_brief = json.load(run_file)
            run_id = run_brief.get("run_id") or os.path.basename(run_path)[6:-5]
            runs.append((run_id, run_brief))
            with open(os.path.join(RUNS_DOCS_DIR, f"{run_id}.html"), "w", encoding="utf-8") as run_html:
                run_html.write(render_run_page(run_brief, run_id))
        f.write(render_archive(list(reversed(dates)), runs))

    tracker_path = os.path.join(ROOT, "data", "editorial_tracker.csv")
    tracker_rows = []
    if os.path.exists(tracker_path):
        with open(tracker_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        tracker_rows = rows
        with open(os.path.join(DOCS, "tracker.html"), "w", encoding="utf-8") as f:
            f.write(render_tracker(rows))

    with open(files[-1], encoding="utf-8") as f:
        latest_brief = json.load(f)
    with open(os.path.join(DOCS, "category.html"), "w", encoding="utf-8") as f:
        f.write(render_category_dashboard(latest_brief, tracker_rows))

    with open(os.path.join(DOCS, "celebrity.html"), "w", encoding="utf-8") as f:
        f.write(render_celebrity_dashboard(latest_brief))

    recent_briefs = []
    for path in files[-7:]:
        with open(path, encoding="utf-8") as f:
            recent_briefs.append(json.load(f))
    with open(os.path.join(DOCS, "stats.html"), "w", encoding="utf-8") as f:
        f.write(render_stats_page(recent_briefs, tracker_rows))

    with open(os.path.join(DOCS, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")
    print(f"사이트 생성 완료 - {len(dates)}일치, 최신 {dates[-1]}")


if __name__ == "__main__":
    main()
