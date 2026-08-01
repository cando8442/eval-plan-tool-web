# dorms-check 점검 리포트

- 앱: 평가계획서 자동생성 도구
- 주소: https://eval-plan-tool.onrender.com 
- 스택: Unknown / 범용
- 점검 트랙: security, edzip

> 이 리포트는 dorms-check(코치)의 자체 점검 결과입니다. 최종 인증마크는 도름스 서버가 스스로 다시 검증해 발급하며, 이 리포트의 통과가 마크를 보장하지 않습니다.

## 보안 검토
- 점수: 100/100 (A+)
- 마크 자격(critical/high 0): 충족

### 통과 항목(증빙)
- [v] Content-Security-Policy — 헤더값: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'
- [v] Strict-Transport-Security — 헤더값: max-age=63072000; includeSubDomains
- [v] 클릭재킹 방어(X-Frame-Options / frame-ancestors) — 헤더값: DENY
- [v] X-Content-Type-Options: nosniff — 헤더값: nosniff
- [v] Referrer-Policy — 헤더값: strict-origin-when-cross-origin
- [v] Permissions-Policy — 헤더값: camera=(), microphone=(), geolocation=()
- [v] 서버/프레임워크 버전 노출 — x-powered-by 미노출(양호)
- [v] HTTPS 강제(HTTP→HTTPS 리다이렉트) — HTTP 요청이 HTTPS로 리다이렉트됨 (HTTP 301 -> https://eval-plan-tool.onrender.com/)
- [v] SSL 인증서 유효 — TLS 연결 성공 (TLSv1.3)
- [v] 구버전 TLS 미사용 — TLS 버전 양호: TLSv1.3
- [v] 민감 파일 노출(.env/.git) — 민감 파일(.env/.git) 노출 없음
- [v] 설정 파일 노출 — 설정 파일 비노출
- [v] 소스맵 노출 — 소스맵 참조 없음
- [v] 에러 스택트레이스 노출 — 스택트레이스 노출 없음
- [v] Mixed Content — mixed content 없음
- [v] CORS 설정 — CORS가 임의 Origin을 허용하지 않음(양호)
- [v] 페이지 제목 — <title> 있음
- [v] 설명 메타 — 설명 메타
- [v] 모바일 viewport — viewport 메타
- [v] Open Graph — Open Graph 태그
- [v] 응답 속도 — 응답 시간 247ms
- [v] 문서 크기 — 문서 크기 12KB
- [v] 압축 — 압축: br
- [v] 개인정보처리방침 — 개인정보처리방침 발견(link: /privacy)
- [v] 연락처 — 연락처/문의 정보 있음
- [v] 미인증 API 접근 — 미인증 호출로 데이터를 반환하는 API 후보 없음
- [v] 클라이언트 시크릿 노출 — 클라 시크릿 노출 미검출
- [v] 헤더 설정 위치 — app.py의 set_security_headers()(@app.after_request, 25~40행 부근)에서 Content-Security-Policy/Strict-Transport-Security/X-Frame-Options/X-Content-Type-Options/Referrer-Policy/Permissions-Policy 6종을 모든 응답에 설정. 재배포 후 실측(curl -sI https://eval-plan-tool.onrender.com/)으로 두 헤더 값이 코드와 일치함을 확인, rescan 결과 sec.header.* 전부 pass로 전환됨(보안 100/100).
- [v] 위험 코드 패턴(검토 후보) — .venv\Lib\site-packages\werkzeug\debug\shared\debugger.js:157, .venv\Lib\site-packages\werkzeug\debug\shared\debugger.js:219, .venv\Lib\site-packages\werkzeug\debug\shared\debugger.js:225 외 20건

### 참고(검토 권장, 마크 게이트 아님)
- canonical: canonical 링크
- 이용약관: 이용약관 페이지/링크 없음

## 학운위 심사 준비(에듀집 필수기준)
- 준비 상태: 충족(제출 서류 준비됨)
- 개인정보처리방침 공개: 있음

> "학운위 심사 준비 완료"는 학교 심의에 낼 서류가 갖춰졌다는 뜻이며, 심의 통과를 보장하지 않습니다. 심의와 최종 결정은 각 학교가 합니다.
