"""
카카오 refresh token 최초 1회 발급용 — 내 컴퓨터에서 한 번만 실행합니다.

준비 (카카오 디벨로퍼스 developers.kakao.com):
  1) 애플리케이션 추가하기
  2) 앱 설정 > 플랫폼 > Web 에 사이트 도메인 등록
     예: https://<깃허브아이디>.github.io
  3) 카카오 로그인 > 활성화 ON
  4) 카카오 로그인 > Redirect URI 에 http://localhost:8080 등록
  5) 카카오 로그인 > 동의항목 > '카카오톡 메시지 전송(talk_message)' 을
     선택 동의 또는 이용 중 동의로 설정
  6) 앱 > 플랫폼 키 > REST API 키에서 REST API 키와 클라이언트 시크릿을 확인

실행:  python scripts/get_kakao_token.py <REST_API_키> [클라이언트_시크릿]

클라이언트 시크릿이 켜져 있으면 두 번째 인자로 반드시 넣어야 합니다.
"""
import os, sys, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import requests

REDIRECT = "http://localhost:8080"
code_box = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        code_box["code"] = q.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h2>인증 완료. 터미널로 돌아가세요.</h2>".encode())

    def log_message(self, *a):
        pass


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    key = sys.argv[1]
    client_secret = (sys.argv[2] if len(sys.argv) >= 3
                     else os.getenv("KAKAO_CLIENT_SECRET", "").strip())

    url = ("https://kauth.kakao.com/oauth/authorize"
           f"?client_id={key}&redirect_uri={REDIRECT}"
           "&response_type=code&scope=talk_message")
    print("브라우저에서 카카오 로그인 후 동의해주세요.\n" + url)
    webbrowser.open(url)

    server = HTTPServer(("localhost", 8080), Handler)
    server.handle_request()

    if not code_box.get("code"):
        print("인증 코드를 받지 못했습니다.")
        sys.exit(1)

    token_data = {
        "grant_type": "authorization_code", "client_id": key,
        "redirect_uri": REDIRECT, "code": code_box["code"],
    }
    if client_secret:
        token_data["client_secret"] = client_secret
    res = requests.post("https://kauth.kakao.com/oauth/token", timeout=15,
                        data=token_data)
    body = res.json()
    if "refresh_token" not in body:
        print("발급 실패:", body)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("아래 두 값을 GitHub Secrets 에 넣으세요.\n")
    print("KAKAO_REST_API_KEY  =", key)
    print("KAKAO_REFRESH_TOKEN =", body["refresh_token"])
    print("=" * 60)


if __name__ == "__main__":
    main()
