"""
작성 관리표 생성

날짜별 brief JSON을 Excel/Google Sheets에서 열 수 있는 CSV로 합친다.
사용자가 수정한 작성·발행 상태와 메모는 topic_id가 같은 동안 보존한다.
"""
import csv
import glob
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")

HEADERS = [
    "topic_id", "날짜", "카테고리", "구분", "주제", "선정 근거",
    "기사1 제목", "기사1 URL", "기사1 출처", "기사1 도메인",
    "기사2 제목", "기사2 URL", "기사2 출처", "기사2 도메인",
    "기사3 제목", "기사3 URL", "기사3 출처", "기사3 도메인",
    "작성 여부", "발행 여부", "작성일", "발행일", "발행 URL", "메모",
]
EDITABLE = ["작성 여부", "발행 여부", "작성일", "발행일", "발행 URL", "메모"]


def fallback_topic_id(date, category, topic, articles):
    value = "|".join([
        date,
        category,
        topic,
        *sorted(str(a.get("link", "")) for a in articles),
    ])
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def article_value(article, key):
    if not article:
        return ""
    return article.get(key, "") or ""


def row_from_topic(date, category, section, topic):
    articles = topic.get("articles", [])[:3]
    row = {header: "" for header in HEADERS}
    row.update({
        "topic_id": topic.get("topic_id") or fallback_topic_id(
            date, category, topic.get("topic", ""), articles
        ),
        "날짜": date,
        "카테고리": category,
        "구분": section,
        "주제": topic.get("topic", ""),
        "선정 근거": topic.get("basis", ""),
        "작성 여부": "미작성",
        "발행 여부": "미발행",
    })
    for index in range(3):
        article = articles[index] if index < len(articles) else {}
        number = index + 1
        row[f"기사{number} 제목"] = article_value(article, "title")
        row[f"기사{number} URL"] = article_value(article, "link")
        row[f"기사{number} 출처"] = article_value(article, "source")
        row[f"기사{number} 도메인"] = article_value(article, "domain")
    return row


def read_existing(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {row.get("topic_id"): row for row in csv.DictReader(f) if row.get("topic_id")}


def main():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(DOCS, exist_ok=True)
    tracker_path = os.path.join(DATA, "editorial_tracker.csv")
    existing = read_existing(tracker_path)
    rows = []

    for path in sorted(glob.glob(os.path.join(DATA, "brief-*.json"))):
        with open(path, encoding="utf-8") as f:
            brief = json.load(f)
        date = brief["date"]
        for category, block in brief.get("categories", {}).items():
            label = block.get("label", category)
            for topic in block.get("topics", []):
                rows.append(row_from_topic(date, label, "일반", topic))
            for topic in block.get("celeb_topics", []):
                rows.append(row_from_topic(date, label, "연예인 건강", topic))

    rows.sort(key=lambda row: (row["날짜"], row["카테고리"], row["구분"], row["주제"]), reverse=True)
    for row in rows:
        old = existing.get(row["topic_id"], {})
        for field in EDITABLE:
            if old.get(field):
                row[field] = old[field]

    for path in (tracker_path, os.path.join(DOCS, "editorial_tracker.csv")):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(rows)

    print(f"작성 관리표 생성 완료 - {len(rows)}개 주제")


if __name__ == "__main__":
    main()
