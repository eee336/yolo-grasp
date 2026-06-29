const targetClass = document.getElementById("targetClass");
const spatialHint = document.getElementById("spatialHint");
const commandText = document.getElementById("commandText");
const confirmMotion = document.getElementById("confirmMotion");
const planButton = document.getElementById("planButton");
const executeButton = document.getElementById("executeButton");
const refreshButton = document.getElementById("refreshButton");
const statusPill = document.getElementById("statusPill");
const runtimeLine = document.getElementById("runtimeLine");
const objectList = document.getElementById("objectList");
const objectCount = document.getElementById("objectCount");
const planOutput = document.getElementById("planOutput");
const planState = document.getElementById("planState");

let statusTimer = null;

function setStatus(kind, text) {
  statusPill.className = `status-pill ${kind}`;
  statusPill.textContent = text;
}

function formatNumber(value, digits = 3) {
  if (typeof value !== "number" || Number.isNaN(value)) return "--";
  return value.toFixed(digits);
}

function formatVec(values) {
  if (!Array.isArray(values)) return "--";
  return values.map((value) => formatNumber(value)).join(", ");
}

function setTargetOptions(classes) {
  const previous = targetClass.value;
  targetClass.innerHTML = "";
  const auto = document.createElement("option");
  auto.value = "";
  auto.textContent = "auto";
  targetClass.appendChild(auto);

  for (const item of classes || []) {
    const option = document.createElement("option");
    option.value = item.class_name;
    option.textContent = item.class_name;
    targetClass.appendChild(option);
  }
  if ([...targetClass.options].some((option) => option.value === previous)) {
    targetClass.value = previous;
  }
}

function renderObjects(objects) {
  objectList.innerHTML = "";
  objectCount.textContent = String(objects.length);
  if (!objects.length) {
    const empty = document.createElement("div");
    empty.className = "object-item";
    empty.innerHTML = "<strong>No target</strong><span>waiting for detections</span>";
    objectList.appendChild(empty);
    return;
  }

  for (const obj of objects) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "object-item";
    item.innerHTML = `
      <strong>${obj.class_name} · ${formatNumber(obj.confidence, 2)}</strong>
      <span>base: ${formatVec(obj.center_base_m)}</span>
      <span>size: ${formatVec(obj.dimensions_base_m)}</span>
      <span>points: ${obj.point_count}</span>
    `;
    item.addEventListener("click", () => {
      targetClass.value = obj.class_name;
    });
    objectList.appendChild(item);
  }
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    const data = await response.json();
    setTargetOptions(data.classes || []);
    renderObjects(data.objects || []);
    runtimeLine.textContent = `camera: ${data.camera || "--"} · detector: ${data.detector || "--"} · grasp: ${
      data.grasp_mode || "--"
    }`;
    if (data.ok) {
      setStatus("ok", "online");
    } else {
      setStatus("error", "error");
      planOutput.textContent = JSON.stringify({ error: data.error }, null, 2);
    }
  } catch (error) {
    setStatus("error", "offline");
    planOutput.textContent = JSON.stringify({ error: String(error) }, null, 2);
  }
}

function requestPayload(execute) {
  return {
    target_class: targetClass.value || null,
    spatial_hint: spatialHint.value || null,
    command_text: commandText.value.trim() || null,
    execute,
    confirm_motion: confirmMotion.checked,
  };
}

async function submitGrasp(execute) {
  planButton.disabled = true;
  executeButton.disabled = true;
  planState.textContent = execute ? "exec" : "plan";
  try {
    const response = await fetch("/api/grasp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload(execute)),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || JSON.stringify(data));
    }
    planState.textContent = data.executed ? "done" : "ready";
    planOutput.textContent = JSON.stringify(
      {
        executed: data.executed,
        target: data.candidate.target_class,
        hand_profile: data.candidate.hand_profile,
        grasp_pose_base: data.candidate.grasp_pose_base,
        pre_grasp_pose_base: data.candidate.pre_grasp_pose_base,
        retreat_pose_base: data.candidate.retreat_pose_base,
        debug_image: data.debug_image,
        intent: data.intent,
      },
      null,
      2,
    );
    await refreshStatus();
  } catch (error) {
    planState.textContent = "error";
    planOutput.textContent = JSON.stringify({ error: String(error.message || error) }, null, 2);
  } finally {
    planButton.disabled = false;
    executeButton.disabled = false;
  }
}

planButton.addEventListener("click", () => submitGrasp(false));
executeButton.addEventListener("click", () => submitGrasp(true));
refreshButton.addEventListener("click", refreshStatus);

refreshStatus();
statusTimer = window.setInterval(refreshStatus, 1500);

window.addEventListener("beforeunload", () => {
  if (statusTimer) window.clearInterval(statusTimer);
});

