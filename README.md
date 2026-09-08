# 블로그 브리핑 봇

매일 아침 7시, 경제·건강·카테크·방송연예·스포츠 블로그용 오늘의 주제와 키워드 연구 보고서를 만들고
카카오톡으로 각각 링크를 보내줍니다.

```
06:50  GitHub Actions 시작
       ├ RSS + NAVER API HUB 뉴스 검색으로 분야별 최신 기사 수집
       ├ GLM-5.3-Flash 로 같은 사건끼리 묶고 주제·근거 생성
       │  └ 주제 1개당 서로 다른 관련 기사 3개, 서로 다른 3개 출처 확인
       ├ 이미 쓴 글(past_titles.txt)과 겹치는 주제 제외
       ├ 날짜별 브리핑 페이지와 실행별 보관 기록·작성 관리표 생성 → GitHub Pages 배포
       ├ 날짜별 키워드 연구 보고서와 1,000개 키워드 체크 화면 생성
       └ 카카오톡 '나에게 보내기' 로 뉴스 브리핑·키워드 보고서 링크 2통 발송
07:00  카톡 도착
```

---

## 세팅 (한 번만)

### 1. 저장소 만들기

이 폴더를 GitHub 새 저장소에 올립니다. **Private 로 만드세요** (Secrets 보호).

```bash
git init && git add . && git commit -m "init"
git branch -M main
git remote add origin https://github.com/<아이디>/blog-briefing.git
git push -u origin main
```

### 2. GitHub Pages 켜기

저장소 → **Settings → Pages**
- Source: `Deploy from a branch`
- Branch: `main` / 폴더: `/docs` → Save

주소가 `https://<아이디>.github.io/blog-briefing/` 로 나옵니다. 이 주소를 적어두세요.

> Private 저장소의 Pages 는 유료 플랜에서만 공개됩니다.
> 무료 플랜이면 저장소를 Public 으로 두되, 민감한 값은 전부 Secrets 에 있으니 코드는 공개돼도 괜찮습니다.

### 3. 피드 점검

```bash
pip install -r requirements.txt
python scripts/verify_sources.py
```

`DEAD` 로 나오는 주소는 `sources.yaml` 에서 지우거나 고칩니다.
언론사 RSS 주소는 종종 바뀌니 처음에 꼭 한 번 돌려보세요.

### 4. NAVER API HUB 키 (선택)

검색 API는 네이버 개발자센터에서 NAVER API HUB로 이관되었습니다.

[NAVER Cloud Console](https://console.ncloud.com) → `All Services` →
`Application Services` → `NAVER API HUB` → 서비스 이용 신청 → `Application` →
`Application 등록`에서 **NAVER 검색 → 뉴스**, **NAVER 검색 → 블로그**, **검색어트렌드**, **쇼핑인사이트**를 선택합니다.

Application 이름은 영문·숫자·하이픈만 사용할 수 있으므로
`blog-briefing-bot`을 권장합니다. 등록 후 `인증 정보`에서 Client ID와 Client Secret을
복사합니다. 이 프로젝트에서는 API HUB 키를 아래 이름으로 저장합니다.

```text
NAVER_CLIENT_ID       # API HUB Client ID
NAVER_CLIENT_SECRET   # API HUB Client Secret
```

뉴스 API가 없어도 RSS만으로 일부 동작하지만, 최신 검색 결과·관심도 순위·네이버 블로그 제목 유사도·쇼핑 관심 키워드까지 사용하려면
네 서비스를 모두 선택하는 것이 좋습니다. 네 서비스는 같은 API HUB Client ID/Secret을 사용합니다.
자세한 이관 절차는 [NAVER API HUB 이관 가이드](https://guide.ncloud-docs.com/docs/apihub-migration)를 참고하세요.

### 5. OpenRouter 키

[openrouter.ai](https://openrouter.ai) 가입 → Keys 에서 발급 → Credits 에 $5 충전.
하루 15개 주제 기준 월 $1 이 안 됩니다.

### 6. 카카오톡 토큰

[developers.kakao.com](https://developers.kakao.com) 에서:

1. **애플리케이션 추가하기**
2. **앱 설정 → 플랫폼 → Web** 에 2번에서 받은 Pages 주소 등록
3. **카카오 로그인 → 활성화 ON**
4. **카카오 로그인 → Redirect URI** 에 `http://localhost:8080` 등록
5. **카카오 로그인 → 동의항목** 에서 `카카오톡 메시지 전송(talk_message)` 을
   **선택 동의** 또는 **이용 중 동의** 로 설정 (필수 동의는 선택 불가)
6. **앱 → 플랫폼 키 → REST API 키**에서 REST API 키와 클라이언트 시크릿 확인

그 다음 내 컴퓨터에서 한 번 실행:

```bash
python scripts/get_kakao_token.py <REST_API_키> <클라이언트_시크릿>
```

브라우저가 열리면 카카오 로그인 후 동의 → 터미널에 `KAKAO_REFRESH_TOKEN` 이 출력됩니다.

### 7. Secrets 등록

저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| 이름 | 값 |
|---|---|
| `OPENROUTER_API_KEY` | `sk-or-v1-...` |
| `KAKAO_REST_API_KEY` | 카카오 REST API 키 |
| `KAKAO_CLIENT_SECRET` | 카카오 REST API 키의 클라이언트 시크릿 |
| `KAKAO_REFRESH_TOKEN` | 6번에서 받은 값 |
| `SITE_URL` | `https://<아이디>.github.io/blog-briefing` |
| `NAVER_CLIENT_ID` | (선택) |
| `NAVER_CLIENT_SECRET` | (선택) |
| `NAVER_SEARCHAD_ACCESS_LICENSE` | 네이버 검색광고 API 엑세스라이선스 (선택) |
| `NAVER_SEARCHAD_SECRET_KEY` | 네이버 검색광고 API 비밀키 (선택) |
| `NAVER_SEARCHAD_CUSTOMER_ID` | 네이버 광고계정 고객 ID (선택) |

### 8. 테스트 실행

**Actions 탭 → 매일 블로그 브리핑 → Run workflow** 로 즉시 한 번 돌려봅니다.
카톡이 오면 성공입니다.

---

## 매일 하는 일

카톡이 오면 링크를 열고, 마음에 드는 주제를 골라 Claude Code 에서 글을 씁니다.

**글을 발행한 뒤 `past_titles.txt` 에 제목을 한 줄씩 추가하세요.**
이게 다음날 중복 주제를 걸러내는 유일한 근거입니다. 이 파일만 관리하면 됩니다.

### 작성 여부 관리

`data/editorial_tracker.csv`가 매일 자동으로 갱신됩니다. Excel이나 Google Sheets에서 열어
다음 열을 수정하면 됩니다.

처음 사용할 때는 저장소의 `editorial_tracker_template.xlsx`를 참고하거나,
`data/editorial_tracker.csv`를 Excel에서 바로 열어도 됩니다. 자동 실행이 상태를 보존하는
기준 파일은 CSV입니다.

- `작성 여부`: `미작성` / `작성중` / `작성완료`
- `발행 여부`: `미발행` / `발행완료`
- `작성일`, `발행일`, `발행 URL`, `메모`

작성 관리 화면은 사이트의 `작성 관리` 메뉴에서 볼 수 있고,
`docs/editorial_tracker.csv`를 내려받을 수도 있습니다. 상태를 수정한 뒤 저장소에 커밋하면
다음 자동 실행에서도 상태와 메모가 유지됩니다.

날짜별 브리핑은 `지난 브리핑` 메뉴에서 확인할 수 있습니다. 같은 날짜에 다시 실행한 결과도
`실행 기록`에서 실행 시각별로 확인할 수 있습니다. 날짜별 브리핑의 `상세 조사 정리`를 누르면 주제별 랜딩페이지가 열립니다.
`카테고리별` 메뉴에서는 대분류·세부 카테고리·콘텐츠 유형·주제·작성/발행 상태를 한 화면에서 확인하고,
주제별 상세 조사 페이지로 바로 이동할 수 있습니다.
`연예인 정보` 메뉴에서는 현재 연예인 건강 이슈와 프로필 확인 상태, 네이버 블로그 참고글 3개를 별도로 모아 보여줍니다.
참고글은 조회수 순위가 아니라 검색 정확도와 검색 결과 요약문 키워드 포함도 기준이며, 각 글의 원문 주소를 제공합니다.
`통계` 메뉴에서는 최근 7일 주제 수와 세부 카테고리별 작성·발행 진행률을 확인할 수 있습니다.
`키워드 연구` 메뉴에서는 첨부된 네이버 키워드 연구 파일을 기준으로 TOP30, 카테고리별 요약,
전체 키워드 1,000개, 대체·확장 검색어, 키워드별 완료 체크를 확인할 수 있습니다. 날짜별 보고서는
`키워드 날짜별 보기`에서 열고, CSV와 원본 XLSX도 내려받을 수 있습니다. 현재는 첨부 파일의 조회 기준일을
그대로 보존하는 방식이며, 검색광고 API Secret 3개를 등록하면 월간 검색량과 경쟁도를 자동 갱신합니다.
검색광고 API는 엑세스라이선스·비밀키뿐 아니라 광고계정 고객 ID도 필요합니다. API로 갱신되는 값과
원본 연구 파일에서 계산된 기회점수·발행 우선점수는 보고서에서 구분해 표시합니다.
발행 완료로 표시된 주제는 다음 실행부터 중복 주제 선정에서 자동 제외됩니다.
랜딩페이지에는 핵심 팩트, 작성 전 확인사항, 독자용 체크리스트, 기사 3개 요지,
글 구성안, TOP N 적합성 판단, 홈판 제목 30개, 네이버 블로그 제목 유사도 조사와 검색 키워드가 들어갑니다. 확인되지 않은 대상·수치·일정은
랜딩페이지의 작성 전 확인 영역에서 원문 확인 대상으로 표시합니다.

주제는 카테고리 안에서 관심도 높은 순으로 표시됩니다. 검색어트렌드 API가 연결되면 최근 7일의
네이버 검색어 상대지수로 정렬하고, 쇼핑인사이트가 설정된 카테고리는 관련 키워드의 최근 클릭 관심도와 변화량을 일부 반영합니다.
두 값이 연결되지 않으면 기사 최신성·출처 확산을 이용한 추정 순위로 표시합니다.
카테고리 상단에는 검색어트렌드 기본 키워드의 최근 관심도도 함께 표시합니다. 상대지수는 절대 검색량이나 조회수를 뜻하지 않습니다.
쇼핑인사이트 값도 요청 기간의 상대지수이며 판매량·매출·절대 인기 순위가 아닙니다. 현재는 생활/건강, 디지털/가전, 화장품/미용 분야의 대표 키워드를 비교합니다.

### 크리에이터 어드바이저 검색어 반영

크리에이터 어드바이저의 `트렌드 → 주제별 인기 유입 검색어`에서 확인한 키워드는
`data/creator_advisor_keywords.csv`에 한 줄씩 입력할 수 있습니다. `카테고리키`에는
`health_current`, `broadcast`, `sports`처럼 `sources.yaml`의 카테고리 키를 넣습니다.
다음 실행부터 해당 키워드가 네이버 뉴스 수집과 검색어트렌드 참고값에 함께 반영됩니다.

```csv
날짜,카테고리키,키워드,순위,변동,메모
2026-09-07,health_current,연예인 이름 건강,1,▲2,인기 유입 검색어
```

크리에이터 어드바이저는 내 채널의 유입·트렌드 분석 서비스이므로, 이 파일은 사용자가 직접 확인한 값을 옮겨 적는 방식입니다.

홈판 제목 생성 규칙은 `prompts/home_title_prompt.txt`에 있습니다. 원하는 제목 생성 프롬프트를
이 파일 내용으로 교체하면 다음 실행부터 30개 제목 생성에 반영됩니다. 제목마다 뉴스·변경형, 궁금형 등 프레임과
근거 기사 번호를 함께 저장하며, 제목 선택 후 `선택 제목 복사`를 누를 수 있습니다.
네이버 블로그 유사도는 NAVER API HUB 블로그 검색 상위 결과의 제목과 비교한 참고용 추정치이며,
표절 여부나 실제 검색 노출 순위를 확정하는 기능은 아닙니다.

기본으로 다음 세부 카테고리에서 각각 5개 주제를 만듭니다.

- 경제: 한국 주식 5개, 미국 주식 5개, 재테크 5개, 한국 정책 이슈 5개, 부동산 5개
- 건강: 최신 이슈 5개, 생활 건강 정보 5개, 연예인 건강 3개
- 리빙: 생활 꿀팁 5개
- 카테크: 자동차 5개, 컴퓨터·IT 5개
- 고생물 5개, 방송연예 5개, 스포츠 5개, 패션뷰티 5개

각 주제에는 서로 다른 관련 기사 3개와 서로 다른 출처 3개를 연결합니다.
브리핑 페이지의 `완료 표시`를 누르면 해당 주제가 완료 상태로 보이고, 같은 브라우저의 저장공간에 남습니다.
브라우저나 저장공간을 바꾸면 체크 상태도 바뀌므로, 장기 관리 상태는 `editorial_tracker.csv`의
`작성 여부`와 `발행 여부`에 함께 기록하세요.
기사 3개와 서로 다른 3개 출처를 확보하지 못한 주제는 억지로 채우지 않고 제외합니다.

---

## 손보고 싶을 때

| 하고 싶은 것 | 고칠 곳 |
|---|---|
| 언론사 추가·교체 | `sources.yaml` → `rss` |
| 검색 키워드 변경 | `sources.yaml` → `naver_queries` |
| 하루 주제 개수 | `sources.yaml` → `topics_per_category` |
| 카테고리별 주제 개수 | `sources.yaml` → 각 카테고리의 `topics_per_category` |
| 한 주제당 기사 수 | `sources.yaml` → `articles_per_topic` |
| 며칠치를 최신으로 볼지 | `sources.yaml` → 기본 또는 카테고리별 `freshness_hours` |
| 연예인 이슈 키워드 | `sources.yaml` → `health_current.celeb.naver_queries` |
| 쇼핑인사이트 분야·키워드 | `sources.yaml` → 각 카테고리의 `shopping_insight` |
| 발송 시각 | `.github/workflows/daily.yml` → `cron` (UTC 기준, KST −9시간) |
| 주제 뽑는 기준·말투 | `scripts/process.py` → `PROMPT` |
| 홈판 제목 생성 규칙 | `prompts/home_title_prompt.txt` |
| 사이트 디자인 | `scripts/build_site.py` → `CSS` |

## 주의할 점

- **카카오 refresh token 은 2개월짜리**입니다. 매일 돌면 자동 갱신되지만,
  만료 30일 미만이 되면 새 토큰이 발급됩니다. 그때 Actions 로그와 실행 요약에
  "refresh token 갱신 필요" 가 뜨니 `KAKAO_REFRESH_TOKEN` Secret 을 교체하세요.
- 카카오 나에게 보내기는 **하루 100통** 한도입니다. 현재 이 봇은 안내문과 링크를 하루 1통 보냅니다.
- 홈판 제목 30개를 생성하므로 기존보다 LLM 응답량이 늘어납니다. 비용과 생성 시간을 줄이려면
  `prompts/home_title_prompt.txt`에서 불필요한 출력 요구를 줄이세요.
- GitHub Actions 크론은 부하에 따라 **몇 분 늦을 수 있습니다.**
- 주제는 카테고리당 5개를 목표로 하되, 중복 제외 후 기사가 모자라면 5개가 안 될 수 있습니다.
  그런 날은 Actions 로그에 `주제가 N개뿐입니다` 가 찍히니 `sources.yaml` 에 피드나 키워드를 보강하세요.
- 한 주제의 기사 3개는 URL과 출처 도메인이 모두 달라야 합니다.
- RSS 요약문과 제목을 근거로 주제를 만들므로, 실제 글 작성 전에는 반드시 원문 3개를 직접 확인하세요.
- 2주 이상 저장소에 활동이 없으면 GitHub 이 스케줄을 자동 중단합니다.
  브리핑이 매일 커밋을 남기므로 실제로는 문제되지 않습니다.
