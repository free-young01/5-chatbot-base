"""답변의 표정 단서에 맞는 공개 이미지를 고른다."""

import json
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "images" / "catalog.json"
PUBLIC_PATH = Path(__file__).resolve().parent.parent / "public"


class StoryImageSelector:
    def __init__(self, path: Path = CATALOG_PATH):
        self.catalog = json.loads(path.read_text(encoding="utf-8"))

    def select(
        self, reply_text: str, character_id: str, scene_id: str, visual_cue: str | None = None
    ) -> str | None:
        images = self.catalog.get(character_id, {})
        cue = visual_cue
        if cue is None:
            cue = "worried" if any(word in reply_text for word in ("뭐", "안 돼", "말할 수", "아직", "왜")) else "smile"
        url = images.get(cue) or images.get("neutral")
        if not isinstance(url, str) or not url.startswith("/assets/images/"):
            return None
        path = PUBLIC_PATH / url.lstrip("/")
        return url if path.is_file() else None
