# 산단 뉴스 모니터

아래 키워드가 들어간 뉴스를 매일 자동으로 모아서 한 페이지에서 볼 수 있는 웹페이지입니다.

- 온산국가산단 / 온산국가산업단지
- 울산 사업장폐기물
- 여수국가산단 / 여수국가산업단지
- 여수 적량지구

## 동작 방식

1. **GitHub Actions**가 매일 한국시간 07시·12시·18시에 `scripts/fetch_news.py`를 실행합니다.
2. 스크립트가 Google 뉴스(필요하면 네이버 뉴스도)에서 키워드별 최근 기사를 가져와 `docs/news.json`에 누적 저장합니다. (중복 기사는 합치고, 90일 지난 기사는 정리)
3. **GitHub Pages**가 `docs/` 폴더를 웹페이지로 보여줍니다.

서버·DB·비용이 필요 없습니다.

## 처음 한 번만 설정하기

1. **GitHub Pages 켜기**
   저장소 → Settings → Pages → *Build and deployment* 에서
   Source: `Deploy from a branch`, Branch: `main` / 폴더: `/docs` 선택 후 Save.
   잠시 후 `https://<계정명>.github.io/newsmonitor/` 주소로 접속할 수 있습니다.
2. **Actions 쓰기 권한 확인**
   Settings → Actions → General → *Workflow permissions* 를 `Read and write permissions`로 설정.
3. **첫 수집 실행**
   Actions 탭 → `뉴스 수집` → `Run workflow` 버튼을 누르면 바로 수집됩니다. 이후로는 매일 자동입니다.

> 자동 실행(schedule)은 기본 브랜치(`main`)에 워크플로 파일이 있어야 동작합니다.

## (선택) 네이버 뉴스도 함께 수집하기

네이버 뉴스까지 포함하면 지역 언론 기사가 더 많이 잡히고 기사 요약도 표시됩니다.

1. [네이버 개발자센터](https://developers.naver.com/apps/#/register)에서 애플리케이션 등록 → 사용 API: **검색**
2. 발급받은 Client ID / Client Secret을 저장소 Settings → Secrets and variables → Actions 에
   `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 이름으로 등록

등록하지 않으면 Google 뉴스만 사용합니다.

## 키워드 바꾸기

`keywords.json`의 `keywords` 목록을 수정하면 됩니다. 띄어쓰기가 없는 키워드는 정확히 일치하는 기사를,
`울산 사업장폐기물`처럼 띄어쓴 키워드는 두 단어가 모두 들어간 기사를 찾습니다.

## 웹페이지 기능

- 키워드별 필터 (여러 개 동시 선택 가능), 기간(오늘/3일/7일/30일/전체), 제목·언론사 검색
- 지난 방문 이후 새로 수집된 기사에 **NEW** 표시
- 클릭한 기사는 읽음 처리 (흐리게 표시), "안 읽은 기사만" 보기
- 휴대폰 화면 지원, 다크 모드 지원

## 직접 실행해 보기

```bash
python3 scripts/fetch_news.py            # docs/news.json 갱신
cd docs && python3 -m http.server 8000   # http://localhost:8000 접속
```
