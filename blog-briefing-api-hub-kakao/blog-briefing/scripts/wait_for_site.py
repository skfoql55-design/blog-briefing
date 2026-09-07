"""GitHub Pages에 오늘 브리핑이 반영될 때까지 짧게 확인한다."""
import datetime as dt
import os
import sys
import time

import requests

KST = dt.timezone(dt.timedelta(hours=9))


def main():
    site = os.environ.get("SITE_URL", "").rstrip("/")
    if not site:
        print("SITE_URL이 없어 Pages 반영 확인을 건너뜁니다.")
        return
    date = dt.datetime.now(KST).strftime("%Y-%m-%d")
    url = f"{site}/{date}.html"
    for attempt in range(24):
        try:
            res = requests.get(
                url,
                timeout=15,
                headers={"Cache-Control": "no-cache", "User-Agent": "blog-briefing/1.0"},
            )
            if res.status_code == 200 and f'name="briefing-date" content="{date}"' in res.text:
                print(f"Pages 반영 확인: {url}")
                return
            print(f"  Pages 대기 {attempt + 1}/24 — HTTP {res.status_code}")
        except requests.RequestException as exc:
            print(f"  Pages 대기 {attempt + 1}/24 — {type(exc).__name__}: {exc}")
        time.sleep(10)
    print("Pages에 오늘 브리핑이 반영되지 않았습니다.")
    sys.exit(1)


if __name__ == "__main__":
    main()
