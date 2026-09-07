"""
4단계 — 카카오톡 '나에게 보내기'
오늘 브리핑 링크와 주제 미리보기를 카톡으로 보낸다.

핵심 주의점 (카카오 API 특성):
- 텍스트 템플릿 본문은 200자 제한 → 카테고리별로 나눠 보낸다
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


def send_text(access_token, text, link_url):
    if len(text) > LIMIT:
        text = text[: LIMIT - 1] + "…"
    template = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": link_url, "mobile_web_url": link_url},
        "button_title": "브리핑 열기",
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
    d = dt.datetime.strptime(date, "%Y-%m-%d")
    head = f'{d.month}월 {d.day}일 브리핑이 준비됐어요.\n'

    # 1통: 전체 요약
    counts = " / ".join(f'{c["label"]} {len(c["topics"])}'
                        for c in brief["categories"].values())
    all_ok = send_text(token, head + f"오늘 주제 {counts}\n아래 버튼으로 전체 보기", day_url)

    # 2통~: 카테고리별 주제 목록
    for cat in brief["categories"].values():
        if not cat["topics"]:
            continue
        lines = [f'[{cat["label"]}]']
        for i, t in enumerate(cat["topics"], 1):
            lines.append(f'{i}. {t["topic"]}')
        if cat.get("celeb_topics"):
            lines.append(f'+ 연예인 이슈 {len(cat["celeb_topics"])}건')
        all_ok = send_text(token, "\n".join(lines), day_url) and all_ok

    if not all_ok:
        print("카카오톡 메시지 중 하나 이상 전송되지 않았습니다.")
        sys.exit(1)


if __name__ == "__main__":
    main()
