"""플레이어 발화를 분류하고 갱신된 마을 태도로 인물 대사를 만든다."""

import json
import os
import re

from openai import OpenAI

from .retriever import KnowledgeHit
from .story import CHAT_DELTAS, WARY_SCORE, WELCOME_SCORE


ALLOWED_REASONING_EFFORTS = {"none", "low", "medium"}
TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "visual_cue": {"type": "string", "enum": ["neutral", "smile", "worried"]},
    },
    "required": ["reply", "visual_cue"],
    "additionalProperties": False,
}
CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {"category": {"type": "string", "enum": list(CHAT_DELTAS)}},
    "required": ["category"],
    "additionalProperties": False,
}


class StoryGenerator:
    def classify(self, question: str, history: list[dict], scene_events: list[dict]) -> str:
        effort = os.getenv("OPENAI_REASONING_EFFORT", "none")
        if effort not in ALLOWED_REASONING_EFFORTS:
            raise ValueError("OPENAI_REASONING_EFFORT must be none, low, or medium.")
        recent = [{"role": item["role"], "content": item["content"]} for item in history[-6:]]
        scene_lines = "\n".join(item["text"] for item in scene_events)
        response = OpenAI(timeout=20.0, max_retries=0).responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
            reasoning={"effort": effort},
            instructions=(
                "이번 플레이어 발화의 행동만 분류하세요. 주민 답변의 친절함이나 표정은 기준이 아닙니다. "
                "첫 인사, 감사, 안부, 상대의 일에 대한 관심, 예의 있는 질문과 반응은 도움 약속이 없어도 friendly입니다. "
                "예: '안녕하세요', '고맙습니다', '잘 지내셨어요?', '하시는 일은 어떠세요?', '마을 이야기를 들려주실 수 있나요?', '많이 놀라셨겠어요'는 friendly입니다. "
                "실제로 도움을 제안·약속하거나 요청을 받아들이면 cooperative입니다. "
                "맥락 없는 짧은 반복, 사실 확인만 하는 말, 판단하기 어려운 말은 neutral입니다. "
                "위협·모욕, 분명한 적대 행동, 상대가 거절한 뒤에도 계속하는 압박만 hostile입니다. "
                "사건을 이해하려는 첫 질문이나 근거 있는 추궁만으로 hostile이라 하지 마세요. '지미는 어디 있죠?', '사진은 왜 여기 있나요?'는 적대가 아닙니다. "
                f"현재 공개된 대사:\n{scene_lines}"
            ),
            input=recent + [{"role": "user", "content": question}],
            text={"format": {"type": "json_schema", "name": "player_action", "strict": True, "schema": CLASSIFICATION_SCHEMA}},
            max_output_tokens=100,
        )
        if response.status == "incomplete":
            raise RuntimeError("모델 분류가 완료되지 않았습니다.")
        try:
            category = json.loads(response.output_text)["category"]
            if category not in CHAT_DELTAS:
                raise ValueError("invalid category")
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("모델 분류 형식이 올바르지 않습니다.") from exc
        return category

    def generate(
        self,
        question: str,
        username: str,
        character: dict,
        knowledge: list[KnowledgeHit],
        history: list[dict],
        place_name: str,
        affinity: int,
        scene_events: list[dict],
        scene_context: tuple[str, str, str],
    ) -> dict:
        effort = os.getenv("OPENAI_REASONING_EFFORT", "none")
        if effort not in ALLOWED_REASONING_EFFORTS:
            raise ValueError("OPENAI_REASONING_EFFORT must be none, low, or medium.")

        persona = character.get("persona", {})
        village_attitude = (
            "경계: 원래의 성격과 말투를 유지하되 대답을 짧게 하고 거리를 두세요. 캐런은 정중하고 밝은 겉모습을 유지하세요"
            if affinity < WARY_SCORE else
            "환대: 원래의 성격과 말투를 유지하며 편안하게 맞이하세요"
            if affinity >= WELCOME_SCORE else
            "평소: 원래의 성격과 말투를 유지하며 자연스럽게 대하세요"
        )
        instructions = (
            f"당신은 1960년대 미국 마을 더뉴빌리지의 {character['name']}입니다. 한국어로 자연스럽게 말하세요.\n"
            f"현재 장소: {place_name}. 마을 전체의 태도: {village_attitude}. 이 태도는 모든 주민에게 공유됩니다. 점수 자체를 대사에서 말하지 마세요.\n"
            f"성격: {persona.get('personality', '')}\n"
            f"말투: {persona.get('speaking_style', '')}\n"
            f"현재 공개 가능한 사실: {persona.get('world', '')}\n"
            "제공된 사실 밖의 사건이나 미래의 비밀을 지어내거나 미리 밝히지 마세요. "
            "장소 이동, 단서 획득, 호감도와 엔딩을 선언하지 마세요. 이전에 나눈 대화를 기억하고, 일반적인 질문에도 자연스럽게 이어서 한두 문장으로 대답하세요. "
            "현재 장면에서 이미 한 대사를 반복하거나 다시 인사하지 말고, 플레이어의 질문에 이어서 답하세요. "
            "reply에는 인물이 실제로 말하는 문장만 쓰세요. 목록 기호(-, *, •), 제목, 강조 표시, 행동 설명, 화자 이름을 넣지 말고 문장은 일반 문장부호로 이어 쓰세요. "
            "visual_cue는 호감도 판정과 별개로 실제 답변의 표정을 나타냅니다. 캐런·캐시가 친절하게 맞이하거나 호의적으로 답하면 smile, 불안하거나 화가 나면 worried를 고르세요. 호감도가 올랐다는 이유만으로 웃게 하지 마세요. 경계 단계의 캐런도 겉으로 웃을 수 있습니다."
        )

        if scene_events:
            lines = "\n".join(
                f"- {'당신이 이미 한 말' if item['speaker_id'] != 'narrator' else '공개된 상황'}: {item['text']}"
                for item in scene_events
            )
            instructions += f"\n현재 장면에서 이미 일어난 공개 사건:\n{lines}"

        observed, known, withheld = scene_context
        instructions += (
            f"\n현재 시점의 장면 정보 (오래된 대화보다 우선):\n"
            f"플레이어가 목격한 사실: {observed}\n"
            f"당신이 실제로 아는 사실: {known}\n"
            f"지금 말하면 안 되는 사실: {withheld}\n"
            "플레이어가 '왜요?', '무슨 일이에요?'처럼 물으면 직전 사건을 가리키는 것으로 해석하세요. "
            "오래된 대화가 현재 장면과 충돌하면 현재 장면을 따르세요. "
            "당신이 아는 사실과 플레이어가 아는 사실을 혼동하지 말고, 모르면 모른다고 답하세요."
        )

        if knowledge:
            context = "\n".join(
                f"- {hit.title}: {hit.content}" for hit in knowledge[:3]
            )
            instructions += f"\n참고 자료:\n{context}"

        conversation = [
            {"role": item["role"], "content": item["content"]}
            for item in history[-20:]
        ]
        if scene_events:
            conversation.append({
                "role": "developer",
                "content": f"현재 장면에서 방금 들은 말: {scene_events[-1]['text']}\n현재 목격한 상황: {observed}",
            })
        conversation.append({"role": "user", "content": f"{username}: {question}"})
        response = OpenAI(timeout=20.0, max_retries=0).responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-6-luna"),
            reasoning={"effort": effort},
            instructions=instructions,
            input=conversation,
            text={"format": {"type": "json_schema", "name": "character_turn", "strict": True, "schema": TURN_SCHEMA}},
            max_output_tokens=700,
        )
        if response.status == "incomplete":
            raise RuntimeError("모델 응답이 완료되지 않았습니다.")

        try:
            turn = json.loads(response.output_text)
            if not isinstance(turn["reply"], str):
                raise ValueError("empty reply")
            turn["reply"] = re.sub(r"(?m)^[ \t]*[-–—*•][ \t]+", "", turn["reply"]).strip()
            if not turn["reply"]:
                raise ValueError("empty reply")
            if turn["visual_cue"] not in {"neutral", "smile", "worried"}:
                raise ValueError("invalid visual cue")
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("모델 응답 형식이 올바르지 않습니다.") from exc
        if character["name"] == "캐런":
            turn["reply"] = re.sub(r"[,，]?\s*후후[.…!~,，]*", "", turn["reply"]).strip() or "편하게 말씀해 주세요."
        return turn
