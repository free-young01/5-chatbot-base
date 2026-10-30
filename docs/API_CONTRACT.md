# 더뉴빌리지로 오세요 — 화면·서버 API 계약 v1

> **구현 전 계약.** 두 개발자가 다른 브랜치에서 동시에 작업할 수 있도록 요청·응답의 경계를 정한다. 현재 베이스 코드의 `/api/chat` 데모 형식과 다르므로 서버와 화면을 함께 이 계약으로 전환한다. 스토리의 미정 분기를 이 문서가 임의로 확정하지 않는다.

## 공통 규칙

- 모든 요청·응답은 UTF-8 JSON이다. 경로는 동일 출처의 상대 경로를 사용한다.
- 서버가 장면, 이동 가능 장소, 대화 가능 인물, 행동 가능 여부와 엔딩을 판정한다. 화면은 서버가 보낸 선택지만 표시하고 임의의 장면 전환을 만들지 않는다.
- `session_id`, 인물 ID, 행동 ID는 문자열이다. 화면은 서버가 제공한 ID를 그대로 보낸다. 표시용 이름이나 문장을 ID로 추측하지 않는다.
- 같은 `view` 객체가 모든 성공 응답에 들어간다. 화면은 매 응답의 `view`로 현재 화면을 갱신한다.
- `events`는 이번 요청으로 새로 발생한 표시용 메시지 목록이다. `view.journal`은 현재까지의 발견 기록이다. 둘을 혼동하지 않는다.
- `affinity`, 숨겨진 단서, 인물별 비밀, 내부 판정 조건은 응답으로 보내지 않는다. 스토리상 공개하기로 정한 결과만 `events`나 `journal`에 나타낸다.
- 호환성을 위해 기존 `GET /`, `/detail`, `/chat`, `/health`는 유지할 수 있지만, 새 화면은 아래 API를 기준으로 만든다. 현재 데모 테스트는 새 계약에 맞게 갱신한다.

## 공개 자료형

아래 JSON은 **형태의 예시**다. 설명 문장과 행동 ID는 실제 스토리 자료가 확정되면 바꿀 수 있다. 필드 이름과 자료형은 양쪽 개발자가 합의 없이 바꾸지 않는다.

```json
{
  "scene_id": "arrival",
  "location_id": "player_house",
  "background": "/assets/images/player_house.png",
  "available_characters": [
    {"id": "jimmy", "name": "지미", "portrait": "/assets/images/jimmy_neutral.png"}
  ],
  "available_actions": [
    {"id": "greet_neighbors", "label": "이웃에게 인사하러 간다", "kind": "move"}
  ],
  "journal": ["지미가 마을 사람들을 소개해 주었다."],
  "ending": null
}
```

`view`의 필드:

| 필드 | 형식 | 의미 |
| --- | --- | --- |
| `scene_id`, `location_id` | 문자열 | 서버가 정한 현재 장면·장소 ID |
| `background` | URL 문자열 또는 `null` | 현재 장소의 배경 이미지 |
| `available_characters` | `{id, name, portrait}` 배열 | 지금 대화할 수 있는 인물. `portrait`는 URL 문자열 또는 `null` |
| `available_actions` | `{id, label, kind}` 배열 | 지금 실행 가능한 버튼. `kind`는 `move`, `inspect`, `choice` 중 하나 |
| `journal` | 문자열 배열 | 플레이어가 이미 알게 된 생각·단서의 표시 문장 |
| `ending` | `null`, `escape`, `death`, `assimilation` 중 하나 | 엔딩에 도달했다면 해당 값. 엔딩 후 대화·행동은 허용하지 않음 |

`events`의 각 항목은 다음 형식이다.

```json
{"speaker_id":"jimmy","text":"새로 오셨군요!","image":"/assets/images/jimmy_smile.png"}
```

`speaker_id`는 `jimmy`, `karen`, `bob`, `cathy`, `narrator`, `thought` 중 하나다. `text`는 표시할 문자열이고 `image`는 답변·사건에 맞는 이미지 URL 또는 `null`이다. 인물의 AI 답변에는 선택된 이미지를 담고, 장소·생각 이벤트는 필요할 때만 이미지를 담는다. 사용자가 보낸 문장은 화면이 즉시 표시하며 서버의 `events`에 되풀이하지 않는다.

## 엔드포인트

### `POST /api/session` — 새 진행 시작

요청:

```json
{"player_name":"알렉스"}
```

응답 `201`:

```json
{"session_id":"opaque-session-id","events":[],"view":{"scene_id":"arrival","location_id":"player_house","background":null,"available_characters":[],"available_actions":[],"journal":[],"ending":null}}
```

`player_name`은 비어 있지 않은 문자열이어야 한다. 이름 길이 제한과 입력 검증의 세부 기준은 서버가 정하되, 오류는 아래 공통 형식을 따른다. `session_id`는 서버가 만든 불투명한 식별자다.

### `GET /api/session/<session_id>` — 현재 진행 복원

응답 `200`: `{"session_id":"...","events":[],"view":{...}}`. 이 API는 현재 상태를 읽기만 하고 사건을 진행시키지 않는다. 저장 방식이 정해지기 전에는 서버가 살아 있는 동안만 복원될 수 있다. 없는 세션은 `404`다.

### `POST /api/chat` — 선택한 인물과 자유 대화

요청:

```json
{"session_id":"opaque-session-id","character_id":"jimmy","message":"마을 축제는 언제 열려요?"}
```

응답 `200`:

```json
{"session_id":"opaque-session-id","events":[{"speaker_id":"jimmy","text":"다음 주에 축제가 열려요.","image":"/assets/images/jimmy_smile.png"}],"view":{"scene_id":"arrival","location_id":"player_house","background":null,"available_characters":[],"available_actions":[],"journal":[],"ending":null}}
```

`message`는 공백만으로 구성될 수 없고 최대 2000자다. `character_id`가 현재 `view.available_characters`에 없으면 서버가 거절한다. 대화 상대의 지식과 현재 장면을 서버가 적용한다. 채팅은 임의의 장면 이동이나 엔딩 확정을 수행하지 않는다.

### `POST /api/action` — 이동·조사·핵심 선택

요청:

```json
{"session_id":"opaque-session-id","action_id":"greet_neighbors"}
```

응답 `200`: `{"session_id":"...","events":[...],"view":{...}}`. `action_id`는 직전 상태의 `view.available_actions` 중 하나여야 한다. 이동·조사·선택의 실제 효과는 서버가 결정한다. 이미 사용했거나 현재 장면에서 불가능한 행동은 다시 실행되지 않는다. 화면은 `kind`에 따라 버튼의 모양만 달리할 수 있으며 규칙을 자체 구현하지 않는다.

## 오류

오류는 항상 다음 형태를 반환한다.

```json
{"error":{"code":"invalid_action","message":"지금은 이 행동을 할 수 없습니다."}}
```

| HTTP | 대표 코드 | 의미 |
| --- | --- | --- |
| `400` | `invalid_request`, `invalid_message` | JSON이나 필수 값이 잘못됨 |
| `404` | `session_not_found` | 세션이 없거나 더 이상 복원할 수 없음 |
| `409` | `character_unavailable`, `invalid_action`, `story_finished` | 현재 장면·엔딩과 요청이 충돌함 |
| `413` | `message_too_long` | 채팅 입력이 2000자를 넘음 |
| `500` | `chat_failed` | AI 응답 생성 등 서버 작업 실패. 성공처럼 빈 대사를 보내지 않음 |

서버의 내부 예외나 비밀 값은 오류 메시지에 넣지 않는다. 화면은 오류를 표시하되 직전 `view`를 임의로 바꾸지 않는다.

## 서버 내부 이미지 선택기 계약

화면 담당자가 `services/image_selector.py`를 구현하고 서버 담당자가 호출한다. 양쪽이 다음 시그니처와 반환값을 기준으로 작업한다.

```python
select(reply_text: str, character_id: str, scene_id: str, visual_cue: str | None = None) -> str | None
```

- `reply_text`: 인물이 실제로 말한 대사.
- `character_id`, `scene_id`: 위 API와 같은 ID.
- `visual_cue`: 서버가 알고 있는 표정·장면 단서. 지정하지 않으면 `None`.
- 반환값: `public/`에서 접근 가능한 `/assets/images/...` URL 또는 `None`.
- 선택기는 장면 진행, 호감도, 엔딩을 바꾸지 않는다. 카탈로그에 없는 파일의 URL을 만들지 않는다.

이 시그니처 또는 API 필드의 변경은 두 개발자가 먼저 합의해 이 문서를 갱신한 뒤 각 담당 브랜치에 반영한다.

