"""초기 장면에서 캐런이 읽는 공개 주민 정보를 확인한다."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.generator import StoryGenerator
from services.retriever import StoryRetriever


class KnowledgeTest(unittest.TestCase):
    def test_charles_search_never_exposes_disappearance_early(self):
        retriever = StoryRetriever()
        jimmy = retriever.search("찰스가 왜 떠났어?", "jimmy", "arrival", [])
        self.assertEqual([hit.title for hit in jimmy], ["지미의 친구 찰스"])
        for character in ("karen", "bob", "cathy"):
            hits = retriever.search("찰스는 어디 있어요?", character, "neighbors", [])
            self.assertEqual([hit.title for hit in hits], ["찰스에 관한 공개 정보"])
            self.assertNotIn("실종", hits[0].content)
        self.assertNotIn("실종", jimmy[0].content)

    def test_karen_finds_public_neighbor_introductions_early(self):
        retriever = StoryRetriever()
        for question in ("마을 사람들은 누가 있어요?", "이웃들은 어떤 사람들이에요?", "여기 사는 주민을 소개해 주세요"):
            hits = retriever.search(question, "karen", "neighbors", [])
            contents = " ".join(hit.content for hit in hits)
            for public_fact in ("캐런", "주민대표", "밥", "정육점", "식당", "캐시", "미용사", "지미", "주황빛 적갈색", "한 달"):
                self.assertIn(public_fact, contents, question)
            for secret in ("지하실", "실종", "식인", "공범", "음식의 재료"):
                self.assertNotIn(secret, contents, question)
        self.assertFalse(any(hit.title == "축제 음식의 정체" for hit in retriever.search("지미의 실종과 축제 음식", "karen", "neighbors", [])))

    def test_public_search_result_reaches_reply_prompt(self):
        question = "이웃들은 어떤 사람들이에요?"
        knowledge = StoryRetriever().search(question, "karen", "neighbors", [])
        answer = {"reply": "밥은 정육점과 식당을 하고, 캐시는 미용사예요.", "visual_cue": "smile"}
        with patch("services.generator.OpenAI") as client:
            client.return_value.responses.create.return_value = SimpleNamespace(status="completed", output_text=json.dumps(answer))
            StoryGenerator().generate(question, "알렉스", {"name": "캐런", "persona": {}}, knowledge, [], "캐런의 집", 50, [], ("방문", "주민대표", "미래 사건은 말하지 않음"), "neighbors")
        instructions = client.return_value.responses.create.call_args.kwargs["instructions"]
        self.assertIn("마을 주민 소개", instructions)
        self.assertIn("주황빛 적갈색", instructions)
        self.assertNotIn("식인", instructions)
        self.assertNotIn("공범", instructions)


if __name__ == "__main__":
    unittest.main()
