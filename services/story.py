"""더뉴빌리지의 고정 사건과 공개 가능한 화면 상태."""

from copy import deepcopy


START_SCORE = 70
JOB_THRESHOLD = 70
CHARACTERS = {"jimmy": "지미", "karen": "캐런", "bob": "밥", "cathy": "캐시"}
LOCATIONS = {
    "player_house": "새집",
    "karen_house": "캐런의 집",
    "butcher_shop": "정육점",
    "salon": "미용실",
    "square": "마을 광장",
    "basement": "정육점 지하실",
}


def event(speaker_id: str, text: str, image: str | None = None) -> dict:
    return {"speaker_id": speaker_id, "text": text, "image": image}


def new_state(player_name: str) -> dict:
    return {
        "version": 1,
        "player_name": player_name,
        "scene_id": "arrival",
        "location_id": "player_house",
        "visited": [],
        "clues": [],
        "journal": [],
        "affinity": START_SCORE,
        "scored_chat": [],
        "has_car_key": False,
        "ending": None,
        "history": {},
    }


def _action(action_id: str, label: str, kind: str) -> dict:
    return {"id": action_id, "label": label, "kind": kind}


def available_characters(state: dict) -> list[str]:
    scene = state["scene_id"]
    if scene in {"arrival", "cathy_task", "dinner_invite"}:
        return ["jimmy"]
    if scene == "neighbors":
        return {
            "karen_house": ["karen"],
            "butcher_shop": ["bob"],
            "salon": ["cathy"],
        }.get(state["location_id"], [])
    if scene == "cathy_help":
        return ["cathy"]
    if scene == "butcher_search":
        return ["jimmy"]
    if scene == "bob_caught" or scene == "festival_invite":
        return ["bob"]
    if scene in {"karen_dinner", "photo_found", "checkpoint"}:
        return ["karen"] if state["location_id"] == "karen_house" or scene == "checkpoint" else []
    if scene in {"festival", "hair_found"}:
        return ["karen", "bob", "cathy"]
    return []


def available_actions(state: dict) -> list[dict]:
    scene = state["scene_id"]
    if scene == "arrival":
        return [_action("visit_neighbors", "이웃들에게 인사하러 간다", "move")]
    if scene == "neighbors":
        actions = [
            _action("visit_karen", "캐런의 집", "move"),
            _action("visit_bob", "정육점", "move"),
            _action("visit_cathy", "미용실", "move"),
        ]
        if len(state["visited"]) == 3:
            actions.append(_action("return_home", "집으로 돌아간다", "move"))
        return actions
    if scene == "cathy_task":
        return [_action("go_help_cathy", "캐시를 도우러 간다", "move")]
    if scene == "cathy_help":
        return [_action("help_cathy", "캐시의 일을 돕는다", "choice")]
    if scene == "jimmy_butcher":
        return [_action("go_butcher", "지미를 찾아 정육점으로 간다", "move")]
    if scene == "butcher_search":
        return [_action("approach_jimmy", "사색이 된 지미에게 다가간다", "inspect")]
    if scene == "empty_butcher":
        return [_action("inspect_basement", "지하실을 살핀다", "inspect")]
    if scene == "basement":
        return [_action("go_upstairs", "위층으로 올라간다", "move")]
    if scene == "bob_caught":
        return [_action("return_home", "집으로 돌아간다", "move")]
    if scene == "dinner_invite":
        return [_action("accept_dinner_invite", "내일 저녁 약속을 기다린다", "choice")]
    if scene == "wait_dinner":
        return [_action("go_karen_dinner", "혼자 캐런의 집으로 간다", "move")]
    if scene == "karen_dinner":
        return [_action("inspect_room", "수상한 방을 살핀다", "inspect")]
    if scene == "photo_found":
        return [_action("return_home", "집으로 돌아간다", "move")]
    if scene == "checkpoint":
        if state["affinity"] >= JOB_THRESHOLD:
            return [
                _action("accept_job", "유통 운전 일을 수락한다", "choice"),
                _action("decline_job", "일자리를 거절한다", "choice"),
            ]
        return [_action("continue_festival", "축제까지 기다린다", "choice")]
    if scene == "festival_invite":
        return [_action("go_festival", "마을 축제로 간다", "move")]
    if scene == "festival":
        return [_action("inspect_food", "음식을 살핀다", "inspect")]
    if scene == "hair_found":
        return [
            _action("escape", "마을에서 도망친다", "choice"),
            _action("stay", "마을에 남는다", "choice"),
        ]
    return []


def view(state: dict) -> dict:
    characters = available_characters(state)
    return {
        "scene_id": state["scene_id"],
        "location_id": state["location_id"],
        "background": f"/assets/images/{state['location_id']}.svg",
        "available_characters": [
            {
                "id": character_id,
                "name": CHARACTERS[character_id],
                "portrait": f"/assets/images/{character_id}_neutral.svg",
            }
            for character_id in characters
        ],
        "available_actions": available_actions(state),
        "journal": state["journal"],
        "ending": state["ending"],
    }


def apply_action(state: dict, action_id: str) -> tuple[dict, list[dict]]:
    """현재 표시된 행동만 한 번 실행하고 다음 상태와 사건을 반환한다."""
    if action_id not in {item["id"] for item in available_actions(state)}:
        raise ValueError("invalid_action")
    next_state = deepcopy(state)
    scene = state["scene_id"]
    events = []

    if scene == "arrival":
        next_state.update(scene_id="neighbors", location_id="square")
        events.append(event("jimmy", "캐런, 밥, 캐시에게 인사해 봐. 모두 좋은 사람들이야."))
    elif scene == "neighbors":
        destination = {
            "visit_karen": ("karen_house", "karen"),
            "visit_bob": ("butcher_shop", "bob"),
            "visit_cathy": ("salon", "cathy"),
        }.get(action_id)
        if destination:
            next_state["location_id"] = destination[0]
            if destination[1] not in next_state["visited"]:
                next_state["visited"].append(destination[1])
            greetings = {
                "karen": "어머, 새로 오신 분이군요. 우리 마을은 모두 가족 같답니다.",
                "bob": "고기 좋아하쇼? 다음 주 축제 때 꼭 들르시게.",
                "cathy": "반가워요. 시간이 되면 미용실에도 들러 주세요.",
            }
            events.append(event(destination[1], greetings[destination[1]]))
        else:
            next_state.update(scene_id="cathy_task", location_id="player_house")
            events.append(event("jimmy", "캐시가 바빠 보이더라. 잠깐 도와줄 수 있을까?"))
    elif scene == "cathy_task":
        next_state.update(scene_id="cathy_help", location_id="salon")
        events.append(event("cathy", "잘 오셨어요. 이 일을 좀 도와주시겠어요?"))
    elif scene == "cathy_help":
        next_state.update(scene_id="jimmy_butcher", location_id="player_house")
        next_state["affinity"] = min(100, next_state["affinity"] + 5)
        events += [
            event("cathy", "고마워요. 새로 오신 분이 이렇게 도와주시다니."),
            event("thought", "캐시가 내 반응을 유심히 살피는 것 같았다."),
            event("jimmy", "나 정육점에 다녀올게."),
            event("karen", "혹시 지미를 보셨나요?"),
        ]
    elif scene == "jimmy_butcher":
        next_state.update(scene_id="butcher_search", location_id="butcher_shop")
        events.append(event("thought", "정육점에 도착하니 지미의 얼굴이 사색이 되어 있었다."))
    elif scene == "butcher_search":
        next_state["scene_id"] = "empty_butcher"
        events.append(event("jimmy", "지금은 말할 수 없어. 나중에 보자.", "/assets/images/jimmy_worried.svg"))
    elif scene == "empty_butcher":
        next_state.update(scene_id="basement", location_id="basement")
        next_state["clues"].append("notebook")
        next_state["journal"].append("지하실의 수첩에 지미의 이름과 축제 준비 날짜가 함께 적혀 있었다.")
        next_state["affinity"] = max(0, next_state["affinity"] - 5)
        events.append(event("thought", "수첩에는 지미의 이름이 있었다. 음식의 정체까지는 알 수 없었다."))
    elif scene == "basement":
        next_state.update(scene_id="bob_caught", location_id="butcher_shop")
        events.append(event("bob", "거기서 뭐 하시오? 여긴 손님이 들어올 곳이 아니야."))
    elif scene == "bob_caught":
        next_state.update(scene_id="dinner_invite", location_id="player_house")
        events.append(event("jimmy", "내일 저녁, 캐런네 집에서 만나자. 꼭 와 줘."))
    elif scene == "dinner_invite":
        next_state["scene_id"] = "wait_dinner"
        events.append(event("thought", "다음 날 약속 시간이 지났지만 지미는 오지 않았다."))
    elif scene == "wait_dinner":
        next_state.update(scene_id="karen_dinner", location_id="karen_house")
        events.append(event("karen", "어서 오세요. 지미는… 아직 안 왔군요. 편히 둘러보세요."))
    elif scene == "karen_dinner":
        next_state["scene_id"] = "photo_found"
        next_state["clues"].append("jimmy_photo")
        next_state["journal"].append("캐런의 수상한 방에서 지미의 사진을 발견했다.")
        next_state["affinity"] = max(0, next_state["affinity"] - 5)
        events += [
            event("thought", "벽에 지미의 사진이 걸려 있었다."),
            event("karen", "거기서 무엇을 보고 계신 거죠?", "/assets/images/karen_worried.svg"),
        ]
    elif scene == "photo_found":
        next_state.update(scene_id="checkpoint", location_id="player_house")
        if next_state["affinity"] >= JOB_THRESHOLD:
            events.append(event("karen", "내일부터 유통 운전 일을 맡아 주시겠어요? 차 키도 드리죠."))
        else:
            events.append(event("thought", "캐런은 일자리를 권하지 않았다. 누군가 집 앞을 지키고 있었다."))
    elif scene == "checkpoint":
        next_state["scene_id"] = "festival_invite"
        if action_id == "accept_job":
            next_state["has_car_key"] = True
            next_state["journal"].append("캐런의 유통 운전 일을 받아 차 키를 얻었다.")
            events.append(event("karen", "잘 생각하셨어요. 이제 우리와 함께 일하게 됐군요."))
        elif action_id == "decline_job":
            events.append(event("karen", "아쉽지만 괜찮아요. 축제에는 꼭 오세요."))
        else:
            events.append(event("thought", "축제가 다가오는 동안 누군가 계속 나를 지켜봤다."))
        events.append(event("bob", "고기 좋아한다고 했지? 다음 주 축제에 와 보시오."))
    elif scene == "festival_invite":
        next_state.update(scene_id="festival", location_id="square")
        events.append(event("narrator", "광장에 축제 음식이 차려졌다. 주민들이 자리에 앉기를 권한다."))
    elif scene == "festival":
        next_state["scene_id"] = "hair_found"
        next_state["clues"].append("jimmy_hair")
        next_state["journal"].append("축제 음식에서 금발인 지미의 머리카락을 발견했다.")
        events.append(event("thought", "음식 속 금발 머리카락. 지미의 머리카락이다. 이 마을의 비밀을 알아차렸다."))
    elif scene == "hair_found":
        ending = "assimilation" if action_id == "stay" else "escape" if state["has_car_key"] else "death"
        next_state.update(scene_id="ending", ending=ending)
        endings = {
            "escape": "차 키를 움켜쥐고 마을 경계를 빠져나왔다. 더뉴빌리지는 뒤로 멀어졌다.",
            "death": "차가 없었다. 이웃들이 길을 막았고, 곧 지미의 사진 옆에 내 사진이 걸렸다.",
            "assimilation": "새 이웃이 도착했다. 나는 캐런처럼 웃으며 말했다. ‘더뉴빌리지에 오신 걸 환영해요.’",
        }
        next_state["journal"].append(endings[ending])
        events.append(event("narrator", endings[ending], f"/assets/images/ending_{ending}.svg"))

    return next_state, events
