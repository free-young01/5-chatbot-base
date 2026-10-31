# 더뉴빌리지 Render 배포 안내

이 프로젝트는 저장소의 [`render.yaml`](../render.yaml)로 Render의 **무료 Python 웹 서비스**를 만듭니다. 서비스는 `main` 브랜치를 배포하며 `/health`로 실행 상태를 확인합니다. 설정 파일에는 비밀 값이 없습니다.

## 팀장이 처음 한 번 할 일

1. 배포할 변경을 검토해 `main`에 합칩니다. `render.yaml`이 GitHub의 `main`에 보여야 합니다.
2. [Render Dashboard](https://dashboard.render.com/)에 로그인합니다. **New → Blueprint**에서 팀장 소유 GitHub 저장소 `free-young01/5-chatbot-base`를 연결합니다. 이미 같은 서비스를 만들었다면 중복 서비스가 생기지 않도록 기존 서비스의 설정을 먼저 확인합니다.
3. Render가 `render.yaml`을 읽어 보여주는 서비스가 `new-village-story-demo`, 브랜치가 `main`, 플랜이 `Free`인지 확인합니다. `OPENAI_API_KEY` 입력 칸에는 운영진이 제공한 키를 Render 화면에서만 입력합니다. `STORY_STATE_KEY`는 Render가 처음 생성합니다. 배포를 시작합니다.
4. 상태가 **Live**가 되면 Render가 보여 주는 공개 주소를 엽니다. `/health`에서 `{"status":"ok"}`가 보이고, 첫 화면에서 이름 입력과 대화까지 되는지 확인합니다. 서비스 주소를 [README](../README.md)의 공개 시연 항목에 적습니다.

키를 채팅, 문서, Git 또는 화면 캡처에 붙이지 않습니다. **`STORY_STATE_KEY`를 다시 만들거나 삭제하면 기존 플레이어의 이어하기 기록을 복원할 수 없습니다.** 이후 배포에서는 같은 값을 유지합니다.

## 프로듀서에게 주소를 전하기 전

- [시연 안내](PRODUCER_TEST_GUIDE.md)에 따라 시작, 대화, 조사, 세 결말을 실제 공개 주소에서 확인합니다.
- 브라우저를 새로고침해 이야기가 이어지는지 확인하고, Render에서 재배포한 뒤에도 같은 브라우저에서 이어지는지 확인합니다.
- 휴대전화 화면에서 글과 버튼, 그림이 보이는지 확인합니다.
- 대화 오류가 나면 화면의 안내를 확인하고 Render 로그에서 원인을 찾습니다. 로그를 공유할 때도 비밀 값을 지웁니다.

무료 서비스는 일정 시간 사용하지 않으면 잠들어 첫 접속에 시간이 걸릴 수 있습니다. [Render 무료 서비스 안내](https://render.com/docs/free)를 참고하세요. 공개 주소의 대화 요청은 팀의 OpenAI 사용량을 발생시키므로 시연 기간과 사용량을 팀장이 확인합니다.

## 변경을 다시 배포할 때

검토가 끝난 변경을 `main`에 합치면 Render가 연결된 브랜치를 다시 배포합니다. 공개 주소에서 바뀐 기능을 다시 확인하고 [구현 현황](IMPLEMENTATION_SPEC.md)을 갱신합니다. Render 화면에서 오류가 나면 [Render Flask 배포 안내](https://render.com/docs/deploy-flask)와 배포 로그를 확인합니다.
