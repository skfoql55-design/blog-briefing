"""
피드 점검 — 처음 한 번, 그리고 가끔 돌려보세요.
실패한 피드나 불완전한 네이버 키가 있으면 종료 코드 1을 반환합니다.
"""
import os
import sys

import feedparser
import requests
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (compatible; blog-briefing/1.0)"


def main():
    cfg = yaml.safe_load(open(os.path.join(ROOT, "sources.yaml"), encoding="utf-8"))
    dead = []

    for key, category in cfg["categories"].items():
        print(f"\n── {category['label']} ──")
        for url in category.get("rss", []):
            try:
                res = requests.get(url, timeout=15, headers={"User-Agent": UA})
                feed = feedparser.parse(res.content)
                count = len(feed.entries)
                if res.status_code == 200 and count:
                    print(f"  OK   {count:3d}건  {url}")
                else:
                    print(f"  DEAD ({res.status_code}, {count}건)  {url}")
                    dead.append(url)
            except Exception as exc:
                print(f"  DEAD ({type(exc).__name__})  {url}")
                dead.append(url)

    cid = os.getenv("NAVER_CLIENT_ID")
    secret = os.getenv("NAVER_CLIENT_SECRET")
    if bool(cid) != bool(secret):
        print("\n네이버 검색 API: Client ID와 Secret을 함께 설정해야 합니다.")
        dead.append("NAVER_API_CREDENTIALS")
    elif cid and secret:
        try:
            res = requests.get(
                "https://naverapihub.apigw.ntruss.com/search/v1/news",
                params={"query": "경제", "display": 1, "format": "json"},
                headers={"X-NCP-APIGW-API-KEY-ID": cid,
                         "X-NCP-APIGW-API-KEY": secret},
                timeout=15,
            )
            print(f"\n네이버 검색 API: {'OK' if res.status_code == 200 else 'FAIL ' + res.text[:200]}")
            if res.status_code != 200:
                dead.append("NAVER_API")
        except Exception as exc:
            print(f"\n네이버 검색 API: FAIL {type(exc).__name__}: {exc}")
            dead.append("NAVER_API")
    else:
        print("\n네이버 검색 API: 키 미설정 (RSS만 사용)")

    if dead:
        print(f"\n점검 실패 {len(dead)}개 — sources.yaml 또는 Secrets를 확인하세요:")
        for value in dead:
            print(f"  {value}")
        sys.exit(1)
    print("\n모든 출처 점검 완료")


if __name__ == "__main__":
    main()
