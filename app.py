"""5기 캐릭터 챗봇 베이스의 웹 진입점."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, url_for

from services import ChatbotService
from services.state_token import InvalidStateToken


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "chatbot_config.json"
load_dotenv(BASE_DIR / ".env")

# Vercel은 public/을 CDN에서 제공하고, 로컬·Render는 Flask가 제공합니다.
IS_VERCEL = os.getenv("VERCEL") == "1"
app = Flask(
    __name__,
    static_folder=None if IS_VERCEL else "public",
    static_url_path=None if IS_VERCEL else "",
)
chatbot = ChatbotService()


def asset_url(filename: str) -> str:
    """배포 방식과 관계없이 public/ 파일을 같은 URL로 참조합니다."""
    if IS_VERCEL:
        return f"/{filename.lstrip('/')}"
    return url_for("static", filename=filename)


app.jinja_env.globals["asset_url"] = asset_url


def load_config() -> dict:
    """캐릭터 설정을 읽습니다. 편집 후 새로고침하면 화면에 반영됩니다."""
    with CONFIG_PATH.open(encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config, dict) or not isinstance(config.get("name"), str):
        raise ValueError("config/chatbot_config.json의 name을 확인하세요.")
    return config


def bot_view(config: dict) -> dict:
    thumbnail = config.get("thumbnail") or "assets/images/hateslop-logo.png"
    return {
        "name": config["name"],
        "description": config.get("description", ""),
        "tags": config.get("tags", []),
        "greeting": config.get("greeting", "안녕하세요!"),
        "image": asset_url(thumbnail),
    }


def error_response(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


@app.get("/")
def index():
    return render_template("index.html", bot=bot_view(load_config()))


@app.get("/detail")
def detail():
    return render_template("detail.html", bot=bot_view(load_config()))


@app.get("/chat")
def chat():
    username = (request.args.get("username") or "사용자").strip()[:50] or "사용자"
    return render_template("chat.html", bot=bot_view(load_config()), username=username)


def json_payload():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None
    return payload


def service_response(operation, *args):
    try:
        return jsonify(operation(*args))
    except InvalidStateToken:
        return error_response("invalid_state_token", "진행 기록을 열 수 없습니다. 새로 시작해 주세요.", 400)
    except ValueError as exc:
        code = str(exc)
        if code in {"invalid_action", "character_unavailable", "story_finished"}:
            return error_response(code, "지금은 이 행동을 할 수 없습니다.", 409)
        app.logger.exception("스토리 값 처리 실패")
        return error_response("chat_failed", "요청을 처리하지 못했습니다. 다시 시도해 주세요.", 500)
    except Exception:
        app.logger.exception("스토리 요청 실패")
        return error_response("chat_failed", "요청을 처리하지 못했습니다. 다시 시도해 주세요.", 500)


@app.post("/api/session")
def api_session():
    payload = json_payload()
    if payload is None:
        return error_response("invalid_request", "JSON 객체를 보내주세요.", 400)
    name = payload.get("player_name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 50:
        return error_response("invalid_request", "이름을 1~50자로 입력해 주세요.", 400)
    response = service_response(chatbot.start, name.strip())
    if isinstance(response, tuple):
        return response
    response.status_code = 201
    return response


@app.post("/api/session/resume")
def api_session_resume():
    payload = json_payload()
    if payload is None:
        return error_response("invalid_request", "JSON 객체를 보내주세요.", 400)
    return service_response(chatbot.resume, payload.get("state_token"))


@app.post("/api/chat")
def api_chat():
    payload = json_payload()
    if payload is None:
        return error_response("invalid_request", "JSON 객체를 보내주세요.", 400)
    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        return error_response("invalid_message", "메시지를 입력해 주세요.", 400)
    if len(message.strip()) > 2000:
        return error_response("message_too_long", "메시지는 2000자 이하로 입력해 주세요.", 413)
    character_id = payload.get("character_id")
    if not isinstance(character_id, str):
        return error_response("invalid_request", "대화 상대를 선택해 주세요.", 400)
    return service_response(chatbot.chat, payload.get("state_token"), character_id, message.strip(), load_config())


@app.post("/api/action")
def api_action():
    payload = json_payload()
    if payload is None:
        return error_response("invalid_request", "JSON 객체를 보내주세요.", 400)
    action_id = payload.get("action_id")
    if not isinstance(action_id, str):
        return error_response("invalid_request", "행동을 선택해 주세요.", 400)
    return service_response(chatbot.action, payload.get("state_token"), action_id)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG") == "1",
    )
