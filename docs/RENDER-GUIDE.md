# 더뉴빌리지 Render 배포 안내

팀장이 직접 만든 [공개 서비스](https://chatbot-bb1234.onrender.com/)가 실행 중입니다. 첫 화면, 대화, 첫 이동, 새로고침 뒤 이어하기와 `/health` 응답은 확인했습니다. Render 대시보드의 실제 설정과 재배포 뒤 복원은 아직 확인하지 않았습니다. 저장소의 [`render.yaml`](../render.yaml)은 나중에 같은 서비스를 새로 만들 때 참고할 설정으로, 비밀 값이 들어 있지 않습니다.

## 현재 서비스에서 팀장이 확인할 것

1. [Render Dashboard](https://dashboard.render.com/)에서 기존 서비스를 엽니다. 연결 저장소와 배포 브랜치가 팀장 소유 저장소의 `main`인지 확인합니다.
2. Python 웹 서비스라면 빌드 명령이 `pip install -r requirements.txt`, 시작 명령이 `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 app:app`인지 확인합니다. `/health`는 `{"status":"ok"}`를 반환합니다.
3. 환경 변수에 `OPENAI_API_KEY`와 `STORY_STATE_KEY`가 설정되어 있는지만 확인합니다. 값은 문서나 채팅에 복사하지 않습니다. `STORY_STATE_KEY`는 현재 서비스에서 쓰는 값을 계속 유지합니다.
4. 이후 변경을 `main`에 병합해 재배포할 때 같은 브라우저에서 이어하기가 유지되는지 시험합니다.

현재 서비스를 **새 Blueprint로 다시 만들지 않습니다.** [`render.yaml`](../render.yaml)은 새 서비스가 필요할 때만 사용합니다. 그때 팀장이 [Render Blueprint 안내](https://render.com/docs/infrastructure-as-code)에 따라 저장소를 연결하고 OpenAI 키를 Render 입력 화면에서 설정합니다.

키를 채팅, 문서, Git 또는 화면 캡처에 붙이지 않습니다. **`STORY_STATE_KEY`를 다시 만들거나 삭제하면 기존 플레이어의 이어하기 기록을 복원할 수 없습니다.** 이후 배포에서는 같은 값을 유지합니다.

## 프로듀서에게 주소를 전하기 전

- [시연 안내](PRODUCER_TEST_GUIDE.md)에 따라 시작, 대화, 조사, 세 결말을 실제 공개 주소에서 확인합니다.
- 브라우저를 새로고침해 이야기가 이어지는지 확인하고, Render에서 재배포한 뒤에도 같은 브라우저에서 이어지는지 확인합니다.
- 휴대전화 화면에서 글과 버튼, 그림이 보이는지 확인합니다.
- 대화 오류가 나면 화면의 안내를 확인하고 Render 로그에서 원인을 찾습니다. 로그를 공유할 때도 비밀 값을 지웁니다.

무료 서비스는 일정 시간 사용하지 않으면 잠들어 첫 접속에 시간이 걸릴 수 있습니다. [Render 무료 서비스 안내](https://render.com/docs/free)를 참고하세요. 공개 주소의 대화 요청은 팀의 OpenAI 사용량을 발생시키므로 시연 기간과 사용량을 팀장이 확인합니다.

## 변경을 다시 배포할 때

Render 서비스가 `main`에 연결되어 있고 자동 배포가 켜져 있다면, 검토가 끝난 변경을 `main`에 합칠 때 다시 배포됩니다. 공개 주소에서 바뀐 기능을 다시 확인하고 [구현 현황](IMPLEMENTATION_SPEC.md)을 갱신합니다. Render 화면에서 오류가 나면 [Render Flask 배포 안내](https://render.com/docs/deploy-flask)와 배포 로그를 확인합니다.
