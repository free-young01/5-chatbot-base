# 더뉴빌리지로 오세요 — 구현·협업

> 분류: 팀 신규 · 독자: 두 개발자와 구현 AI 에이전트 · 실행 중 대화 모델의 입력: 아님. [문서 지도](README.md)

[스토리](STORY.md)와 [API 계약](API_CONTRACT.md)을 공동 기준으로 삼는다. 첫 공개 시연에서 세 엔딩까지 도달한다. 자유 대사는 AI가 생성하고 장소 이동, 조사, 호감도 검사, 차 키와 결말은 서버가 결정한다.

## 두 개발자의 파일 경계

| 담당 | 작업 | 소유 파일 |
| --- | --- | --- |
| 팀장 (`suyoung` 브랜치) | 장면·호감도·엔딩, 공개 사실 검색, AI 대사, 토큰과 API | `app.py`, `services/story.py`, `services/state_token.py`, `services/chatbot_service.py`, `services/generator.py`, `services/retriever.py`, `config/`, `data/knowledge/`, 서버 테스트 |
| 팀원 (`yejoon` 브랜치) | 장소·인물·채팅·발견 기록 화면, 이미지 자산과 선택 | `templates/`, `public/assets/`, `services/image_selector.py`, `data/images/`, 화면 테스트 |

`requirements.txt`, `README.md`, `AGENTS.md`, `docs/`는 공유 영역이다. 인터페이스를 바꿀 때 두 사람이 [API 계약](API_CONTRACT.md)을 먼저 갱신한다. 화면 담당자는 계약의 예시 응답으로 화면을 먼저 검증할 수 있다.

## 브랜치와 순서

원본에서 fork한 팀장 소유 저장소를 기준으로 한다. 두 사람은 `git remote -v`로 자신의 `origin`을 확인한다. 팀장은 `suyoung`에서 서버·스토리를, 팀원은 `yejoon`에서 화면·이미지를 구현한다. 각각 `main` 대상의 작은 PR을 올리면 팀장이 검토한 뒤 병합한다. AI 에이전트에도 브랜치별 파일 경계, 스토리와 API 계약을 전달한다.

1. 계약·스토리·에이전트 지침을 기준 브랜치에 반영한다.
2. 서버와 화면을 파일 경계대로 구현한다. 첫 통합 구현은 `main`에 포함되었고, 이후 변경부터 `suyoung`과 `yejoon`의 경계를 적용한다.
3. 이름 입력부터 세 결말까지, 정보 제한, 중복 점수, 잘못된 토큰, 모델 실패와 화면 복원을 검증한다.
4. PR 검토·병합 뒤 Render에 배포하고 공개 URL에서 모바일과 새로고침을 재검증한다.

로컬 환경은 `conda activate chatbot-base`로 활성화한다. Ponytail은 선택적 보조 도구이며 프로젝트 계약과 검증 기준이 우선이다. 비밀 값은 `.env`와 Render 환경 변수에만 둔다.
