"""장면, 점수와 세 결말의 결정적인 규칙을 확인한다."""

import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet

os.environ["STORY_STATE_KEY"] = Fernet.generate_key().decode("ascii")

from app import app, chatbot  # noqa: E402
from services.retriever import StoryRetriever  # noqa: E402
from services.state_token import decode_state, encode_state  # noqa: E402
from services.story import CHAT_DELTAS, START_SCORE, adjusted_affinity, available_actions, available_characters  # noqa: E402


TO_CHECKPOINT = [
    "visit_neighbors", "visit_karen", "visit_bob", "visit_cathy", "return_home",
    "go_help_cathy", "choose_shampoo", "choose_scissors", "choose_comb", "help_cathy", "return_home",
    "see_jimmy_off", "go_butcher", "approach_jimmy",
    "inspect_basement", "descend_stairs", "inspect_wallet", "open_wallet", "inspect_wallet_photo", "go_upstairs", "return_home", "accept_dinner_invite",
    "go_karen_dinner", "inspect_room", "inspect_photo_back", "recognize_photo",
    "inspect_charles_photo", "inspect_charles_photo_back", "recognize_charles_photo", "return_home",
]


class StoryTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        response = self.client.post("/api/session", json={"player_name": "알렉스", "gender": "male"})
        self.assertEqual(response.status_code, 201)
        self.token = response.get_json()["state_token"]

    def action(self, action_id):
        response = self.client.post("/api/action", json={"state_token": self.token, "action_id": action_id})
        self.assertEqual(response.status_code, 200, (action_id, response.get_json()))
        data = response.get_json()
        self.token = data["state_token"]
        self.assertLessEqual(len(data["view"]["available_characters"]), 1, action_id)
        return data

    def finish_photo_room(self):
        for action in ["inspect_photo_back", "recognize_photo", "inspect_charles_photo", "inspect_charles_photo_back", "recognize_charles_photo"]:
            if any(a["id"] == action for a in available_actions(decode_state(self.token))):
                result = self.action(action)
        return result

    def escape_through_truck(self):
        for action in ["escape", "begin_truck_escape", "open_truck_door"]:
            result = self.action(action)
        if result["view"]["scene_id"] == "truck_escape":
            state = decode_state(self.token)
            with patch("services.story.time.time", return_value=state["truck_deadline"] / 1000):
                self.action("truck_timeout")
        return self.action("finish_truck_escape")

    def checkpoint(self):
        for action_id in TO_CHECKPOINT:
            self.action(action_id)
        self.assertEqual(decode_state(self.token)["scene_id"], "checkpoint")

    def checkpoint_at(self, score):
        for action_id in TO_CHECKPOINT[:-1]:
            self.action(action_id)
        state = decode_state(self.token)
        state["affinity"] = score
        self.token = encode_state(state)
        return self.action("return_home")

    def chat(self, character, message, attitude="cooperative"):
        turn = {"reply": "알겠습니다.", "visual_cue": "neutral"}
        with patch.object(chatbot.generator, "classify", return_value=attitude), patch.object(chatbot.generator, "generate", return_value=turn):
            response = self.client.post("/api/chat", json={"state_token": self.token, "character_id": character, "message": message})
        self.assertEqual(response.status_code, 200)
        self.token = response.get_json()["state_token"]
        return response.get_json()

    def festival(self, checkpoint_action):
        self.action(checkpoint_action)
        if checkpoint_action == "accept_job":
            self.action("choose_driver")
        self.action("see_karen_off")
        self.action("go_festival")
        self.action("inspect_food")
        self.assertEqual(decode_state(self.token)["scene_id"], "hair_found")
        self.action("begin_final_choice")

    def test_charles_first_greeting_and_early_questions_keep_jimmy_belief_public(self):
        started = self.client.post("/api/session", json={"player_name": "알렉스", "gender": "female"}).get_json()
        self.token = started["state_token"]
        greeting = started["events"][0]["text"]
        self.assertNotIn("찰스", greeting)
        self.assertEqual(started["view"]["scene_id"], "arrival")
        self.assertNotIn("실종", greeting)
        initial_lines = decode_state(self.token)["scene_events"]
        self.assertIn("내 친구 찰스가 지난주에 마을을 떠나서 외로웠던 참이었어!", initial_lines[0]["text"])
        self.assertEqual(initial_lines[1]["text"], greeting.removeprefix("안녕, 알렉스! "))
        turns = [
            {"reply": "찰스는 내 친구야. 지난주 마을을 떠났어.", "visual_cue": "neutral"},
            {"reply": "왜 떠났는지는 나도 몰라.", "visual_cue": "neutral"},
        ]
        with patch.object(chatbot.generator, "classify", return_value="neutral"), patch.object(chatbot.generator, "generate", side_effect=turns) as generate:
            for question in ("찰스가 누구야?", "왜 떠났어?"):
                response = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "jimmy", "message": question})
                self.assertEqual(response.status_code, 200)
                self.token = response.get_json()["state_token"]
        first, second = (call.args for call in generate.call_args_list)
        self.assertIn("찰스는 지미의 친구", first[3][0].content)
        self.assertIn("지난주 마을을 떠났다고 알고", first[3][0].content)
        self.assertIn("떠난 이유와 행선지는 모른다", first[3][0].content)
        self.assertEqual(first[7], initial_lines)
        self.assertIn("찰스는 내 친구야", second[4][-1]["content"])
        for args in (first, second):
            self.assertNotIn("실종", str((args[2], args[3], args[7], args[8])))
            self.assertNotIn("화로", str((args[2], args[3], args[7], args[8])))

    def test_low_affinity_goes_to_butcher_death_without_festival(self):
        checkpoint = self.checkpoint_at(64)
        state = decode_state(self.token)
        self.assertEqual(state["affinity"], 64)
        self.assertEqual(state["story_day"], 4)
        self.assertIsNone(state["ending"])
        self.assertFalse(state["has_car_key"])
        self.assertEqual([person["id"] for person in checkpoint["view"]["available_characters"]], ["karen"])
        self.assertEqual([action["id"] for action in checkpoint["view"]["available_actions"]], ["go_butcher"])
        self.assertIn("정육점", checkpoint["events"][0]["text"])
        self.assertNotIn("식인", " ".join(item["text"] for item in checkpoint["events"]))
        with patch.object(chatbot.generator, "classify", return_value="neutral"), patch.object(
            chatbot.generator, "generate", return_value={"reply": "정육점에서 뵐게요.", "visual_cue": "neutral"}
        ) as generate:
            response = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "karen", "message": "왜 부르셨어요?"})
        self.assertEqual(response.status_code, 200)
        self.token = response.get_json()["state_token"]
        self.assertIn("정육점으로 오라고 불렀다", generate.call_args.args[-1][0])
        self.assertNotIn("식인", " ".join(generate.call_args.args[-1]))
        self.chat("karen", "고마워요", "friendly")
        self.assertGreaterEqual(decode_state(self.token)["affinity"], 65)
        self.assertEqual([action["id"] for action in available_actions(decode_state(self.token))], ["go_butcher"])
        result = self.action("go_butcher")
        self.assertEqual(result["view"]["ending"], "death")
        self.assertEqual(decode_state(self.token)["story_day"], 4)
        self.assertEqual(result["view"]["today"], checkpoint["view"]["today"])
        self.assertEqual(result["view"]["location_id"], "butcher_shop")
        self.assertIsNone(result["events"][0]["image"])
        self.assertIn("캐런의 부름", result["events"][0]["text"])
        self.assertEqual(decode_state(self.token)["journal"][-1], result["events"][0]["text"])
        self.assertFalse(decode_state(self.token)["has_car_key"])
        self.assertNotIn("jimmy_hair", decode_state(self.token)["clues"])
        self.assertEqual(result["view"]["available_actions"], [])
        self.assertEqual(result["view"]["available_characters"], [])
        for forbidden in ("continue_festival", "go_festival", "inspect_food"):
            response = self.client.post("/api/action", json={"state_token": self.token, "action_id": forbidden})
            self.assertEqual(response.status_code, 409)

    def test_final_choice_deadline_is_server_owned_and_late_choices_die_even_with_key(self):
        for action, moment, ending in (("escape", 1009.999, None), ("stay",1009.999,"assimilation"),
                                       ("escape",1010,"death"), ("stay",1010,"death"), ("choice_timeout",1010,"death")):
            with self.subTest(action=action,moment=moment):
                state=decode_state(self.token)
                state.update(scene_id="hair_found",location_id="square",ending=None,has_car_key=True)
                self.token=encode_state(state)
                self.assertIsNone(self.client.post('/api/session/resume',json={"state_token":self.token}).get_json()["view"]["choice_deadline"])
                with patch('services.story.time.time',return_value=1000):
                    opened=self.action('begin_final_choice')
                self.assertEqual(opened['view']['choice_deadline'],1010000)
                self.assertEqual(opened['view']['available_characters'],[])
                with patch('services.story.time.time',return_value=moment):
                    self.assertEqual(self.action(action)['view']['ending'],ending)
                self.assertIsNone(self.client.post('/api/session/resume',json={"state_token":self.token}).get_json()['view']['choice_deadline'])

    def test_truck_deadline_job_key_and_locked_retries_are_server_owned(self):
        for gender in ("male", "female"):
            for job, key, moment, success in (("driver", True, 1011.999, True), ("driver", True, 1012, False),
                                             ("gardener", False, 1005, False), (None, False, 1005, False),
                                             ("gardener", True, 1005, False), ("driver", False, 1005, False)):
                with self.subTest(gender=gender, job=job, moment=moment):
                    state = decode_state(self.token)
                    state.update(scene_id="final_choice", ending=None, gender=gender, job=job, has_car_key=key, choice_deadline=1010000)
                    self.token = encode_state(state)
                    with patch("services.story.time.time", return_value=1000):
                        truck = self.action("escape")
                    self.assertEqual(truck["view"]["scene_id"], "truck_escape")
                    self.assertIsNone(truck["view"]["truck_deadline"])
                    self.assertIsNone(truck["view"]["ending"])
                    self.assertTrue(truck["view"]["background"].endswith("ending_truck.png"))
                    with patch("services.story.time.time", return_value=1002):
                        armed = self.action("begin_truck_escape")
                        self.assertEqual(armed["view"]["truck_deadline"], 1012000)
                        for action in ("begin_truck_escape", "truck_timeout"):
                            self.assertEqual(self.client.post("/api/action", json={"state_token": self.token,"action_id": action}).status_code,409)
                    with patch("services.story.time.time", return_value=moment):
                        opened = self.action("open_truck_door")
                        if not success and moment < 1012:
                            self.assertEqual(opened["view"]["scene_id"], "truck_escape")
                            self.assertIn("잠겨", opened["events"][0]["text"])
                            for _ in range(2):
                                retried = self.action("open_truck_door")
                                self.assertEqual(retried["view"]["truck_deadline"], 1012000)
                                self.assertIsNone(retried["view"]["ending"])
                    if opened["view"]["scene_id"] == "truck_escape":
                        with patch("services.story.time.time", return_value=1012):
                            self.action("truck_timeout")
                    elif success:
                        self.assertIn("차 키로 열었다", opened["events"][0]["text"])
                    with patch("services.story.time.time", return_value=2000):
                        ending = self.action("finish_truck_escape")
                    self.assertEqual(ending["view"]["ending"], "escape" if success else "death")
                    self.assertEqual(ending["view"]["gender"], gender)

    def test_timeout_cannot_be_submitted_early_and_decision_cannot_be_started_twice(self):
        state=decode_state(self.token);state.update(scene_id='hair_found',location_id='square')
        self.token=encode_state(state)
        with patch('services.story.time.time',return_value=1000):
            self.action('begin_final_choice')
            for action in ('choice_timeout','begin_final_choice'):
                self.assertEqual(self.client.post('/api/action',json={"state_token":self.token,"action_id":action}).status_code,409)

    def test_threshold_and_high_affinity_job_choices(self):
        checkpoint = self.checkpoint_at(65)
        self.assertEqual([action["id"] for action in checkpoint["view"]["available_actions"]], ["accept_job", "decline_job"])
        self.action("decline_job")
        invitation = self.action("see_karen_off")
        self.assertIn("내일 마을 축제", invitation["events"][-1]["text"])
        self.assertEqual(invitation["view"]["scene_id"], "festival_invite")
        self.action("go_festival")
        self.action("inspect_food")
        self.action("begin_final_choice")
        self.assertFalse(decode_state(self.token)["has_car_key"])
        self.assertEqual(self.escape_through_truck()["view"]["ending"], "death")

    def test_cooperative_chat_unlocks_job_and_key_then_escape(self):
        self.chat("jimmy", "마을을 안내해 줘. 나도 도울게")
        for action_id in TO_CHECKPOINT:
            self.action(action_id)
            state = decode_state(self.token)
            characters = available_characters(state)
            if characters and state["scene_id"] != "checkpoint":
                self.chat(characters[0], f"{characters[0]}의 {state['scene_id']}에서 제가 도울게요")
        self.assertEqual(decode_state(self.token)["affinity"], 80)
        self.assertTrue(decode_state(self.token)["job_offered"])
        self.festival("accept_job")
        self.assertTrue(decode_state(self.token)["has_car_key"])
        self.assertEqual(self.escape_through_truck()["view"]["ending"], "escape")

    def test_gardener_has_profession_without_truck_key(self):
        self.checkpoint_at(65)
        choices = self.action("accept_job")
        self.assertEqual(choices["view"]["scene_id"], "job_choice")
        self.assertIsNone(choices["view"]["job"])
        self.assertEqual([item["id"] for item in choices["view"]["available_actions"]],
                         ["choose_gardener", "choose_driver"])
        result = self.action("choose_gardener")
        state = decode_state(self.token)
        self.assertEqual((state["job"], state["affinity"], state["has_car_key"]), ("gardener", 70, False))
        self.assertEqual(result["view"]["job"], "gardener")
        self.assertIn("직업 획득: 정원사", result["view"]["journal"])
        self.assertEqual(result["view"]["available_characters"], [])
        self.assertEqual(result["events"][0]["speaker_id"], "karen")
        self.assertIn("축하", result["events"][0]["text"])
        for invalid in ("choose_gardener", "choose_driver", "go_festival"):
            self.assertEqual(self.client.post("/api/action", json={"state_token": self.token, "action_id": invalid}).status_code, 409)
        invitation = self.action("see_karen_off")
        self.assertEqual(invitation["events"][0]["speaker_id"], "bob")
        self.action("go_festival")
        self.action("inspect_food")
        self.action("begin_final_choice")
        self.assertEqual(self.escape_through_truck()["view"]["ending"], "death")

    def test_declining_keeps_profession_and_key_empty(self):
        self.checkpoint_at(65)
        result = self.action("decline_job")
        state = decode_state(self.token)
        self.assertEqual((state["job"], state["affinity"], state["has_car_key"]), (None, 65, False))
        self.assertIsNone(result["view"]["job"])
        self.assertEqual(result["view"]["scene_id"], "job_result")
        self.assertIn("서두르실 필요", result["events"][0]["text"])
        self.assertEqual(result["events"][0]["speaker_id"], "karen")

    def test_everyday_conversation_can_reach_job_offer(self):
        self.chat("jimmy", "지미, 안녕하세요", "friendly")
        for action_id in TO_CHECKPOINT:
            self.action(action_id)
            state = decode_state(self.token)
            characters = available_characters(state)
            if characters and state["scene_id"] != "checkpoint":
                self.chat(characters[0], f"{characters[0]}의 {state['scene_id']}에서 만나 반가워요", "friendly")
        state = decode_state(self.token)
        self.assertEqual(state["affinity"], 73)
        self.assertTrue(state["job_offered"])
        self.assertIn("accept_job", [item["id"] for item in available_actions(state)])

    def test_frightened_jimmy_only_answers_ellipsis_then_leaves_in_a_hurry(self):
        for action in TO_CHECKPOINT[:TO_CHECKPOINT.index("approach_jimmy")]:
            data = self.action(action)
        self.assertEqual(data["events"][0]["text"], "...")
        with patch.object(chatbot.generator, "classify", return_value="neutral"), patch.object(chatbot.generator, "generate") as generate:
            answer = self.client.post("/api/chat", json={"state_token":self.token,"character_id":"jimmy","message":"무슨 일이야?"}).get_json()
        generate.assert_not_called()
        self.assertEqual(answer["events"][0]["text"], "...")
        self.token = answer["state_token"]
        left = self.action("approach_jimmy")
        self.assertEqual(left["events"][0]["text"], "(지미가 급하게 나갔다)")
        self.assertEqual(left["view"]["available_characters"], [])

    def test_continued_hostility_path_has_no_job_offer(self):
        self.chat("jimmy", "적대 arrival", "hostile")
        for action_id in TO_CHECKPOINT:
            self.action(action_id)
            state = decode_state(self.token)
            characters = available_characters(state)
            if characters and state["scene_id"] != "checkpoint":
                self.chat(characters[0], f"적대 {state['scene_id']} {characters[0]}", "hostile")
        state = decode_state(self.token)
        self.assertEqual(state["affinity"], 0)
        self.assertFalse(state["job_offered"])
        self.assertEqual(state["hostile_streak"], 9)

    def test_staying_assimilates_without_key(self):
        self.checkpoint_at(70)
        self.festival("decline_job")
        self.assertEqual(self.action("stay")["view"]["ending"], "assimilation")

    def test_action_cannot_repeat_and_secret_is_gated(self):
        self.action("visit_neighbors")
        response = self.client.post("/api/action", json={"state_token": self.token, "action_id": "visit_neighbors"})
        self.assertEqual(response.status_code, 409)
        retriever = StoryRetriever()
        self.assertFalse(any("머리카락" in hit.content or "음식의 재료" in hit.content
                             for hit in retriever.search("지미의 머리카락과 고기", "jimmy", "arrival", [])))
        self.assertFalse(any(hit.title == "축제 음식의 정체" for hit in retriever.search("지미 머리카락", "bob", "festival", [])))
        self.assertTrue(any(hit.title == "축제 음식의 정체" for hit in retriever.search("지미 머리카락", "bob", "hair_found", ["jimmy_hair"])))
        self.assertFalse(any("다음 주" in hit.content or "내일" in hit.content
                             for hit in retriever.search("축제", "bob", "neighbors", [])))
        self.assertTrue(any("다음 날" in hit.content for hit in retriever.search("축제", "bob", "festival_invite", [])))
        self.assertFalse(any("오후 6시" in hit.content for hit in retriever.search("약속", "jimmy", "arrival", [])))
        self.assertTrue(any("오후 6시" in hit.content for hit in retriever.search("약속", "jimmy", "dinner_invite", ["brazier"])))

    def test_place_has_one_character_and_affinity_is_shared_with_bob(self):
        start = self.client.post("/api/session", json={"player_name": "검증", "gender": "male"}).get_json()["view"]
        self.assertEqual((start["location_name"], start["affinity"]), ("새집", 50))
        self.assertEqual(start["available_characters"][0]["id"], "jimmy")
        self.assertEqual(self.action("visit_neighbors")["view"]["available_characters"], [])
        self.assertEqual(self.action("visit_karen")["view"]["available_characters"][0]["id"], "karen")
        with patch.object(chatbot.generator, "classify", return_value="hostile"), patch.object(chatbot.generator, "generate", return_value={"reply": "그 얘기는 불편하군요.", "visual_cue": "worried"}):
            response = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "karen", "message": "당신을 가만두지 않겠어요"})
        self.assertEqual(response.status_code, 200)
        self.token = response.get_json()["state_token"]
        self.assertEqual(response.get_json()["view"]["affinity"], 48)
        bob = self.action("visit_bob")
        self.assertEqual(bob["view"]["location_name"], "정육점")
        self.assertEqual([person["id"] for person in bob["view"]["available_characters"]], ["bob"])
        self.assertIn("필요한 게", bob["events"][0]["text"])
        with patch.object(chatbot.generator, "classify", return_value="neutral"), patch.object(chatbot.generator, "generate", return_value={"reply": "어서 오시오.", "visual_cue": "neutral"}) as generate:
            response = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "bob", "message": "가게는 언제 열어요?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate.call_args.args[6], 48)

    def test_same_reply_uses_new_attitude_at_both_boundaries(self):
        state = decode_state(self.token)
        state["affinity"] = 69
        self.token = encode_state(state)
        with patch.object(chatbot.generator, "classify", return_value="friendly"), patch.object(chatbot.generator, "generate", return_value={"reply": "반가워!", "visual_cue": "smile"}) as generate:
            result = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "jimmy", "message": "안녕하세요"}).get_json()
        self.assertEqual(result["view"]["affinity"], 72)
        self.assertEqual(generate.call_args.args[6], 72)
        self.token = result["state_token"]

        self.action("visit_neighbors")
        self.action("visit_karen")
        state = decode_state(self.token)
        state["affinity"] = 35
        self.token = encode_state(state)
        with patch.object(chatbot.generator, "classify", return_value="hostile"), patch.object(chatbot.generator, "generate", return_value={"reply": "어서 오세요.", "visual_cue": "smile"}) as generate, patch.object(chatbot.image_selector, "select", return_value="/assets/images/karen_smile.png") as select:
            result = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "karen", "message": "협박하겠어요"}).get_json()
        self.assertEqual(result["view"]["affinity"], 33)
        self.assertEqual(generate.call_args.args[6], 33)
        self.assertEqual(select.call_args.args, ("어서 오세요.", "karen", "neighbors", "smile"))
        self.assertEqual(result["events"][0]["image"], "/assets/images/karen_smile.png")

    def test_revisiting_neighbor_does_not_repeat_fixed_greeting(self):
        self.action("visit_neighbors")
        self.assertTrue(self.action("visit_karen")["events"])
        self.action("visit_bob")
        revisit = self.action("visit_karen")
        self.assertEqual(revisit["events"], [])
        self.assertEqual(decode_state(self.token)["scene_events"], [])

    def test_each_character_remembers_only_own_conversation(self):
        self.action("visit_neighbors")
        self.action("visit_karen")
        turn = {"reply": "기억하고 있어요.", "visual_cue": "neutral"}
        with patch.object(chatbot.generator, "classify", return_value="neutral"), patch.object(chatbot.generator, "generate", return_value=turn) as generate:
            for character, message in (("karen", "제 이름은 알렉스예요"), ("bob", "고기가 있나요?"), ("karen", "제 이름을 기억하나요?")):
                if character == "bob":
                    self.action("visit_bob")
                elif message.startswith("제 이름을"):
                    self.action("visit_karen")
                response = self.client.post("/api/chat", json={"state_token": self.token, "character_id": character, "message": message})
                self.assertEqual(response.status_code, 200)
                self.token = response.get_json()["state_token"]
        self.assertEqual(generate.call_args_list[1].args[4], [])
        self.assertEqual(generate.call_args_list[2].args[4][0]["content"], "제 이름은 알렉스예요")
        self.assertEqual(decode_state(self.token)["history"]["bob"][0]["content"], "고기가 있나요?")

    def test_jimmy_leaves_before_karen_arrives(self):
        for action_id in TO_CHECKPOINT[:6]:
            self.action(action_id)
        self.assertEqual(decode_state(self.token)["location_id"], "salon")
        for action_id in ("choose_shampoo", "choose_scissors", "choose_comb"):
            self.action(action_id)
        result = self.action("help_cathy")
        self.assertIn("정확해요", result["events"][0]["text"])
        jimmy = self.action("return_home")
        self.assertEqual(jimmy["view"]["location_id"], "player_house")
        self.assertEqual([person["id"] for person in jimmy["view"]["available_characters"]], ["jimmy"])
        self.assertEqual([item["id"] for item in jimmy["view"]["available_actions"]], ["see_jimmy_off"])
        self.assertEqual([item["speaker_id"] for item in jimmy["events"]], ["thought", "jimmy"])
        self.assertIn("정육점", jimmy["events"][1]["text"])
        self.assertEqual([item["speaker_id"] for item in decode_state(self.token)["scene_events"]], ["jimmy"])
        self.chat("jimmy", "정육점에는 왜 가요?", "neutral")
        karen = self.action("see_jimmy_off")
        self.assertEqual([person["id"] for person in karen["view"]["available_characters"]], ["karen"])
        self.assertEqual([item["id"] for item in karen["view"]["available_actions"]], ["go_butcher"])
        self.assertEqual([item["speaker_id"] for item in karen["events"]], ["thought", "karen"])
        self.assertIn("지미가 떠난 뒤", karen["events"][0]["text"])
        self.assertEqual([item["speaker_id"] for item in decode_state(self.token)["scene_events"]], ["karen"])

    def test_cathy_basket_checks_exact_tools_and_failure_continues(self):
        for action_id in TO_CHECKPOINT[:6]:
            self.action(action_id)
        request = decode_state(self.token)
        self.assertEqual(request["scene_id"], "cathy_help")
        self.assertEqual(request["cathy_tools"], [])
        self.assertEqual(available_characters(request), [])
        before = request["affinity"]
        self.action("choose_shampoo")
        self.action("choose_shampoo")
        self.assertEqual(decode_state(self.token)["cathy_tools"], [])
        self.action("choose_shampoo")
        self.action("choose_scissors")
        self.action("choose_comb")
        self.action("choose_conditioner")
        failed = self.action("help_cathy")
        self.assertEqual(failed["view"]["scene_id"], "cathy_result")
        self.assertEqual(failed["view"]["affinity"], before)
        self.assertIn("집에 가세요", failed["events"][0]["text"])
        self.assertEqual([a["id"] for a in failed["view"]["available_actions"]], ["return_home"])
        self.assertEqual(self.client.post("/api/action", json={"state_token": self.token, "action_id": "help_cathy"}).status_code, 409)
        self.assertEqual(self.action("return_home")["view"]["scene_id"], "jimmy_butcher")

    def test_cathy_basket_success_adds_five_once(self):
        for action_id in TO_CHECKPOINT[:6]:
            self.action(action_id)
        before = decode_state(self.token)["affinity"]
        for tool in ("shampoo", "scissors", "comb"):
            self.action(f"choose_{tool}")
        result = self.action("help_cathy")
        self.assertEqual(result["view"]["affinity"], min(100, before + 5))
        self.assertIn("고마워요", result["events"][0]["text"])

    def test_cathy_tools_match_illustration_and_old_dryer_is_rejected(self):
        for action_id in TO_CHECKPOINT[:6]:
            data = self.action(action_id)
        tools = {"shampoo", "scissors", "conditioner", "comb", "spray", "serum", "brush", "mirror", "towel", "roller"}
        self.assertIn("지금 너무 바쁘니까", data["events"][0]["text"])
        self.assertIn("샴푸, 가위, 빗", data["events"][1]["text"])
        self.assertEqual({a["id"] for a in data["view"]["available_actions"]}, {f"choose_{tool}" for tool in tools} | {"help_cathy"})
        rejected = self.client.post("/api/action", json={"state_token": self.token, "action_id": "choose_dryer"})
        self.assertEqual(rejected.status_code, 409)
        before = data["view"]["affinity"]
        for tool in tools:
            self.action(f"choose_{tool}")
            self.action(f"choose_{tool}")
        self.assertEqual(decode_state(self.token)["cathy_tools"], [])
        self.assertEqual(decode_state(self.token)["affinity"], before)

    def test_butcher_visit_reason_and_karen_request_reach_model(self):
        for action_id in TO_CHECKPOINT[:11]:
            self.action(action_id)
        with patch.object(chatbot.generator, "classify", return_value="neutral"), patch.object(chatbot.generator, "generate", return_value={"reply": "고기를 사러 가.", "visual_cue": "neutral"}) as generate:
            self.client.post("/api/chat", json={"state_token": self.token, "character_id": "jimmy", "message": "왜 정육점에 가요?"})
        self.assertIn("고기를 사러", " ".join(generate.call_args.args[-1]))
        self.assertIn("아직 지하실의 비밀을 모른다", generate.call_args.args[-1][1])
        self.assertNotIn("식인", " ".join(generate.call_args.args[-1]))
        self.action("see_jimmy_off")
        with patch.object(chatbot.generator, "classify", return_value="neutral"), patch.object(chatbot.generator, "generate", return_value={"reply": "지미에게 전할 말이 있어요.", "visual_cue": "neutral"}) as generate:
            unseen = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "karen", "message": "무슨 용건이세요?"})
        self.assertEqual(unseen.status_code, 200)
        self.token = unseen.get_json()["state_token"]
        self.assertFalse(decode_state(self.token)["jimmy_destination_told"])
        self.assertNotIn("정육점", generate.call_args.args[-1][0])
        self.assertIn("행선지를 아직 모른다", generate.call_args.args[-1][1])
        self.assertEqual(generate.call_args.args[-2][0]["speaker_id"], "karen")
        with patch.object(chatbot.generator, "classify", return_value="neutral"), patch.object(chatbot.generator, "generate", return_value={"reply": "알려주셔서 고마워요. 그쪽에서 찾아봐 주시겠어요?", "visual_cue": "smile"}) as generate:
            informed = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "karen", "message": "지미가 정육점에 간다고 했어요."})
        self.assertEqual(informed.status_code, 200)
        self.token = informed.get_json()["state_token"]
        self.assertTrue(decode_state(self.token)["jimmy_destination_told"])
        self.assertIn("처음 들었다", generate.call_args.args[-1][1])
        self.assertIn("정육점 쪽에서 찾아봐 달라고", generate.call_args.args[-1][1])
        self.assertIn("캐런도 모른다", generate.call_args.args[-1][2])
        with patch.object(chatbot.generator, "classify", return_value="neutral"), patch.object(chatbot.generator, "generate", return_value={"reply": "함께 찾아봐 주세요.", "visual_cue": "neutral"}) as generate:
            later = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "karen", "message": "제가 찾아볼게요."})
        self.assertEqual(later.status_code, 200)
        self.assertIn("말을 들었다", generate.call_args.args[-1][1])
        self.assertNotIn("처음 들었다", generate.call_args.args[-1][1])

    def test_wallet_reveals_are_ordered_and_idempotent(self):
        for action_id in TO_CHECKPOINT[:TO_CHECKPOINT.index("inspect_wallet")]:
            self.action(action_id)
        self.assertTrue(self.action("inspect_wallet")["view"]["background"].endswith("basement_wallet.png"))
        self.assertEqual(self.client.post("/api/action", json={"state_token": self.token, "action_id": "inspect_wallet_photo"}).status_code, 409)
        self.action("open_wallet")
        photo = self.action("inspect_wallet_photo")
        self.assertEqual(photo["events"][0]["text"], "지미…랑 옆에는 누구지…?")
        self.action("inspect_wallet")
        self.action("open_wallet")
        self.action("inspect_wallet_photo")
        state = decode_state(self.token)
        self.assertEqual(state["clues"].count("wallet_photo"), 1)
        self.assertEqual(len(state["journal"]), 2)
        self.assertEqual(state["scene_id"], "basement")
        self.assertEqual(self.action("go_upstairs")["view"]["scene_id"], "bob_caught")

    def test_brazier_caught_and_photo_exit_are_fixed_events(self):
        for action_id in TO_CHECKPOINT[:14]:
            self.action(action_id)
        before = decode_state(self.token)["affinity"]
        entry = self.action("inspect_basement")
        self.assertEqual(entry["view"]["scene_id"], "basement_entry")
        self.assertEqual([a["id"] for a in entry["view"]["available_actions"]], ["descend_stairs"])
        basement = self.action("descend_stairs")
        self.assertEqual(basement["view"]["affinity"], before)
        self.assertEqual(entry["events"][0]["text"], "뭐가 엄청 어질러져 있네.. 내려가 볼까?")
        self.assertIn("brazier", decode_state(self.token)["clues"])
        self.assertEqual(basement["events"], [])
        self.assertEqual([item["id"] for item in basement["view"]["available_actions"]], ["inspect_wallet"])
        self.assertEqual(self.client.post("/api/action", json={"state_token": self.token, "action_id": "go_upstairs"}).status_code, 409)
        self.assertEqual(self.client.post("/api/action", json={"state_token": self.token, "action_id": "inspect_brazier"}).status_code, 409)
        for action in ["inspect_wallet", "open_wallet", "inspect_wallet_photo"]:
            inspected = self.action(action)
        self.assertEqual(inspected["view"]["affinity"], before)
        self.assertEqual(inspected["view"]["available_actions"][0]["id"], "go_upstairs")
        self.assertEqual(len(decode_state(self.token)["journal"]), 2)
        caught = self.action("go_upstairs")
        self.assertEqual(caught["view"]["affinity"], before - 5)
        self.assertEqual(self.client.post("/api/action", json={"state_token": self.token, "action_id": "go_upstairs"}).status_code, 409)
        self.assertEqual(caught["view"]["available_characters"], [])
        self.assertIn("나가시오", caught["events"][0]["text"])
        self.assertEqual([item["id"] for item in caught["view"]["available_actions"]], ["return_home"])
        rejected = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "bob", "message": "왜요?"})
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(self.action("return_home")["view"]["scene_id"], "dinner_invite")
        for action_id in ("accept_dinner_invite", "go_karen_dinner"):
            self.action(action_id)
        before_photo = decode_state(self.token)["affinity"]
        entered = self.action("inspect_room")
        self.assertEqual(entered["events"], [])
        self.assertEqual(entered["view"]["affinity"], before_photo)
        self.assertEqual([item["id"] for item in entered["view"]["available_actions"]], ["inspect_photo_back", "inspect_charles_photo"])
        self.assertNotIn("jimmy_photo", decode_state(self.token)["clues"])
        self.assertFalse(any("지미의 사진" in note for note in entered["view"]["journal"]))
        self.assertEqual(self.client.post("/api/action", json={"state_token": self.token, "action_id": "return_home"}).status_code, 409)
        photo = self.finish_photo_room()
        self.assertEqual(photo["view"]["affinity"], max(0, before_photo - 5))
        self.assertIn("jimmy_photo", decode_state(self.token)["clues"])
        self.assertEqual(photo["view"]["available_characters"], [])
        self.assertIn("나가 주세요", photo["events"][-1]["text"])
        self.assertEqual([item["id"] for item in photo["view"]["available_actions"]], ["return_home"])
        self.assertEqual(self.client.post("/api/action", json={"state_token": self.token, "action_id": "recognize_photo"}).status_code, 409)
        rejected = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "karen", "message": "사진이네요"})
        self.assertEqual(rejected.status_code, 409)

    def test_six_story_days_advance_at_scene_boundaries_across_calendar_boundaries(self):
        cases = (
            (datetime(2024, 2, 28, 23, 59, tzinfo=ZoneInfo("Asia/Seoul")), ("1955.2.28", "1955.3.1", "1955.3.2", "1955.3.3", "1955.3.4", "1955.3.5")),
            (datetime(2023, 12, 31, 23, 59, tzinfo=ZoneInfo("Asia/Seoul")), ("1955.12.31", "1956.1.1", "1956.1.2", "1956.1.3", "1956.1.4", "1956.1.5")),
            (datetime(2023, 2, 28, 23, 59, tzinfo=ZoneInfo("Asia/Seoul")), ("1955.2.28", "1955.3.1", "1955.3.2", "1955.3.3", "1955.3.4", "1955.3.5")),
        )
        transitions = {("neighbors", "return_home"): 1, ("cathy_result", "return_home"): 2,
                       ("dinner_invite", "accept_dinner_invite"): 3,
                       ("photo_found", "return_home"): 4, ("festival_invite", "go_festival"): 5}
        for started, dates in cases:
            with self.subTest(started=started):
                with patch("services.story.datetime") as clock:
                    clock.now.return_value = started
                    self.setUp()
                    clock.now.assert_called_once_with(ZoneInfo("Asia/Seoul"))
                self.assertEqual(decode_state(self.token)["start_date"], started.date().replace(year=1955).isoformat())
                with patch("services.story.datetime") as later_clock:
                    later_clock.now.return_value = started + timedelta(days=1)
                    self.assertEqual(self.client.post("/api/session/resume", json={"state_token": self.token}).get_json()["view"]["today"], dates[0])
                    later_clock.now.assert_not_called()
                day = 0
                for action_id in TO_CHECKPOINT:
                    if action_id == "return_home" and decode_state(self.token)["scene_id"] == "photo_found":
                        state = decode_state(self.token)
                        state["affinity"] = 70
                        self.token = encode_state(state)
                    scene = decode_state(self.token)["scene_id"]
                    day = transitions.get((scene, action_id), day)
                    self.assertEqual(self.action(action_id)["view"]["today"], dates[day], action_id)
                    self.assertEqual(decode_state(self.token)["story_day"], day, action_id)
                    if (scene, action_id) in transitions:
                        self.assertEqual(self.client.post("/api/action", json={"state_token": self.token, "action_id": action_id}).status_code, 409)
                        self.assertEqual(self.client.post("/api/session/resume", json={"state_token": self.token}).get_json()["view"]["today"], dates[day])
                    if scene == "bob_caught":
                        self.assertEqual(self.chat("jimmy", "내일 데리러 오는 거지?", "neutral")["view"]["today"], dates[day])
                self.assertEqual(self.action("decline_job")["view"]["today"], dates[4])
                self.assertEqual(self.action("see_karen_off")["view"]["today"], dates[4])
                arrived = self.action("go_festival")
                self.assertEqual(arrived["view"]["today"], dates[5])
                self.assertEqual(decode_state(self.token)["story_day"], 5)
                self.assertEqual(self.client.post("/api/action", json={"state_token": self.token, "action_id": "go_festival"}).status_code, 409)
                self.assertEqual(self.action("inspect_food")["view"]["today"], dates[5])

    def test_both_frames_are_required_in_either_order_and_karen_appears_once(self):
        for first in ("jimmy", "charles"):
            with self.subTest(first=first):
                self.setUp()
                for action in TO_CHECKPOINT[:TO_CHECKPOINT.index("inspect_photo_back")]:
                    self.action(action)
                before = decode_state(self.token)["affinity"]
                frames = {"jimmy": ["inspect_photo_back", "recognize_photo"],
                          "charles": ["inspect_charles_photo", "inspect_charles_photo_back", "recognize_charles_photo"]}
                for person in [first, "charles" if first == "jimmy" else "jimmy"]:
                    for action in frames[person]:
                        result = self.action(action)
                        if action == "inspect_charles_photo":
                            self.assertEqual(result["events"][0]["text"], "이 사람은 어제 지갑 속 사진에 있던 사람이잖아..?")
                    if person == first:
                        self.assertEqual(result["events"], [])
                        self.assertEqual(result["view"]["affinity"], before)
                        self.assertFalse(decode_state(self.token)["photo_recognized"])
                        denied = self.client.post("/api/action", json={"state_token": self.token, "action_id": "return_home"})
                        self.assertEqual(denied.status_code, 409)
                self.assertTrue(decode_state(self.token)["photo_recognized"])
                self.assertEqual(result["view"]["affinity"], before - 5)
                self.assertEqual(sum(e["speaker_id"] == "karen" for e in result["events"]), 2)
                self.assertEqual(result["events"][0]["speaker_id"], "karen")
                self.assertFalse(any("벽에 지미와 찰스" in e["text"] for e in result["events"]))
                self.assertEqual([a["id"] for a in result["view"]["available_actions"]], ["return_home"])
                denied = self.client.post("/api/action", json={"state_token": self.token, "action_id": frames[first][-1]})
                self.assertEqual(denied.status_code, 409)

    def test_photo_back_date_is_disclosed_once_only_after_back_inspection(self):
        with patch("services.story.datetime") as clock:
            clock.now.return_value = datetime(2024, 3, 1, 0, 1, tzinfo=ZoneInfo("Asia/Seoul"))
            self.setUp()
        for action_id in TO_CHECKPOINT[:TO_CHECKPOINT.index("inspect_photo_back")]:
            self.action(action_id)
        self.assertEqual(self.client.post("/api/session/resume", json={"state_token": self.token}).get_json()["view"]["today"], "1955.3.4")
        self.assertIsNone(self.client.post("/api/session/resume", json={"state_token": self.token}).get_json()["view"]["photo_back_date"])
        denied = self.client.post("/api/action", json={"state_token": self.token, "action_id": "recognize_photo"})
        self.assertEqual(denied.status_code, 409)
        self.assertNotIn("photo_back_date", decode_state(self.token)["clues"])
        inspected = self.action("inspect_photo_back")
        self.assertEqual(inspected["view"]["photo_back_date"], "1955.3.3")
        self.assertEqual(decode_state(self.token)["journal"][-1].count("1955.3.3"), 1)
        self.assertEqual(self.client.post("/api/action", json={"state_token": self.token, "action_id": "inspect_photo_back"}).status_code, 409)
        self.assertEqual(decode_state(self.token)["clues"].count("photo_back_date"), 1)

    def test_accept_job_fixed_reward_and_cap(self):
        for score in (70, 98):
            with self.subTest(score=score):
                self.setUp()
                self.checkpoint_at(score)
                learned = self.action("accept_job")
                self.assertEqual(learned["view"]["affinity"], score)
                self.assertIsNone(learned["view"]["job"])
                self.assertFalse(decode_state(self.token)["has_car_key"])
                accepted = self.action("choose_driver")
                self.assertEqual(accepted["view"]["affinity"], min(100, score + 5))
                self.assertEqual(accepted["view"]["job"], "driver")
                self.assertIn("고마워요", accepted["events"][0]["text"])
                self.assertTrue(decode_state(self.token)["job_offered"])
                self.assertEqual(self.client.post("/api/action", json={"state_token": self.token, "action_id": "accept_job"}).status_code, 409)
        self.setUp()
        self.checkpoint_at(70)
        self.assertEqual(self.action("decline_job")["view"]["affinity"], 70)

    def test_dinner_pickup_promise_and_festival_inference(self):
        for action_id in TO_CHECKPOINT[:TO_CHECKPOINT.index("return_home", TO_CHECKPOINT.index("go_upstairs"))]:
            self.action(action_id)
        basement = decode_state(self.token)
        self.assertIn("brazier", basement["clues"])
        self.assertNotIn("jimmy_hair", basement["clues"])
        self.assertFalse(any("식인" in entry or "음식의 정체" in entry for entry in basement["journal"]))
        invitation = self.action("return_home")
        self.assertEqual(invitation["view"]["scene_id"], "dinner_invite")
        self.assertEqual([person["id"] for person in invitation["view"]["available_characters"]], ["jimmy"])
        self.assertIn("캐런이 내일 저녁 식사에 초대", invitation["events"][0]["text"])
        self.assertEqual(invitation["events"][0]["text"], "캐런이 내일 저녁 식사에 초대했어.. 같이 가자.. 내일 6시까지 여기로 올게..")
        self.assertIn("데리러", invitation["view"]["available_actions"][0]["label"])
        with patch.object(chatbot.generator, "classify", return_value="friendly"), patch.object(chatbot.generator, "generate", return_value={"reply": "고마워.", "visual_cue": "worried"}) as generate:
            response = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "jimmy", "message": "지미, 멋져요"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate.call_args.kwargs["scene_id"], "dinner_invite")
        wait = self.action("accept_dinner_invite")
        self.assertEqual(wait["events"][0]["text"], "다음 날 7시가 되도록 지미는 나타나지 않았다.")
        self.assertIn("혼자", wait["view"]["available_actions"][0]["label"])
        alone = self.action("go_karen_dinner")
        self.assertEqual(alone["view"]["location_id"], "karen_house")
        self.assertEqual(alone["view"]["available_characters"], [])
        self.assertEqual(alone["events"][0]["speaker_id"], "karen")
        with patch.object(chatbot.generator, "classify") as classify:
            blocked = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "karen", "message": "안녕하세요"})
        self.assertEqual(blocked.status_code, 409)
        classify.assert_not_called()
        self.action("inspect_room")
        self.finish_photo_room()
        state = decode_state(self.token)
        state["affinity"] = 70
        self.token = encode_state(state)
        for action_id in ("return_home", "decline_job", "see_karen_off", "go_festival"):
            self.action(action_id)
        food = self.action("inspect_food")
        self.assertEqual(len(food["events"]), 2)
        self.assertTrue(food["events"][0]["text"].startswith("와… 이게 다 뭐야?"))
        self.assertTrue(food["events"][0]["text"].endswith("어…? 이게 뭐지?"))
        self.assertEqual(len(food["events"][1]["text"].splitlines()), 6)
        self.assertTrue(food["events"][1]["text"].endswith("그럼 지금까지 내가 먹었던 게…"))
        thoughts = " ".join(item["text"] for item in food["events"])
        for detail in ("머리카락", "밥은 머리카락이 없잖아", "지미", "설마", "먹었던 게"):
            self.assertIn(detail, thoughts)
        self.assertEqual([item["id"] for item in food["view"]["available_actions"]], ["begin_final_choice"])

    def test_fixed_scene_line_reaches_ai_without_private_thoughts(self):
        for action_id in TO_CHECKPOINT[:-1]:
            self.action(action_id)
        state = decode_state(self.token)
        self.assertEqual(state["scene_id"], "photo_found")
        self.assertEqual([item["speaker_id"] for item in state["scene_events"]], ["karen", "karen"])
        self.assertIn("제 방에서", state["scene_events"][0]["text"])
        with patch.object(chatbot.generator, "classify") as classify, patch.object(chatbot.generator, "generate") as generate:
            response = self.client.post("/api/chat", json={"state_token": self.token, "character_id": "karen", "message": "왜 놀라셨어요?"})
        self.assertEqual(response.status_code, 409)
        classify.assert_not_called()
        generate.assert_not_called()

    def test_current_incident_context_reaches_each_character_without_forcing_chat(self):
        steps = [
            ("visit_neighbors", None, None),
            ("visit_karen", None, None), ("visit_bob", None, None), ("visit_cathy", None, None),
            ("return_home", "jimmy", "캐시가"),
            ("go_help_cathy", None, None),
            ("choose_shampoo", None, None), ("choose_scissors", None, None), ("choose_comb", None, None),
            ("help_cathy", None, None),
            ("return_home", "jimmy", "고기를 사러 정육점에 다녀오겠다고"),
            ("see_jimmy_off", "karen", "전할 말이 있어"),
            ("go_butcher", "jimmy", "지미는 정육점 지하실에서"),
            ("approach_jimmy", None, None), ("inspect_basement", None, None), ("descend_stairs", None, None), ("inspect_wallet", None, None), ("open_wallet", None, None), ("inspect_wallet_photo", None, None),
            ("go_upstairs", None, None),
            ("return_home", "jimmy", "오후 6시에"),
            ("accept_dinner_invite", None, None), ("go_karen_dinner", None, None),
            ("inspect_room", None, None), ("inspect_photo_back", None, None), ("recognize_photo", None, None),
            ("inspect_charles_photo", None, None), ("inspect_charles_photo_back", None, None), ("recognize_charles_photo", None, None),
            ("return_home", None, None), ("decline_job", None, None), ("see_karen_off", "bob", "초대한 날의 다음 날"),
        ]
        for action_id, character, expected in steps:
            if action_id == "return_home" and decode_state(self.token)["scene_id"] == "photo_found":
                state = decode_state(self.token)
                state["affinity"] = 70
                self.token = encode_state(state)
            result = self.action(action_id)
            if character:
                self.assertTrue(result["view"]["available_actions"], action_id)
                with patch.object(chatbot.generator, "classify", return_value="neutral"), patch.object(chatbot.generator, "generate", return_value={"reply": "글쎄요.", "visual_cue": "neutral"}) as generate:
                    response = self.client.post("/api/chat", json={"state_token": self.token, "character_id": character, "message": "무슨 일이에요?"})
                    self.assertEqual(response.status_code, 200)
                    self.token = response.get_json()["state_token"]
                if action_id == "go_butcher":
                    generate.assert_not_called()
                    self.assertEqual(response.get_json()["events"][0]["text"], "...")
                    continue
                context = generate.call_args.args[-1]
                self.assertIn(expected, " ".join(context), action_id)
                if character != "jimmy" or expected == "고기를 사러 정육점에 다녀오겠다고":
                    self.assertNotIn("식인", " ".join(context), action_id)
                self.assertEqual(result["view"]["available_actions"],
                                 self.client.post("/api/session/resume", json={"state_token": self.token}).get_json()["view"]["available_actions"])
                if action_id == "go_butcher":
                    self.assertIn("식인", context[1])
                    self.assertNotIn("식인", context[0])
                if action_id == "return_home" and character == "jimmy" and "데리러" in expected:
                    self.assertIn("이름과 날짜만", context[0])

    def test_job_offer_is_fixed_when_later_chat_lowers_affinity(self):
        state = decode_state(self.token)
        state["affinity"] = 75
        self.token = encode_state(state)
        self.checkpoint()
        self.assertEqual(decode_state(self.token)["affinity"], 70)
        for index in range(3):
            response = self.chat("karen", f"당신을 가만두지 않겠어요 {index}", "hostile")
        self.assertEqual(response["view"]["affinity"], 58)
        self.assertIn("accept_job", [action["id"] for action in response["view"]["available_actions"]])
        self.action("accept_job")
        self.assertTrue(decode_state(self.action("choose_driver")["state_token"])["has_car_key"])

    def test_adjustment_center_edges_rounding_and_bounds(self):
        self.assertEqual(START_SCORE, 50)
        self.assertEqual(CHAT_DELTAS, {"friendly": 5, "cooperative": 7, "neutral": 0, "hostile": -2})
        for score, friendly, cooperative in ((50, 5, 7), (70, 3, 4), (90, 1, 1), (0, 5, 7)):
            self.assertEqual(adjusted_affinity(score, 5) - score, friendly)
            self.assertEqual(adjusted_affinity(score, 7) - score, cooperative)
        self.assertEqual(adjusted_affinity(0, -2), 0)
        self.assertEqual(adjusted_affinity(100, 5), 100)
        self.assertEqual(adjusted_affinity(100, -6), 94)
        self.assertEqual(adjusted_affinity(99, 7), 99)  # Rounded zero stays zero.

    def test_neutral_duplicate_and_positive_tiers(self):
        self.assertEqual(self.chat("jimmy", "네", "neutral")["view"]["affinity"], 50)
        self.assertEqual(self.chat("jimmy", "네", "friendly")["view"]["affinity"], 50)
        self.assertEqual(self.chat("jimmy", "안녕하세요", "friendly")["view"]["affinity"], 55)
        self.assertEqual(self.chat("jimmy", "안녕하세요", "friendly")["view"]["affinity"], 55)
        self.assertEqual(self.chat("jimmy", "도울게")["view"]["affinity"], 57)
        self.assertEqual(self.chat("jimmy", "다른 일도 도울게")["view"]["affinity"], 57)
        self.action("visit_neighbors")
        self.action("visit_karen")
        self.assertEqual(self.chat("karen", "  안녕하세요  ", "friendly")["view"]["affinity"], 57)
        state = decode_state(self.token)
        state["scored_chat"] = [f"earlier:{n}" for n in range(12)] + state["scored_chat"]
        self.token = encode_state(state)
        self.assertEqual(self.chat("karen", "다른 일을 돕겠습니다")["view"]["affinity"], 63)

    def test_hostile_streak_recovery_duplicates_and_scene_cap(self):
        self.assertEqual(self.chat("jimmy", "꺼져 1", "hostile")["view"]["affinity"], 48)
        self.assertEqual(self.chat("jimmy", "꺼져 2", "hostile")["view"]["affinity"], 44)
        self.assertEqual(self.chat("jimmy", "꺼져 2", "hostile")["view"]["affinity"], 44)
        self.assertEqual(decode_state(self.token)["hostile_streak"], 2)
        self.assertEqual(self.chat("jimmy", "고마워요", "friendly")["view"]["affinity"], 49)
        self.assertEqual(decode_state(self.token)["hostile_streak"], 1)
        self.assertEqual(self.chat("jimmy", "꺼져 3", "hostile")["view"]["affinity"], 45)
        self.assertEqual(self.chat("jimmy", "꺼져 4", "hostile")["view"]["affinity"], 45)
        self.assertEqual(decode_state(self.token)["hostile_streak"], 2)
        self.assertEqual(self.chat("jimmy", "네", "neutral")["view"]["affinity"], 45)
        self.assertEqual(decode_state(self.token)["hostile_streak"], 2)
        self.assertEqual(self.chat("jimmy", "도와드릴게요", "cooperative")["view"]["affinity"], 47)
        self.assertEqual(decode_state(self.token)["hostile_streak"], 1)

    def test_zero_score_hostility_does_not_advance_streak(self):
        state = decode_state(self.token)
        state["affinity"] = 0
        self.token = encode_state(state)
        self.assertEqual(self.chat("jimmy", "꺼져", "hostile")["view"]["affinity"], 0)
        self.assertEqual(decode_state(self.token)["hostile_streak"], 0)
        self.assertEqual(self.chat("jimmy", "고마워요", "friendly")["view"]["affinity"], 5)
        self.assertEqual(self.chat("jimmy", "나가", "hostile")["view"]["affinity"], 3)
        self.assertEqual(decode_state(self.token)["hostile_streak"], 1)

    def test_fixed_actions_do_not_change_hostile_streak(self):
        self.chat("jimmy", "꺼져", "hostile")
        state = decode_state(self.token)
        self.assertEqual(state["hostile_streak"], 1)
        for action_id in TO_CHECKPOINT[:11]:
            self.action(action_id)
        self.assertEqual(decode_state(self.token)["hostile_streak"], 1)

    def test_legacy_token_keeps_duplicate_record(self):
        self.chat("jimmy", "꺼져", "hostile")
        state = decode_state(self.token)
        state.pop("hostile_streak")
        state.pop("positive_scores")
        state["scored_chat"] = ["arrival:jimmy:suspicious"]
        state["scored_messages"] = ["꺼져"]
        self.token = encode_state(state)
        self.assertEqual(self.chat("jimmy", "꺼져", "hostile")["view"]["affinity"], 48)
        self.assertEqual(decode_state(self.token).get("hostile_streak", 0), 0)


if __name__ == "__main__":
    unittest.main()
