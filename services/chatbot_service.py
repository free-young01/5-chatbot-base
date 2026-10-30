"""진행 상태, 인물 대화, 이미지와 API 응답을 연결한다."""

from copy import deepcopy

from .generator import StoryGenerator
from .image_selector import StoryImageSelector
from .retriever import StoryRetriever
from .state_token import decode_state, encode_state
from .story import apply_action, available_characters, event, new_state, view


class ChatbotService:
    def __init__(self, retriever=None, generator=None, image_selector=None):
        self.retriever = retriever or StoryRetriever()
        self.generator = generator or StoryGenerator()
        self.image_selector = image_selector or StoryImageSelector()

    def _response(self, state: dict, events: list[dict]) -> dict:
        for item in events:
            if item["image"] is None and item["speaker_id"] in {"jimmy", "karen", "bob", "cathy"}:
                item["image"] = self.image_selector.select(
                    item["text"], item["speaker_id"], state["scene_id"]
                )
        return {"state_token": encode_state(state), "events": events, "view": view(state)}

    def start(self, player_name: str) -> dict:
        state = new_state(player_name)
        return self._response(state, [event("jimmy", f"안녕, {player_name}! 난 지미야. 한 달 전에 이사 왔어. 마을을 소개해 줄게.")])

    def resume(self, token: str) -> dict:
        return self._response(decode_state(token), [])

    def action(self, token: str, action_id: str) -> dict:
        state, events = apply_action(decode_state(token), action_id)
        return self._response(state, events)

    def chat(self, token: str, character_id: str, message: str, config: dict) -> dict:
        state = decode_state(token)
        if state["ending"] is not None:
            raise ValueError("story_finished")
        if character_id not in available_characters(state):
            raise ValueError("character_unavailable")
        knowledge = self.retriever.search(message, character_id, state["scene_id"], state["clues"])
        history = state["history"].get(character_id, [])
        turn = self.generator.generate(
            message, state["player_name"], config["characters"][character_id], knowledge, history
        )
        next_state = deepcopy(state)
        attitude = turn["attitude"]
        score_key = f"{state['scene_id']}:{character_id}:{attitude}"
        if attitude != "neutral" and score_key not in next_state["scored_chat"]:
            next_state["affinity"] = max(0, min(100, next_state["affinity"] + (5 if attitude == "cooperative" else -5)))
            next_state["scored_chat"].append(score_key)
        next_state["history"][character_id] = (history + [
            {"role": "user", "content": message[:500]},
            {"role": "assistant", "content": turn["reply"][:500]},
        ])[-12:]
        image = self.image_selector.select(
            turn["reply"], character_id, state["scene_id"], turn["visual_cue"]
        )
        return self._response(next_state, [event(character_id, turn["reply"], image)])
