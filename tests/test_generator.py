"""대화 모델에 장소, 마을 공통 태도와 해당 인물의 기억만 전달한다."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.generator import StoryGenerator


class GeneratorTest(unittest.TestCase):
    def test_low_affinity_and_prior_chat_reach_model(self):
        answer = {"reply": "기억해요.", "attitude": "neutral", "visual_cue": "neutral"}
        history = [{"role": "user", "content": "나는 커피를 좋아해"}, {"role": "assistant", "content": "기억할게요."}]
        with patch("services.generator.OpenAI") as client:
            client.return_value.responses.create.return_value = SimpleNamespace(status="completed", output_text=json.dumps(answer))
            result = StoryGenerator().generate("내 취향 기억해?", "알렉스", {"name": "밥", "persona": {}}, [], history, "정육점", 65)
        self.assertEqual(result, answer)
        request = client.return_value.responses.create.call_args.kwargs
        self.assertIn("정육점", request["instructions"])
        self.assertIn("경계하고 조심스럽게", request["instructions"])
        self.assertEqual(request["input"][0]["content"], "나는 커피를 좋아해")


if __name__ == "__main__":
    unittest.main()
