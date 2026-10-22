const offline = document.querySelector("#offline");
const config = document.querySelector("#config");
const loginForm = document.querySelector("#login-form");
const keyInput = document.querySelector("#key");
const sessionOn = document.querySelector("#session-on");
const logout = document.querySelector("#logout");
const composer = document.querySelector("#composer");
const toolsPanel = document.querySelector("#tools");
const toolList = document.querySelector("#tool-list");
const flowForm = document.querySelector("#flow-form");
const components = document.querySelector("#components");
const loading = document.querySelector("#loading");
const empty = document.querySelector("#empty");
const errorBox = document.querySelector("#error");
const result = document.querySelector("#result");
const preview = document.querySelector("#preview");
const gaps = document.querySelector("#gaps");
const steps = document.querySelector("#steps");
const spec = document.querySelector("#spec");

const ERRORS = {
  unauthorized: "인증이 필요합니다. 키는 이 페이지에 저장하지 않습니다.",
  service_not_configured: "서버에 인증키가 없어 호출을 막았습니다.",
  origin_not_allowed: "이 주소에서만 호출할 수 있습니다.",
  offline: "오프라인입니다. 도구를 호출하지 않았습니다.",
  tool_rejected: "도구가 입력을 거절했습니다.",
  tool_failed: "도구 실행에 실패했습니다.",
  invalid_json: "요청 형식이 올바르지 않습니다.",
  body_too_large: "요청이 너무 큽니다.",
  network: "서버에 닿지 못했습니다. 호출 결과는 없습니다.",
};

function showOffline() {
  offline.hidden = navigator.onLine;
}

function field(label, className, value) {
  const wrap = document.createElement("label");
  wrap.textContent = label;
  const input = document.createElement(className === "states" || className === "name" ? "input" : "textarea");
  input.className = className;
  input.value = value || "";
  if (className === "states") input.placeholder = "default, loading, empty, error";
  wrap.append(input);
  return wrap;
}

function addComponent(data) {
  if (components.children.length >= 8) return;
  const card = document.createElement("fieldset");
  card.className = "card component";
  const legend = document.createElement("legend");
  legend.textContent = "구성요소 " + (components.children.length + 1);
  card.append(legend, field("이름", "name", data && data.name), field("역할", "role", data && data.role), field("상태", "states", data && data.states), field("모바일에서의 기대", "mobile", data && data.mobile_behavior), field("동작, 미구현", "interaction", data && data.interaction), field("접근성, 미구현", "accessibility", data && data.accessibility));
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "ghost";
  remove.textContent = "이 구성요소 빼기";
  remove.addEventListener("click", () => {
    if (components.children.length === 1) return;
    card.remove();
    renumber();
  });
  card.append(remove);
  components.append(card);
}

function renumber() {
  [...components.children].forEach((card, index) => {
    card.querySelector("legend").textContent = "구성요소 " + (index + 1);
  });
}

function readComponents() {
  return [...components.querySelectorAll(".component")].map((card) => {
    const value = (name) => card.querySelector("." + name).value.trim();
    const states = value("states").split(",").map((item) => item.trim()).filter(Boolean);
    const component = {
      name: value("name"),
      role: value("role"),
      states,
      mobile_behavior: value("mobile"),
    };
    if (value("interaction")) component.interaction = value("interaction");
    if (value("accessibility")) component.accessibility = value("accessibility");
    return component;
  });
}

function clearResult() {
  result.hidden = true;
  preview.removeAttribute("srcdoc");
  gaps.replaceChildren();
  steps.replaceChildren();
  spec.textContent = "";
}

function showError(error) {
  loading.hidden = true;
  empty.hidden = true;
  result.hidden = true;
  const code = error.code || "network";
  const prefix = ERRORS[code] || ERRORS.network;
  const detail = error.detail && error.detail !== code ? " " + error.detail : "";
  const step = error.step ? " (" + error.step + ")" : "";
  errorBox.textContent = prefix + step + detail;
  errorBox.hidden = false;
  errorBox.scrollIntoView({block: "nearest"});
}

async function api(path, options) {
  options = options || {};
  if (!navigator.onLine) {
    const error = new Error("offline");
    error.code = "offline";
    throw error;
  }
  let response;
  try {
    response = await fetch(path, {
      method: options.method || "GET",
      headers: options.body ? { "content-type": "application/json", accept: "application/json" } : { accept: "application/json" },
      body: options.body,
      credentials: "same-origin",
    });
  } catch (cause) {
    const error = new Error("network");
    error.code = "network";
    throw error;
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || "network");
    error.code = data.error || "network";
    error.step = data.step || "";
    error.detail = data.message || "";
    throw error;
  }
  return data;
}

function setSession(on) {
  loginForm.hidden = on;
  sessionOn.hidden = !on;
  logout.hidden = !on;
  composer.hidden = !on;
  toolsPanel.hidden = !on;
}

function line(text) {
  const item = document.createElement("li");
  item.textContent = text;
  return item;
}

function renderTools(catalog) {
  toolList.replaceChildren();
  const note = document.createElement("p");
  note.className = "help";
  note.textContent = catalog.note || "";
  toolList.append(note);
  Object.entries(catalog.servers || {}).forEach(([server, items]) => {
    const heading = document.createElement("h3");
    heading.textContent = server;
    const list = document.createElement("ul");
    items.forEach((tool) => {
      list.append(line(tool.name + (tool.callable_from_pwa ? " · 이 화면에서 호출" : " · 이 화면에서 호출하지 않음")));
    });
    toolList.append(heading, list);
  });
}

function renderResult(data) {
  errorBox.hidden = true;
  empty.hidden = true;
  loading.hidden = true;
  preview.srcdoc = data.preview_html || "";
  gaps.replaceChildren();
  const handoff = data.handoff || {};
  const unimplemented = handoff.unimplemented || {};
  gaps.append(line("상태: " + (handoff.status || "없음")));
  gaps.append(line("기능 구현 완료: " + String(handoff.functional_ui_complete === true)));
  gaps.append(line("릴리스 승인: " + String(handoff.release_authorized === true)));
  gaps.append(line("사람 검토 필요: " + String(handoff.human_review_required === true)));
  gaps.append(line("시각 검증: " + (handoff.visual_verification || "NOT_RUN")));
  if (handoff.note) gaps.append(line(handoff.note));
  (unimplemented.components || []).forEach((component) => {
    const block = document.createElement("article");
    block.className = "card";
    const title = document.createElement("h3");
    title.textContent = component.name + " · " + (component.implementation || "NOT_IMPLEMENTED");
    const list = document.createElement("ul");
    list.append(line("상태: " + (component.states || []).join(", ")));
    list.append(line("모바일 기대: " + (component.mobile_behavior || "없음")));
    list.append(line("동작: " + (component.interaction || "명세 없음")));
    list.append(line("접근성: " + (component.accessibility || "명세 없음")));
    block.append(title, list);
    gaps.append(block);
  });
  const constraints = data.constraints || {};
  (constraints.state_gaps || []).forEach((gap) => {
    gaps.append(line(gap.component + " 빠진 상태: " + (gap.missing_states || []).join(", ") + " · " + (gap.status || "REVIEW")));
  });
  const layouts = unimplemented.layouts || {};
  Object.entries(layouts).forEach(([viewport, text]) => {
    gaps.append(line(viewport + "px 레이아웃 문구, 미구현: " + text));
  });
  if (data.specification && data.specification.layout_defaults_proposed) {
    gaps.append(line("레이아웃 문구는 본새가 제안한 기본값입니다. 이 화면의 배치가 아닙니다."));
  }
  if (unimplemented.motion) gaps.append(line("모션, 미구현: " + unimplemented.motion));
  if (unimplemented.accessibility) gaps.append(line("접근성, 미구현: " + unimplemented.accessibility));
  steps.replaceChildren();
  (data.steps || []).forEach((step) => {
    steps.append(line(step.server + " / " + step.tool + " / " + step.transport));
  });
  steps.append(line("런타임 스크립트: " + (data.runtime_script || "removed")));
  steps.append(line("품질 모드: " + (data.quality_mode || "advisory") + ", 높은 심각도 " + String(data.high_severity_count)));
  spec.textContent = handoff.ui_spec_json || "";
  result.hidden = false;
  result.scrollIntoView({block: "start"});
}

async function refresh() {
  showOffline();
  try {
    const status = await api("/mobile/api/session");
    config.hidden = status.configured !== false;
    if (status.configured === false) {
      config.textContent = ERRORS.service_not_configured;
      setSession(false);
      return;
    }
    setSession(status.authenticated === true);
    if (status.authenticated) renderTools(await api("/mobile/api/tools"));
  } catch (error) {
    if (error.code !== "offline") showError(error);
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.hidden = true;
  const key = keyInput.value;
  keyInput.value = "";
  try {
    await api("/mobile/api/session", { method: "POST", body: JSON.stringify({ key }) });
    await refresh();
  } catch (error) {
    showError(error);
  }
});

logout.addEventListener("click", async () => {
  clearResult();
  empty.hidden = false;
  try {
    await api("/mobile/api/session", { method: "DELETE" });
  } catch (error) {
    showError(error);
  }
  setSession(false);
  toolList.replaceChildren();
});

document.querySelector("#example").addEventListener("click", () => {
  document.querySelector("#goal").value = "원정 현황을 한 화면에서 확인";
  components.replaceChildren();
  addComponent({
    name: "Energy",
    role: "현재 에너지를 보여 주는 상태 카드",
    states: "default, loading, empty, error",
    mobile_behavior: "390px에서는 최상단에 항상 보이도록 배치",
    interaction: "호스트에서 실시간 에너지 갱신",
    accessibility: "수치와 단위를 함께 제공",
  });
  addComponent({
    name: "Start",
    role: "원정 시작 액션 자리",
    states: "default, disabled",
    mobile_behavior: "터치 가능한 크기 유지",
    interaction: "호스트에서 원정 시작 이벤트 처리",
    accessibility: "키보드로 초점을 받을 수 있어야 함",
  });
});

document.querySelector("#add-component").addEventListener("click", () => addComponent());

flowForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!navigator.onLine) {
    showOffline();
    showError({ code: "offline" });
    return;
  }
  clearResult();
  errorBox.hidden = true;
  empty.hidden = true;
  loading.hidden = false;
  document.querySelector("#run").disabled = true;
  try {
    const data = await api("/mobile/api/flow", {
      method: "POST",
      body: JSON.stringify({
        goal: document.querySelector("#goal").value.trim(),
        preset: document.querySelector("#preset").value,
        components: readComponents(),
      }),
    });
    renderResult(data);
  } catch (error) {
    showError(error);
  } finally {
    loading.hidden = true;
    document.querySelector("#run").disabled = false;
  }
});

window.addEventListener("online", showOffline);
window.addEventListener("offline", showOffline);
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/mobile/sw.js", { scope: "/mobile/" }).catch(() => {});
}
addComponent();
refresh();
