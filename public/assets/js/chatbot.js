const shell = document.querySelector(".story-layout");
const form = document.getElementById("chat-form");
const input = document.getElementById("user-message");
const log = document.getElementById("chat-log");
const actionList = document.getElementById("action-list");
const characterList = document.getElementById("character-list");
const journalList = document.getElementById("journal-list");
const statusMessage = document.getElementById("status-message");
const tokenKey = "new-village-state-v1";
const transcriptKey = "new-village-transcript-v1";
const locationNames = {
  player_house: "새집", karen_house: "캐런의 집", butcher_shop: "정육점",
  salon: "미용실", square: "마을 광장", basement: "정육점 지하실",
};
const endingNames = { escape: "더뉴빌리지 탈출", death: "벽에 걸린 사진", assimilation: "새로운 이웃" };
let stateToken = localStorage.getItem(tokenKey);
let transcript;
try { transcript = JSON.parse(localStorage.getItem(transcriptKey) || "[]"); }
catch { transcript = []; }
let selectedCharacter = null;
let currentView = null;
let busy = false;

function showMessage(speaker, text, image = null, save = true) {
  const item = document.createElement("article");
  item.className = `message ${speaker === "user" ? "user" : "bot"}`;
  const label = document.createElement("strong");
  label.textContent = { jimmy: "지미", karen: "캐런", bob: "밥", cathy: "캐시", narrator: "이야기", thought: "나의 생각", user: "나" }[speaker] || speaker;
  item.append(label);
  if (image) {
    const picture = document.createElement("img");
    picture.src = image;
    picture.alt = `${label.textContent}의 현재 모습`;
    item.append(picture);
  }
  const body = document.createElement("p");
  body.textContent = text;
  item.append(body);
  log.append(item);
  log.scrollTop = log.scrollHeight;
  if (save) {
    transcript.push({ speaker, text, image });
    transcript = transcript.slice(-120);
    localStorage.setItem(transcriptKey, JSON.stringify(transcript));
  }
  return item;
}

function renderView(view) {
  currentView = view;
  document.getElementById("location-title").textContent = locationNames[view.location_id] || view.location_id;
  const background = document.getElementById("scene-background");
  background.style.backgroundImage = view.background ? `url("${view.background}")` : "none";
  background.setAttribute("aria-label", `${locationNames[view.location_id] || view.location_id} 배경`);

  actionList.replaceChildren();
  for (const action of view.available_actions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `action-button ${action.kind}`;
    button.textContent = action.label;
    button.disabled = busy;
    button.addEventListener("click", () => performAction(action.id));
    actionList.append(button);
  }

  if (!view.available_characters.some((item) => item.id === selectedCharacter)) {
    selectedCharacter = view.available_characters[0]?.id || null;
  }
  characterList.replaceChildren();
  for (const character of view.available_characters) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `character-button ${character.id === selectedCharacter ? "active" : ""}`;
    button.textContent = character.name;
    button.disabled = busy;
    button.setAttribute("aria-pressed", character.id === selectedCharacter ? "true" : "false");
    button.addEventListener("click", () => { selectedCharacter = character.id; renderView(currentView); });
    characterList.append(button);
  }
  const selected = view.available_characters.find((item) => item.id === selectedCharacter);
  document.getElementById("character-title").textContent = selected?.name || "이웃을 선택하세요";
  const portrait = document.getElementById("character-portrait");
  portrait.hidden = !selected?.portrait;
  if (selected?.portrait) { portrait.src = selected.portrait; portrait.alt = `${selected.name} 초상`; }

  journalList.replaceChildren();
  for (const note of view.journal) {
    const item = document.createElement("li");
    item.textContent = note;
    journalList.append(item);
  }
  const endingCard = document.getElementById("ending-card");
  endingCard.hidden = !view.ending;
  endingCard.textContent = view.ending ? `ENDING — ${endingNames[view.ending] || view.ending}` : "";
  input.disabled = busy || !selected || !!view.ending;
  document.getElementById("send-btn").disabled = input.disabled;
  input.placeholder = view.ending ? "이야기가 끝났습니다" : selected ? `${selected.name}에게 말을 걸어 보세요` : "먼저 장소를 선택하세요";
}

async function request(path, payload) {
  const response = await fetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error?.message || "요청을 처리하지 못했습니다.");
    error.code = data.error?.code;
    throw error;
  }
  stateToken = data.state_token;
  localStorage.setItem(tokenKey, stateToken);
  for (const item of data.events) showMessage(item.speaker_id, item.text, item.image);
  renderView(data.view);
}

async function performAction(actionId) {
  if (busy) return;
  busy = true;
  renderView(currentView);
  statusMessage.textContent = "이야기가 이어지는 중…";
  try { await request("/api/action", { state_token: stateToken, action_id: actionId }); }
  catch (error) { statusMessage.textContent = error.message; }
  finally {
    busy = false;
    if (currentView) renderView(currentView);
    if (statusMessage.textContent === "이야기가 이어지는 중…") statusMessage.textContent = "";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message || busy || !selectedCharacter || !stateToken) return;
  busy = true;
  renderView(currentView);
  statusMessage.textContent = "답변을 기다리는 중…";
  const userItem = showMessage("user", message);
  try {
    await request("/api/chat", { state_token: stateToken, character_id: selectedCharacter, message });
    input.value = "";
    statusMessage.textContent = "";
  } catch (error) {
    userItem.remove();
    transcript.pop();
    localStorage.setItem(transcriptKey, JSON.stringify(transcript));
    statusMessage.textContent = error.message;
  } finally {
    busy = false;
    if (currentView) renderView(currentView);
    input.focus();
  }
});

document.getElementById("restart-btn").addEventListener("click", async () => {
  if (busy) return;
  busy = true;
  statusMessage.textContent = "새 이야기를 시작하는 중…";
  try {
    const response = await fetch("/api/session", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_name: shell.dataset.playerName || "새 이웃" }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.message || "새 이야기를 시작하지 못했습니다.");
    transcript = [];
    log.replaceChildren();
    localStorage.removeItem(transcriptKey);
    stateToken = data.state_token;
    localStorage.setItem(tokenKey, stateToken);
    for (const item of data.events) showMessage(item.speaker_id, item.text, item.image);
    renderView(data.view);
    statusMessage.textContent = "";
  } catch (error) {
    statusMessage.textContent = error.message;
  } finally {
    busy = false;
    if (currentView) renderView(currentView);
  }
});

async function initialize() {
  statusMessage.textContent = "이야기를 불러오는 중…";
  try {
    if (stateToken) {
      for (const item of transcript) showMessage(item.speaker, item.text, item.image, false);
      await request("/api/session/resume", { state_token: stateToken });
    } else {
      await request("/api/session", { player_name: shell.dataset.playerName || "새 이웃" });
    }
    statusMessage.textContent = "";
  } catch (error) {
    if (stateToken && error.code !== "invalid_state_token") {
      statusMessage.textContent = "이어하기에 실패했습니다. 잠시 후 새로고침해 주세요.";
      return;
    }
    stateToken = null;
    transcript = [];
    localStorage.removeItem(tokenKey);
    localStorage.removeItem(transcriptKey);
    log.replaceChildren();
    statusMessage.textContent = "이전 기록을 열지 못해 새 이야기를 시작합니다.";
    try { await request("/api/session", { player_name: shell.dataset.playerName || "새 이웃" }); }
    catch (error) { statusMessage.textContent = error.message; }
  }
}

initialize();
