"""브라우저에 보관할 진행 상태를 암호화하고 검증한다."""

import json
import os

from cryptography.fernet import Fernet, InvalidToken


class InvalidStateToken(ValueError):
    pass


def _cipher() -> Fernet:
    key = os.getenv("STORY_STATE_KEY", "")
    if not key:
        raise RuntimeError("STORY_STATE_KEY가 설정되지 않았습니다.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError("STORY_STATE_KEY 형식이 올바르지 않습니다.") from exc


def encode_state(state: dict) -> str:
    raw = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _cipher().encrypt(raw).decode("ascii")


def decode_state(token: str) -> dict:
    if not isinstance(token, str) or not token or len(token) > 150_000:
        raise InvalidStateToken("진행 기록이 올바르지 않습니다.")
    try:
        state = json.loads(_cipher().decrypt(token.encode("ascii")))
    except (InvalidToken, UnicodeError, ValueError, TypeError) as exc:
        raise InvalidStateToken("진행 기록을 읽을 수 없습니다.") from exc
    if not isinstance(state, dict) or state.get("version") != 1:
        raise InvalidStateToken("현재 버전에서 열 수 없는 진행 기록입니다.")
    return state
