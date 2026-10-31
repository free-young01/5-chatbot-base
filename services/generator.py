"""인물의 대사와 대화 태도를 한 번의 모델 호출로 생성한다."""

import json
import os

from openai import OpenAI

from .retriever import KnowledgeHit


ALLOWED_REASONING_EFFORTS = {"none", "low", "medium"}
TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "attitude": {"type": "string", "enum": ["cooperative", "neutral", "suspicious"]},
        "visual_cue": {"type": "string", "enum": ["neutral", "smile", "worried"]},
    },
    "required": ["reply", "attitude", "visual_cue"],
    "additionalProperties": False,
}


class StoryGenerator:
    def generate(
        self,
        question: str,
        username: str,
        character: dict,
        knowledge: list[KnowledgeHit],
        history: list[dict],
    ) -> dict:
        effort = os.getenv("OPENAI_REASONING_EFFORT", "none")
        if effort not in ALLOWED_REASONING_EFFORTS:
            raise ValueError("OPENAI_REASONING_EFFORT must be none, low, or medium.")

        persona = character.get("persona", {})
        instructions = (
            f"당신은 1960년대 미국 마을 더뉴빌리지의 {character['name']}입니다. 한국어로 자연스럽게 말하세요.\n"
            f"성격: {persona.get('personality', '')}\n"
            f"말투: {persona.get('speaking_style', '')}\n"
            f"현재 공개 가능한 사실: {persona.get('world', '')}\n"
            "제공된 사실 밖의 사건이나 미래의 비밀을 지어내거나 미리 밝히지 마세요. "
            "장소 이동, 단서 획득, 호감도와 엔딩을 선언하지 마세요. 한두 문장으로 대답하세요. "
            "attitude는 캐릭터의 감정이 아니라 사용자 발화가 협조적인지, 의심·추궁하는지 판정하세요. "
            "애매하면 neutral을 선택하세요. visual_cue는 답변에 어울리는 표정입니다."
        )

        if knowledge:
            context = "\n".join(
                f"- {hit.title}: {hit.content}" for hit in knowledge[:3]
            )
            instructions += f"\n참고 자료:\n{context}"

        conversation = [
            {"role": item["role"], "content": item["content"]}
            for item in history[-12:]
        ]
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
            if not isinstance(turn["reply"], str) or not turn["reply"].strip():
                raise ValueError("empty reply")
            if turn["attitude"] not in {"cooperative", "neutral", "suspicious"}:
                raise ValueError("invalid attitude")
            if turn["visual_cue"] not in {"neutral", "smile", "worried"}:
                raise ValueError("invalid visual cue")
        except (ValueError, KeyError, TypeError) as exc:
            raise RuntimeError("모델 응답 형식이 올바르지 않습니다.") from exc
        return turn
