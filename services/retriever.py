"""인물과 장면에 공개 가능한 마을 자료만 검색한다."""

import json
from dataclasses import dataclass
from pathlib import Path


FACTS_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge" / "facts.json"


@dataclass(frozen=True)
class KnowledgeHit:
    title: str
    content: str


class StoryRetriever:
    def __init__(self, path: Path = FACTS_PATH):
        self.facts = json.loads(path.read_text(encoding="utf-8"))

    def search(self, question: str, character_id: str, scene_id: str, clues: list[str]) -> list[KnowledgeHit]:
        query = question.casefold()
        hits = []
        for fact in self.facts:
            if character_id not in fact["characters"] or scene_id not in fact["scenes"]:
                continue
            if any(clue not in clues for clue in fact.get("requires", [])):
                continue
            if not fact["keywords"] or any(word.casefold() in query for word in fact["keywords"]):
                hits.append(KnowledgeHit(fact["title"], fact["content"]))
        return hits[:3]
