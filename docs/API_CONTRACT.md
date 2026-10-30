# 더뉴빌리지로 오세요 — 화면·서버 API 계약 v2

이 계약은 화면과 서버를 다른 브랜치에서 작업할 때의 공통 기준이다. 모든 API는 동일 출처의 UTF-8 JSON을 사용한다. 서버만 장면·단서·호감도·차 키·엔딩을 판정한다. 화면은 응답의 `view`와 `events`를 그린다.

## 성공 응답

모든 성공 응답은 같은 최상위 필드를 사용한다.

```json
{
  "state_token": "encrypted-state-token",
  "events": [{"speaker_id": "jimmy", "text": "새로 오셨군요!", "image": "/assets/images/jimmy_smile.svg"}],
  "view": {
    "scene_id": "arrival",
    "location_id": "player_house",
    "background": "/assets/images/player_house.svg",
    "available_characters": [{"id": "jimmy", "name": "지미", "portrait": "/assets/images/jimmy_neutral.svg"}],
    "available_actions": [{"id": "visit_neighbors", "label": "이웃들에게 인사하러 간다", "kind": "move"}],
    "journal": [],
    "ending": null
  }
}
```

- `state_token`은 암호화된 진행 기록이다. 화면은 같은 브라우저의 `localStorage`에 저장하고 **모든 후속 요청에 그대로 보낸다**. 이 값을 URL에 넣거나 수정하지 않는다. 서버가 재시작해도 같은 `STORY_STATE_KEY`가 설정되어 있으면 복원할 수 있다.
- `events`는 이번 요청에서 새로 생긴 메시지다. `speaker_id`는 `jimmy`, `karen`, `bob`, `cathy`, `narrator`, `thought` 중 하나이고 `image`는 공개 URL 또는 `null`이다. 사용자의 입력은 화면이 표시한다.
- `view`에는 현재 장면·장소와 공개 가능한 선택지만 들어간다. `available_actions.kind`는 `move`, `inspect`, `choice` 중 하나다. `ending`은 `null`, `escape`, `death`, `assimilation` 중 하나다. 엔딩 후에는 대화 상대와 행동 목록이 비어 있다.
- 호감도, 차 키, 미래 단서, 인물별 비밀은 `view`로 보내지 않는다. 이미 발견한 사실만 `journal`에 나타낸다.
- URL은 `/assets/images/...` 형식이며 실제 파일이 `public/assets/images/`에 있어야 한다.

## 요청

| 엔드포인트 | JSON 요청 | 성공 | 역할 |
| --- | --- | --- | --- |
| `POST /api/session` | `{"player_name":"알렉스"}` | `201` | 새 이야기 시작. 이름은 공백을 제외한 1~50자 |
| `POST /api/session/resume` | `{"state_token":"..."}` | `200` | 현재 진행을 읽는다. 새 사건은 발생시키지 않는다 |
| `POST /api/chat` | `{"state_token":"...","character_id":"jimmy","message":"마을은 어때요?"}` | `200` | 현재 대화 가능한 인물에게 자유 입력. 메시지는 공백을 제외한 1~2000자 |
| `POST /api/action` | `{"state_token":"...","action_id":"visit_neighbors"}` | `200` | 직전 `view.available_actions`에 있는 ID만 실행 |

대화 입력은 AI 대사와 제한된 호감도 변화만 만든다. 장면 이동, 단서 획득, 차 키, 엔딩은 `action_id`로만 처리한다. 화면은 요청 중 다른 요청을 보내지 않고, 성공 응답의 새 토큰으로 이전 토큰을 교체한다. 모델 실패 시 이전 토큰을 유지한다.

## 오류

```json
{"error":{"code":"invalid_action","message":"지금은 이 행동을 할 수 없습니다."}}
```

| HTTP | 코드 | 의미 |
| --- | --- | --- |
| `400` | `invalid_request`, `invalid_message`, `invalid_state_token` | 요청 형식·입력 또는 토큰이 잘못됨 |
| `409` | `invalid_action`, `character_unavailable`, `story_finished` | 현재 장면에서 불가능한 요청 |
| `413` | `message_too_long` | 메시지가 2000자를 넘음 |
| `500` | `chat_failed` | 모델 호출 등 처리 실패. 서버 비밀과 내부 예외를 노출하지 않음 |

## 서버 내부 이미지 선택기

```python
select(reply_text: str, character_id: str, scene_id: str, visual_cue: str | None = None) -> str | None
```

`visual_cue`는 `neutral`, `smile`, `worried` 중 하나이거나 `None`이다. 선택기는 대사·상황에 맞는 카탈로그 이미지를 반환하지만 진행 상태를 바꾸지 않는다. 카탈로그에 없는 파일이나 외부 URL을 새로 만들지 않는다.

## 변경 절차

필드 이름, 자료형, 엔드포인트 또는 이미지 선택기 시그니처를 바꾸려면 두 개발자가 먼저 합의해 이 문서를 수정한다. 각자 브랜치에서 인터페이스를 추측해 늘리지 않는다.
