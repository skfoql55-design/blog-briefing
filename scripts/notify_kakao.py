"""
4단계 — 카카오톡 '나에게 보내기'
오늘 브리핑 안내문과 확인 링크를 카톡으로 보낸다.

핵심 주의점 (카카오 API 특성):
- 텍스트 템플릿 본문은 200자 제한 → 짧은 안내문 1통만 보낸다
- access token 6시간 / refresh token 2개월
- refresh token 은 남은 기간이 30일 이하일 때만 응답에 새로 내려온다.
  무조건 덮어쓰면 토큰을 잃으므로 '있을 때만' 갱신한다.
"""
import os, sys, json, datetime as dt, time
import requests

KST = dt.timezone(dt.timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
LIMIT = 195  # 200자 제한, 여유 5자


def refresh_access_token():
    """refresh token 으로 access token 을 새로 받는다."""
    token_data = {
        "grant_type": "refresh_token",
        "client_id": os.environ["KAKAO_REST_API_KEY"],
        "refresh_token": os.environ["KAKAO_REFRESH_TOKEN"],
    }
    client_secret = os.getenv("KAKAO_CLIENT_SECRET", "").strip()
    if client_secret:
        token_data["client_secret"] = client_secret
    res = requests.post(TOKEN_URL, timeout=15, data=token_data)
    res.raise_for_status()
    body = res.json()

    new_refresh = body.get("refresh_token")
    if new_refresh:
        # 토큰 값은 로그나 요약에 남기지 않는다. 사용자가 로컬에서 갱신해야 한다.
        print("새 refresh token 이 발급되었습니다. GitHub Secret 교체가 필요합니다.")
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a") as f:
                f.write("## 카카오 refresh token 갱신 필요\n\n"
                        "`KAKAO_REFRESH_TOKEN` Secret 을 로컬에서 새 값으로 교체하세요. "
                        "토큰 값은 로그에 출력하지 않았습니다.\n")
    return body["access_token"]


def send_text(access_token, text, link_url, button_title="브리핑 열기"):
    if len(text) > LIMIT:
        suffix = f"\n{link_url}"
        available = max(20, LIMIT - len(suffix) - 2)
        text = text[:available] + "…" + suffix
    template = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": link_url, "mobile_web_url": link_url},
        "button_title": button_title,
    }
    for attempt in range(3):
        try:
            res = requests.post(
                SEND_URL, timeout=15,
                headers={"Authorization": f"Bearer {access_token}",
                         "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
                data={"template_object": json.dumps(template, ensure_ascii=False)},
            )
            try:
                ok = res.status_code == 200 and res.json().get("result_code") == 0
            except ValueError:
                ok = False
            if ok:
                print("  보냄")
                return True
            retryable = res.status_code == 429 or res.status_code >= 500
            if retryable and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            print(f"  실패 {res.status_code} {res.text[:200]}")
            return False
        except requests.RequestException as exc:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            print(f"  실패 {type(exc).__name__}: {exc}")
            return False
    return False


def main():
    site = os.environ["SITE_URL"].rstrip("/")
    date = dt.datetime.now(KST).strftime("%Y-%m-%d")
    path = os.path.join(ROOT, "data", f"brief-{date}.json")
    if not os.path.exists(path):
        print("오늘 브리핑이 없습니다.")
        sys.exit(1)
    brief = json.load(open(path, encoding="utf-8"))
    day_url = f"{site}/{date}.html"

    token = refresh_access_token()
    candidates = []
    for category in brief.get("categories", {}).values():
        for topic in list(category.get("topics", [])) + list(category.get("celeb_topics", [])):
            interest = topic.get("interest") or {}
            try:
                score = float(interest.get("score") or 0)
            except (TypeError, ValueError):
                score = 0
            candidates.append((score, topic.get("topic", "")))
    candidates.sort(key=lambda item: item[0], reverse=True)
    top_topics = [title for _, title in candidates if title][:3]
    if top_topics:
        lines = ["오늘의 브리핑 소식 보내드립니다.", "", "관심도 상위 주제"]
        lines.extend(f"{index}. {title[:30]}" for index, title in enumerate(top_topics, 1))
        lines.extend(["", "아래 링크에서 자세히 확인해주세요.", day_url])
        message = "\n".join(lines)
    else:
        message = (
            "오늘의 브리핑 소식 보내드립니다.\n\n"
            "아래 링크에서 확인해주세요.\n"
            f"{day_url}"
        )
    news_ok = send_text(token, message, day_url, "뉴스 브리핑 열기")

    keyword_url = f"{site}/keywords/"
    keyword_message = (
        "오늘의 키워드 연구 보고서입니다.\n\n"
        "검색량·검색 추이·경쟁도·추천 글감을 확인하세요.\n"
        f"{keyword_url}"
    )
    keyword_ok = send_text(token, keyword_message, keyword_url, "키워드 보고서 열기")

    if not (news_ok and keyword_ok):
        print("카카오톡 뉴스 브리핑 또는 키워드 연구 보고서 중 하나 이상 전송되지 않았습니다.")
        sys.exit(1)


if __name__ == "__main__":
    main()
