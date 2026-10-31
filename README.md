# 더뉴빌리지로 오세요

1960년대 미국의 수상한 마을을 배경으로 한 대화 중심 스토리 챗봇. 지미, 캐런, 밥, 캐시와 자유롭게 대화하고 장소 조사와 선택으로 이야기를 진행한다. 축제에서 금발인 지미의 머리카락을 발견한 뒤 선택에 따라 **탈출·사망·동화** 엔딩에 도달한다.

## 실행

```powershell
conda activate chatbot-base
python -m pip install -r requirements.txt
python app.py
```

처음 실행하기 전에 프로젝트 루트의 `.env`에 `OPENAI_API_KEY`와 `STORY_STATE_KEY`를 설정한다. 후자는 아래 명령으로 생성한 Fernet 키다. 실제 값은 Git에 올리지 않는다.

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`.env.example`에는 변수 이름과 공개 가능한 기본값만 있다. 브라우저에서 `http://localhost:5000`을 열고 이름을 입력해 시작한다.

## 동작 방식

- Flask 서버가 현재 장면, 허용된 대화 상대와 버튼, 호감도, 차 키, 엔딩을 판정한다. 장면 및 엔딩 규칙은 `services/story.py`에 있다.
- 화면의 자유 입력은 `POST /api/chat`으로 전달된다. 서버는 현재 인물과 장면에 공개 가능한 사실만 `data/knowledge/facts.json`에서 검색한다. OpenAI 모델 한 번의 구조화된 응답으로 대사, 대화 태도, 이미지 표정을 얻는다.
- 이미지 선택기는 `data/images/catalog.json`에서 인물·표정에 맞는 자산을 고른다. 현재 SVG는 교체 가능한 임시 그림이다.
- 진행 상태는 `STORY_STATE_KEY`로 암호화한 토큰으로 응답하며 브라우저의 `localStorage`에 저장된다. 같은 브라우저에서 새로고침하거나 서버를 재시작한 뒤 이어할 수 있다. 서버 키를 바꾸거나 브라우저 저장소를 지우면 이전 진행은 복원할 수 없다. 다른 기기와 동기화되지 않는다.

화면은 서버의 `view`와 `events`만 표시한다. API의 요청·응답 예시는 [계약서](docs/API_CONTRACT.md)에 있다.

## 검증

```powershell
python -m unittest discover -s tests -v
```

테스트는 모델을 대체하여 세 결말, 호감도 검사 시점, 같은 대화 태도의 중복 점수 방지, 정보 공개 범위, 토큰 변조, 모델 실패 시 상태 보존을 검사한다. 실제 모델 대사와 공개 URL의 화면은 별도로 확인해야 한다.

## 협업과 배포

[구현 명세와 진행 현황](docs/IMPLEMENTATION_SPEC.md), [스토리](docs/STORY.md), [두 개발자의 파일 경계](docs/TEAM_IMPLEMENTATION.md), [AI 에이전트 지침](AGENTS.md)을 함께 본다. 팀장 소유 fork를 기준으로 각자 브랜치와 PR로 작업하며 팀장이 `main`에 병합한다.

Render의 Python 웹 서비스는 `pip install -r requirements.txt`로 빌드하고 `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 app:app`으로 시작한다. 환경 변수에 `OPENAI_API_KEY`, `STORY_STATE_KEY`, `OPENAI_MODEL=gpt-6-luna`, `OPENAI_REASONING_EFFORT=none`을 설정한다. 같은 `STORY_STATE_KEY`를 유지해야 저장한 토큰이 재배포 뒤에도 복원된다. 공개 URL에서 시작부터 세 엔딩, 모바일 화면, 새로고침 복원을 확인한다.

기존 베이스 프로젝트의 상세 참고 문서는 `docs/`에 남겨 두었다. 이 프로젝트의 실제 API와 실행 방법은 이 README 및 [API 계약서](docs/API_CONTRACT.md)를 기준으로 한다.
