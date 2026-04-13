const state = {
  sessions: [],
  timerSeconds: 25 * 60,
  timerRunning: false,
  timerInterval: null,
  timerPreset: 25,
};

const API_BASE = "";

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value || "";
  return div.innerHTML;
}

function formatDate(dateString) {
  if (!dateString) return "--/--";

  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return "--/--";

  return date.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
  });
}

async function apiFetch(url, options = {}) {
  const config = {
    method: options.method || "GET",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
    ...options,
  };

  const response = await fetch(`${API_BASE}${url}`, config);

  if (!response.ok) {
    let errorMessage = "Erro na requisição.";
    try {
      const errorData = await response.json();
      errorMessage = errorData.error || errorMessage;
    } catch (_) {}
    throw new Error(errorMessage);
  }

  if (response.status === 204) return null;

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  return response.json();
}

async function ensureSetup() {
  try {
    await apiFetch("/setup", { method: "POST" });
  } catch (error) {
    console.warn("Não foi possível executar /setup automaticamente:", error.message);
  }
}

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;

      document.querySelectorAll(".tab-btn").forEach((button) => {
        button.classList.remove("tab-active");
      });

      btn.classList.add("tab-active");

      document.querySelectorAll(".tab-content").forEach((section) => {
        section.classList.add("hidden");
      });

      const selectedTab = document.getElementById(`tab-${tab}`);
      if (selectedTab) {
        selectedTab.classList.remove("hidden");
      }
    });
  });
}

async function loadSessions() {
  try {
    const sessions = await apiFetch("/study-sessions");

    state.sessions = Array.isArray(sessions)
      ? sessions.map((session) => ({
          id: session.id,
          subject: session.subject_name || "Sem matéria",
          topic: session.content_name || "",
          duration: session.duration_minutes || 0,
          created_at:
            session.start_time ||
            session.study_date ||
            new Date().toISOString(),
        }))
      : [];

    renderSessions();
    renderStats();
  } catch (error) {
    console.error("Erro ao carregar sessões:", error.message);
    state.sessions = [];
    renderSessions();
    renderStats();
  }
}

async function handleAddSession(event) {
  event.preventDefault();

  const subjectName = document.getElementById("subject").value.trim();
  const topicName = document.getElementById("topic").value.trim();
  const duration = parseInt(document.getElementById("duration").value, 10) || 0;
  const status = document.getElementById("addStatus");
  const button = document.getElementById("addBtn");

  if (!subjectName || duration <= 0) {
    status.textContent = "Preencha a matéria e a duração corretamente.";
    status.style.color = "#f87171";
    return;
  }

  try {
    button.disabled = true;
    button.textContent = "Salvando...";

    const subject = await findOrCreateSubject(subjectName);
    let contentId = null;

    if (topicName) {
      const content = await findOrCreateContent(topicName, subject.id);
      contentId = content.id;
    }

    const end = new Date();
    const start = new Date(end.getTime() - duration * 60000);

    await apiFetch("/study-sessions", {
      method: "POST",
      body: JSON.stringify({
        subject_id: subject.id,
        content_id: contentId,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
      }),
    });

    document.getElementById("addForm").reset();
    status.textContent = "✓ Sessão registrada!";
    status.style.color = "#4ade80";

    setTimeout(() => {
      status.textContent = "";
    }, 2000);

    await loadSessions();
  } catch (error) {
    console.error("Erro ao salvar sessão:", error.message);
    status.textContent = error.message;
    status.style.color = "#f87171";
  } finally {
    button.disabled = false;
    button.textContent = "Registrar Sessão";
  }
}

async function findOrCreateSubject(name) {
  const subjects = await apiFetch("/subjects");

  const existing = Array.isArray(subjects)
    ? subjects.find(
        (subject) => subject.name.toLowerCase() === name.toLowerCase()
      )
    : null;

  if (existing) return existing;

  return apiFetch("/subjects", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

async function findOrCreateContent(name, subjectId) {
  const contents = await apiFetch(`/contents?subject_id=${subjectId}`);

  const existing = Array.isArray(contents)
    ? contents.find(
        (content) => content.name.toLowerCase() === name.toLowerCase()
      )
    : null;

  if (existing) return existing;

  return apiFetch("/contents", {
    method: "POST",
    body: JSON.stringify({
      name,
      subject_id: subjectId,
    }),
  });
}

function renderSessions() {
  const container = document.getElementById("sessionList");
  const empty = document.getElementById("emptyState");

  const sessions = [...state.sessions].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at)
  );

  empty.style.display = sessions.length === 0 ? "block" : "none";

  container.innerHTML = sessions
    .map(
      (session, index) => `
        <div class="rounded-xl p-4 card-hover fade-in stagger-${(index % 3) + 1} card-surface">
          <div class="flex items-start justify-between gap-3">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1 flex-wrap">
                <span class="text-sm font-semibold">${escapeHtml(session.subject)}</span>
                ${
                  session.topic
                    ? `<span class="text-xs px-2 py-0.5 rounded-full" style="background:#a78bfa22; color:#a78bfa;">${escapeHtml(session.topic)}</span>`
                    : ""
                }
              </div>
              <div class="flex items-center gap-3 text-xs" style="color:#52525b;">
                <span><i data-lucide="clock" class="icon-sm inline-icon"></i> ${session.duration} min</span>
                <span><i data-lucide="calendar" class="icon-sm inline-icon"></i> ${formatDate(session.created_at)}</span>
              </div>
            </div>
          </div>
        </div>
      `
    )
    .join("");

  lucide.createIcons();
}

function renderStats() {
  const total = state.sessions.length;
  const totalMinutes = state.sessions.reduce(
    (sum, session) => sum + (session.duration || 0),
    0
  );
  const subjects = new Set(
    state.sessions.map((session) => session.subject).filter(Boolean)
  );

  document.getElementById("statTotal").textContent = total;
  document.getElementById("statHours").textContent = (totalMinutes / 60).toFixed(1);
  document.getElementById("statCompleted").textContent = 0;
  document.getElementById("statSubjects").textContent = subjects.size;

  const breakdown = document.getElementById("subjectBreakdown");
  const noStats = document.getElementById("noStats");
  noStats.style.display = total === 0 ? "block" : "none";

  const subjectMap = {};
  state.sessions.forEach((session) => {
    if (!session.subject) return;

    if (!subjectMap[session.subject]) {
      subjectMap[session.subject] = 0;
    }

    subjectMap[session.subject] += session.duration || 0;
  });

  const entries = Object.entries(subjectMap);
  const maxMinutes = Math.max(...entries.map(([, minutes]) => minutes), 1);
  const colors = ["#a78bfa", "#f472b6", "#4ade80", "#fbbf24", "#60a5fa", "#f87171"];

  breakdown.innerHTML = entries
    .sort((a, b) => b[1] - a[1])
    .map(
      ([name, minutes], index) => `
        <div>
          <div class="flex justify-between text-xs mb-1">
            <span>${escapeHtml(name)}</span>
            <span style="color:#71717a;">${minutes} min</span>
          </div>
          <div class="w-full rounded-full h-2" style="background:#27272e;">
            <div class="rounded-full h-2 transition-all" style="width:${(minutes / maxMinutes) * 100}%; background:${colors[index % colors.length]};"></div>
          </div>
        </div>
      `
    )
    .join("");
}

function updateTimerDisplay() {
  const minutes = Math.floor(state.timerSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (state.timerSeconds % 60).toString().padStart(2, "0");
  const display = document.getElementById("timerDisplay");

  display.textContent = `${minutes}:${seconds}`;
  display.classList.toggle("timer-pulse", state.timerRunning);
}

function setupTimer() {
  const toggleButton = document.getElementById("timerToggle");
  const resetButton = document.getElementById("timerReset");

  toggleButton.addEventListener("click", () => {
    if (state.timerRunning) {
      clearInterval(state.timerInterval);
      state.timerRunning = false;
      toggleButton.innerHTML =
        '<i data-lucide="play" class="icon-sm inline-icon"></i> Iniciar';
    } else {
      state.timerRunning = true;
      toggleButton.innerHTML =
        '<i data-lucide="pause" class="icon-sm inline-icon"></i> Pausar';

      state.timerInterval = setInterval(() => {
        state.timerSeconds -= 1;

        if (state.timerSeconds <= 0) {
          clearInterval(state.timerInterval);
          state.timerRunning = false;
          state.timerSeconds = 0;
          toggleButton.innerHTML =
            '<i data-lucide="play" class="icon-sm inline-icon"></i> Iniciar';
        }

        updateTimerDisplay();
        lucide.createIcons();
      }, 1000);
    }

    updateTimerDisplay();
    lucide.createIcons();
  });

  resetButton.addEventListener("click", () => {
    clearInterval(state.timerInterval);
    state.timerRunning = false;
    state.timerSeconds = state.timerPreset * 60;
    toggleButton.innerHTML =
      '<i data-lucide="play" class="icon-sm inline-icon"></i> Iniciar';
    updateTimerDisplay();
    lucide.createIcons();
  });

  document.querySelectorAll(".timer-preset").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".timer-preset").forEach((preset) => {
        preset.classList.remove("preset-active");
      });

      button.classList.add("preset-active");
      state.timerPreset = parseInt(button.dataset.minutes, 10);

      if (!state.timerRunning) {
        state.timerSeconds = state.timerPreset * 60;
        updateTimerDisplay();
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  setupTimer();
  document
    .getElementById("addForm")
    .addEventListener("submit", handleAddSession);

  updateTimerDisplay();
  lucide.createIcons();
  await ensureSetup();
  await loadSessions();
});