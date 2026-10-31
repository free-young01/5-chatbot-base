"""장면, 점수와 세 결말의 결정적인 규칙을 확인한다."""

import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

os.environ["STORY_STATE_KEY"] = Fernet.generate_key().decode("ascii")

from app import app, chatbot  # noqa: E402
from services.retriever import StoryRetriever  # noqa: E402
from services.state_token import decode_state  # noqa: E402


TO_CHECKPOINT = [
    "visit_neighbors", "visit_karen", "visit_bob", "visit_cathy", "return_home",
    "go_help_cathy", "help_cathy", "go_butcher", "approach_jimmy",
    "inspect_basement", "go_upstairs", "return_home", "accept_dinner_invite",
    "go_karen_dinner", "inspect_room", "return_home",
]


class StoryTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        response = self.client.post("/api/session", json={"player_name": "알렉스"})
        self.assertEqual(response.status_code, 201)
        self.token = response.get_json()["state_token"]

    def action(self, action_id):
        response = self.client.post("/api/action", json={"state_token": self.token, "action_id": action_id})
        self.assertEqual(response.status_code, 200, (action_id, response.get_json()))
        data = response.get_json()
        self.token = data["state_token"]
        return data

    def checkpoint(self):
        for action_id in TO_CHECKPOINT:
            self.action(action_id)
        self.assertEqual(decode_state(self.token)["scene_id"], "checkpoint")

    def festival(self, checkpoint_action):
        self.action(checkpoint_action)
        self.action("go_festival")
        self.action("inspect_food")
        self.assertEqual(decode_state(self.token)["scene_id"], "hair_found")

    def test_low_affinity_continues_to_festival_and_escape_fails_without_key(self):
        self.checkpoint()
        state = decode_state(self.token)
        self.assertEqual(state["affinity"], 65)
        self.assertIsNone(state["ending"])
        self.assertFalse(state["has_car_key"])
        self.festival("continue_festival")
        result = self.action("escape")
        self.assertEqual(result["view"]["ending"], "death")
        self.assertEqual(result["view"]["available_actions"], [])

    def test_cooperative_chat_unlocks_job_and_key_then_escape(self):
        turn = {"reply": "이웃에게 인사해 봐.", "attitude": "cooperative", "visual_cue": "smile"}
        with patch.object(chatbot.generator, "generate", return_value=turn):
            for _ in range(2):
                response = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "jimmy", "message": "고마워, 도울게"})
                self.assertEqual(response.status_code, 200)
                self.token = response.get_json()["state_token"]
        self.assertEqual(decode_state(self.token)["affinity"], 75)
        self.checkpoint()
        self.assertEqual(decode_state(self.token)["affinity"], 70)
        self.festival("accept_job")
        self.assertTrue(decode_state(self.token)["has_car_key"])
        self.assertEqual(self.action("escape")["view"]["ending"], "escape")

    def test_staying_assimilates_even_when_watched(self):
        self.checkpoint()
        self.festival("continue_festival")
        self.assertEqual(self.action("stay")["view"]["ending"], "assimilation")

    def test_action_cannot_repeat_and_secret_is_gated(self):
        self.action("visit_neighbors")
        response = self.client.post("/api/action", json={"state_token": self.token, "action_id": "visit_neighbors"})
        self.assertEqual(response.status_code, 409)
        retriever = StoryRetriever()
        self.assertEqual(retriever.search("지미의 머리카락과 고기", "jimmy", "arrival", []), [])
        self.assertFalse(any(hit.title == "축제 음식의 정체" for hit in retriever.search("지미 머리카락", "bob", "festival", [])))
        self.assertTrue(any(hit.title == "축제 음식의 정체" for hit in retriever.search("지미 머리카락", "bob", "hair_found", ["jimmy_hair"])))


if __name__ == "__main__":
    unittest.main()
