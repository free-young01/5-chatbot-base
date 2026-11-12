"""진행 상태, 인물 대화, 이미지와 API 응답을 연결한다."""

from copy import deepcopy
from hashlib import sha256
from logging import getLogger
from time import perf_counter

from .generator import StoryGenerator
from .image_selector import StoryImageSelector
from .retriever import StoryRetriever
from .state_token import decode_state, encode_state
from .story import CHAT_DELTAS, LOCATIONS, MAX_HOSTILE_CHATS_PER_SCENE, adjusted_affinity, apply_action, available_characters, event, new_state, scene_context, view


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

    def start(self, player_name: str, gender: str) -> dict:
        state = new_state(player_name, gender)
        greeting = "난 지미야. 한 달 전에 이사 왔어. 마을을 소개해 줄게. 궁금한 게 있으면 물어봐!"
        events = [event("jimmy", f"안녕, {player_name}! {greeting}")]
        state["scene_events"] = [
            {"speaker_id": "jimmy", "text": "내 친구 찰스가 지난주에 마을을 떠나서 외로웠던 참이었어!"},
            {"speaker_id": "jimmy", "text": greeting},
        ]
        return self._response(state, events)

    def resume(self, token: str) -> dict:
        return self._response(decode_state(token), [])

    def action(self, token: str, action_id: str) -> dict:
        state, events = apply_action(decode_state(token), action_id)
        state["scene_events"] = [
            {"speaker_id": item["speaker_id"], "text": item["text"]}
            for item in events if item["speaker_id"] != "thought"
        ]
        return self._response(state, events)

    def chat(self, token: str, character_id: str, message: str, config: dict) -> dict:
        state = decode_state(token)
        if state["ending"] is not None:
            raise ValueError("story_finished")
        if character_id not in available_characters(state):
            raise ValueError("character_unavailable")
        knowledge = self.retriever.search(message, character_id, state["scene_id"], state["clues"])
        history = state["history"].get(character_id, [])
        scene_events = [item for item in state.get("scene_events", [])
                        if item["speaker_id"] in {character_id, "narrator"}]
        started = perf_counter()
        try:
            attitude = self.generator.classify(message, history, scene_events)
        finally:
            getLogger(__name__).info("chat classification %.1f ms", (perf_counter() - started) * 1000)
        next_state = deepcopy(state)
        just_told_destination = (
            state["scene_id"] == "karen_search" and not state.get("jimmy_destination_told")
            and "정육점" in message and any(word in message for word in ("지미", "갔", "간다", "간다고", "가겠", "간대"))
        )
        if just_told_destination:
            next_state["jimmy_destination_told"] = True
        score_key = f"{state['scene_id']}:{character_id}"
        message_key = " ".join(message.casefold().split())
        message_hash = sha256(message_key.encode("utf-8")).hexdigest()
        seen = next_state.setdefault("scored_messages", [])
        if message_key not in seen and message_hash not in seen:
            seen.append(message_hash)
            scored = next_state["scored_chat"]
            before = next_state["affinity"]
            if attitude in {"friendly", "cooperative"}:
                friendly_key, cooperative_key = f"{score_key}:friendly", f"{score_key}:cooperative"
                if attitude == "friendly" and friendly_key not in scored and cooperative_key not in scored:
                    next_state["affinity"] = adjusted_affinity(before, CHAT_DELTAS[attitude])
                    next_state.setdefault("positive_scores", {})[score_key] = before
                    scored.append(friendly_key)
                elif attitude == "cooperative" and cooperative_key not in scored:
                    if friendly_key in scored:
                        first_score = next_state.get("positive_scores", {}).get(score_key, before)
                        extra = adjusted_affinity(first_score, CHAT_DELTAS["cooperative"]) - adjusted_affinity(first_score, CHAT_DELTAS["friendly"])
                        next_state["affinity"] = min(100, before + extra)
                    else:
                        next_state["affinity"] = adjusted_affinity(before, CHAT_DELTAS[attitude])
                    scored.append(cooperative_key)
                if next_state["affinity"] > before:
                    next_state["hostile_streak"] = max(0, next_state.get("hostile_streak", 0) - 1)
            elif attitude == "hostile":
                count = sum(key.startswith(f"{score_key}:hostile:") for key in scored)
                count += f"{score_key}:suspicious" in scored  # Earlier tokens used this category.
                if count < MAX_HOSTILE_CHATS_PER_SCENE:
                    streak = next_state.get("hostile_streak", 0)
                    next_state["affinity"] = adjusted_affinity(before, CHAT_DELTAS["hostile"] * min(streak + 1, 3))
                    if next_state["affinity"] < before:
                        next_state["hostile_streak"] = streak + 1
                        scored.append(f"{score_key}:hostile:{count + 1}")
        started = perf_counter()
        try:
            turn = {"reply": "...", "visual_cue": "worried"} if state["scene_id"] == "butcher_search" else self.generator.generate(
                message, state["player_name"], config["characters"][character_id], knowledge, history,
                LOCATIONS[state["location_id"]], next_state["affinity"], scene_events,
                scene_context(next_state, just_told_destination), scene_id=state["scene_id"],
            )
        finally:
            getLogger(__name__).info("chat generation %.1f ms", (perf_counter() - started) * 1000)
        # shortcut: 인물마다 최근 10번의 대화만 보관, 긴 대화 기억이 필요하면 요약을 추가한다.
        next_state["history"][character_id] = (history + [
            {"role": "user", "content": message[:500]},
            {"role": "assistant", "content": turn["reply"][:500]},
        ])[-20:]
        image = self.image_selector.select(
            turn["reply"], character_id, state["scene_id"], turn["visual_cue"]
        )
        return self._response(next_state, [event(character_id, turn["reply"], image)])
