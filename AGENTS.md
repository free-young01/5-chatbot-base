# 더뉴빌리지로 오세요 — 이 저장소의 AI 에이전트 지침

이 파일은 이 저장소에서 구현하는 모든 AI 에이전트에 적용된다. 상위 워크스페이스의 `AGENTS.md`도 함께 따른다. 사용자의 직접 지시와 팀이 확정한 결정이 이 문서보다 우선한다.

## 먼저 읽을 문서

1. `docs/README.md`: 베이스·팀 문서의 출처와 독자, 대화 모델의 실제 입력.
2. `docs/IMPLEMENTATION_SPEC.md`: 초기 베이스 대비 기능, 담당자, 현재 상태와 다음 작업.
3. `docs/STORY.md`: 확정된 인물·장면·엔딩.
4. `docs/API_CONTRACT.md`: 화면·서버 및 이미지 선택기의 고정 인터페이스.
5. `docs/TEAM_IMPLEMENTATION.md`: 구현 순서, 담당 영역, PR 절차.
6. 해당 작업에 영향을 주는 기존 `README.md`, `docs/PROJECT_GUIDE.md`, 코드와 테스트.

스토리의 핵심 사건과 세 엔딩은 `docs/STORY.md`를 기준으로 유지한다. 호감도 기준은 시연 후 조정할 수 있도록 설정값으로 둔다.

## 구현 원칙

- 이 제품은 **대화 중심의 스토리 챗봇**이다. 캐릭터의 자유 대사는 LLM이 만들고, 장면 이동·조사·단서·호감도 검사·엔딩은 결정적인 서버 규칙이 관리한다.
- 현재 대화 상대에게 허용된 인물 설정과 공개 가능한 사실만 전달한다. 미래 장면의 비밀을 프롬프트나 API 응답에 섞지 않는다.
- 화면은 서버의 `view`와 `events`를 렌더링한다. 장소·엔딩·차 키·호감도 판정을 화면에 중복 구현하지 않는다.
- `docs/API_CONTRACT.md`의 필드·ID 전달 방식·오류 형태와 이미지 선택기 시그니처를 유지한다. 바꿔야 한다면 먼저 팀장과 다른 엔지니어가 합의하고 계약서를 수정한다.
- 기존 베이스 코드를 출발점으로 사용하고, 실제 요청에 필요한 가장 단순한 완전한 변경을 한다. 필요한 입력 검증, 오류 처리, 접근성, 의미 있는 테스트를 생략하지 않는다.
- 답변별 이미지가 실제 대화·장면에 맞게 선택되어야 한다. 고정 초상화만으로 완료로 표시하지 않는다.
- 기능을 구현하거나 수정할 때마다 같은 작업에서 `docs/IMPLEMENTATION_SPEC.md`의 해당 항목을 비개발자도 이해할 말로 갱신한다. 실제 확인한 동작, 남은 확인·문제, 담당자를 적고 검증 전에는 완료라고 쓰지 않는다. 배포 상태는 공개 주소에서 확인한 뒤에만 갱신한다.
- 다음 기능 구현을 시작할 때는 `docs/IMPLEMENTATION_SPEC.md`의 **플레이 종료와 새 시작** 결정을 먼저 적용한다. 현재의 이어하기는 임시 동작이다. 문서에 기록한 새로고침·화면 이탈 뒤 재진입·엔딩 뒤 새 시작을 검증하기 전에는 다른 기능을 추가하지 않는다.

## 파일 소유권과 협업

- **팀장 엔지니어 (`suyoung` 브랜치):** `app.py`, `services/story.py`, `services/state_token.py`, `services/chatbot_service.py`, `services/generator.py`, `services/retriever.py`, `config/`, `data/knowledge/`, 서버 테스트.
- **팀원 엔지니어 (`yejoon` 브랜치):** `templates/`, `public/assets/`, `services/image_selector.py`, `data/images/`, 화면 테스트.
- `requirements.txt`, `README.md`, `AGENTS.md`, `docs/`, 양쪽이 사용하는 테스트는 공유 영역이다. 수정 전 담당자와 변경 범위를 정한다. 다른 사람 소유 파일을 AI 에이전트가 무심코 수정하지 않도록 diff를 확인한다.
- 기준 저장소는 팀장 소유 fork다. 팀장은 `suyoung`, 팀원은 `yejoon` 브랜치에서 담당 범위를 작업하고 `main` 대상 PR을 작성한다. 팀장이 검토하고 `main`에 병합한다. `main` 직접 push나 강제 push를 하지 않는다.
- Ponytail 같은 보조 플러그인을 사용해도 이 저장소의 스토리, API 계약, 파일 소유권, 검증 기준을 우선한다. 플러그인을 프로젝트 의존성으로 추가하지 않는다.

## 환경과 검증

- 로컬 환경 활성화: `conda activate chatbot-base`.
- 필요한 경우 이 환경에서 `python -m pip install -r requirements.txt`를 사용한다. 기존 환경을 다시 생성하지 않는다.
- 관련 변경 후 가장 작은 의미 있는 테스트를 실행한다. 전체 연결을 바꿨다면 `python -m unittest discover -s tests -v`와 브라우저의 실제 장면 흐름을 확인한다. 기존 데모 테스트가 새 계약과 충돌하면 실제 계약에 맞게 갱신한다.
- `.env`, API 키, 토큰, 비밀번호를 코드·문서·Git·스크린샷에 넣지 않는다. 커밋 전 `git status --short`와 `git check-ignore .env`를 확인한다.
- 작업 결과에는 변경 내용, 실행한 검증, 남은 위험이나 팀의 결정이 필요한 사항만 간결히 보고한다.

