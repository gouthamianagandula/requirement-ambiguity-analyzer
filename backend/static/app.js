let barChartInstance = null;
let doughnutChartInstance = null;
let realtimeTimer = null;
let lastRealtimeValue = "";
let isAnalyzing = false;

/* ================= THEME ================= */
function applySavedTheme() {
  const savedTheme = localStorage.getItem("theme") || "dark-theme";
  document.body.classList.remove("light-theme", "dark-theme");
  document.body.classList.add(savedTheme);
}

function toggleTheme() {
  if (document.body.classList.contains("dark-theme")) {
    document.body.classList.remove("dark-theme");
    document.body.classList.add("light-theme");
    localStorage.setItem("theme", "light-theme");
  } else {
    document.body.classList.remove("light-theme");
    document.body.classList.add("dark-theme");
    localStorage.setItem("theme", "dark-theme");
  }
}

/* ================= HELPERS ================= */
function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function setAnalyzeButtonsBusy(isBusy) {
  document.querySelectorAll(".analyze-btn").forEach((btn) => {
    btn.disabled = isBusy;
    btn.classList.toggle("btn-loading", isBusy);

    if (isBusy) {
      if (!btn.dataset.originalText) {
        btn.dataset.originalText = btn.innerText;
      }
      btn.innerText = "RAA analyzing...";
    } else if (btn.dataset.originalText) {
      btn.innerText = btn.dataset.originalText;
    }
  });
}

/* ================= LOGIN ================= */
function showLoginTab(tabName) {
  const loginTab = document.getElementById("loginTab");
  const registerTab = document.getElementById("registerTab");
  const buttons = document.querySelectorAll(".tab-btn");

  buttons.forEach((btn) => btn.classList.remove("active-tab"));

  if (tabName === "login") {
    loginTab?.classList.add("active-auth-tab");
    registerTab?.classList.remove("active-auth-tab");
    buttons[0]?.classList.add("active-tab");
  } else {
    registerTab?.classList.add("active-auth-tab");
    loginTab?.classList.remove("active-auth-tab");
    buttons[1]?.classList.add("active-tab");
  }
}

async function loginWithEmail() {
  const email = document.getElementById("loginEmail")?.value.trim();
  const password = document.getElementById("loginPassword")?.value.trim();
  const msg = document.getElementById("authMessage");

  if (!email || !password) {
    if (msg) msg.innerText = "Enter email and password";
    return;
  }

  try {
    const res = await fetch("/login-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();

    if (!res.ok) {
      if (msg) msg.innerText = data.error || "Login failed";
      return;
    }

    window.location.href = "/analyzer";
  } catch (error) {
    if (msg) msg.innerText = "Login failed";
  }
}

async function registerWithEmail() {
  const name = document.getElementById("registerName")?.value.trim();
  const email = document.getElementById("registerEmail")?.value.trim();
  const password = document.getElementById("registerPassword")?.value.trim();
  const msg = document.getElementById("authMessage");

  if (!name || !email || !password) {
    if (msg) msg.innerText = "Fill all fields";
    return;
  }

  try {
    const res = await fetch("/register-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password })
    });

    const data = await res.json();

    if (!res.ok) {
      if (msg) msg.innerText = data.error || "Registration failed";
      return;
    }

    if (msg) msg.innerText = data.message || "Registered";
    showLoginTab("login");
  } catch (error) {
    if (msg) msg.innerText = "Registration failed";
  }
}

/* ================= API ================= */
async function callAnalyzeApi(payload, isFile = false) {
  const endpoint = isFile ? "/analyze-file" : "/analyze";

  const options = isFile
    ? {
        method: "POST",
        body: payload
      }
    : {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      };

  const res = await fetch(endpoint, options);

  let data = {};
  try {
    data = await res.json();
  } catch (error) {
    throw new Error("Backend returned invalid JSON.");
  }

  if (!res.ok || data.error) {
    throw new Error(data.error || "Analysis failed.");
  }

  return data;
}

/* ================= ANALYZER ================= */
async function analyzeRequirement() {
  const textBox = document.getElementById("requirementText");
  const text = textBox?.value.trim();

  if (!text || isAnalyzing) return;

  isAnalyzing = true;
  setAnalyzeButtonsBusy(true);
  setAnalyzerLoading();

  try {
    const data = await callAnalyzeApi({ text }, false);
    renderAnalyzerResult(data);
    await loadDashboard();
  } catch (err) {
    renderAnalyzerError(err.message || "Analysis failed");
  } finally {
    isAnalyzing = false;
    setAnalyzeButtonsBusy(false);
  }
}

async function analyzeUploadedFile() {
  const fileInput = document.getElementById("fileInput");
  const file = fileInput?.files?.[0];

  if (!file || isAnalyzing) {
    if (!file) renderAnalyzerError("Select a file first.");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  isAnalyzing = true;
  setAnalyzeButtonsBusy(true);
  setAnalyzerLoading("RAA analyzing file...");

  try {
    const data = await callAnalyzeApi(formData, true);
    renderAnalyzerResult(data);
    await loadDashboard();
  } catch (err) {
    renderAnalyzerError(err.message || "File analysis failed");
  } finally {
    isAnalyzing = false;
    setAnalyzeButtonsBusy(false);
  }
}

/* ================= REALTIME ================= */
function scheduleRealtimeAnalysis() {
  const text = document.getElementById("requirementText")?.value.trim() || "";

  if (text.length < 12 || text === lastRealtimeValue) return;

  clearTimeout(realtimeTimer);

  realtimeTimer = setTimeout(async () => {
    lastRealtimeValue = text;
    await analyzeRequirement();
  }, 800);
}

function attachRealtimeAnalyzer() {
  document.getElementById("requirementText")
    ?.addEventListener("input", scheduleRealtimeAnalysis);
}

/* ================= OUTPUT ================= */
function renderAnalyzerResult(data) {
  const highlightedOutput = document.getElementById("highlightedOutput");
  const correctedOutput = document.getElementById("correctedOutput");
  const rewriteOutput = document.getElementById("rewriteOutput");
  const analyzerStatus = document.getElementById("analyzerStatus");

  if (highlightedOutput) {
    highlightedOutput.innerHTML = data.highlighted_html || "";
  }

  if (correctedOutput) {
    correctedOutput.innerText = data.corrected_text || "";
  }

  if (rewriteOutput) {
    rewriteOutput.innerText = data.rewrite || "";
  }

  renderIssues(data.issues || []);

  if (analyzerStatus) {
    analyzerStatus.innerHTML = `<span class="status-success">Done</span>`;
  }
}

function renderIssues(issues) {
  const div = document.getElementById("issuesOutput");
  if (!div) return;

  if (!issues.length) {
    div.innerHTML = "No issues";
    return;
  }

  div.innerHTML = issues.map((i) => `
    <div class="issue-card">
      <div class="issue-card-head">
        <h4>${escapeHtml(i.category || "Issue")}</h4>
        <span class="issue-severity">${escapeHtml(i.severity || "Info")}</span>
      </div>
      ${i.term ? `<p><strong>Text:</strong> ${escapeHtml(i.term)}</p>` : ""}
      ${i.explanation ? `<p>${escapeHtml(i.explanation)}</p>` : ""}
      ${i.replacement ? `<p><b>Fix:</b> ${escapeHtml(i.replacement)}</p>` : ""}
      ${
        Array.isArray(i.alternatives) && i.alternatives.length
          ? `<div class="issue-list-block"><strong>Alternatives:</strong><ul>${i.alternatives.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>`
          : ""
      }
      ${
        Array.isArray(i.meanings) && i.meanings.length
          ? `<div class="issue-list-block"><strong>Possible meanings:</strong><ul>${i.meanings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>`
          : ""
      }
    </div>
  `).join("");
}

/* ================= STATUS ================= */
function setAnalyzerLoading(message = "RAA analyzing...") {
  const analyzerStatus = document.getElementById("analyzerStatus");
  const highlightedOutput = document.getElementById("highlightedOutput");
  const correctedOutput = document.getElementById("correctedOutput");
  const rewriteOutput = document.getElementById("rewriteOutput");
  const issuesOutput = document.getElementById("issuesOutput");

  if (analyzerStatus) {
    analyzerStatus.innerHTML = `<span class="status-loading">${escapeHtml(message)}</span>`;
  }

  if (highlightedOutput) highlightedOutput.innerHTML = "";
  if (correctedOutput) correctedOutput.innerText = "Processing...";
  if (rewriteOutput) rewriteOutput.innerText = "Processing...";
  if (issuesOutput) issuesOutput.innerHTML = "Preparing AI analysis...";
}

function renderAnalyzerError(msg) {
  const analyzerStatus = document.getElementById("analyzerStatus");
  if (analyzerStatus) {
    analyzerStatus.innerHTML = `<span class="status-error">${escapeHtml(msg)}</span>`;
  }
}

/* ================= DASHBOARD ================= */
async function loadDashboard() {
  try {
    const res = await fetch("/stats");
    const data = await res.json();

    if (!res.ok) return;

    const totalRequirements = document.getElementById("totalRequirements");
    const ambiguousCount = document.getElementById("ambiguousCount");
    const averageScore = document.getElementById("averageScore");
    const lastLabel = document.getElementById("lastLabel");
    const profileName = document.getElementById("profileName");
    const profileEmail = document.getElementById("profileEmail");
    const profileAvatar = document.querySelector(".profile-avatar");
    const dashboardSummary = document.getElementById("dashboardSummary");

    if (totalRequirements) {
      totalRequirements.innerText = data.total_requirements_analyzed ?? 0;
    }

    if (ambiguousCount) {
      ambiguousCount.innerText = data.ambiguous_count ?? 0;
    }

    if (averageScore) {
      averageScore.innerText = data.average_score ?? 0;
    }

    if (lastLabel) {
      lastLabel.innerText = data.last_predicted_label ?? "None";
    }

    if (profileName) {
      profileName.innerText = data.user_name || "User";
    }

    if (profileEmail) {
      profileEmail.innerText = data.user_email || "";
    }

    if (profileAvatar && data.user_name) {
      profileAvatar.innerText = data.user_name.charAt(0).toUpperCase();
    }

    if (dashboardSummary) {
      dashboardSummary.innerHTML = `
        <p><strong>Total Requirements:</strong> ${data.total_requirements_analyzed ?? 0}</p>
        <p><strong>Ambiguous Count:</strong> ${data.ambiguous_count ?? 0}</p>
        <p><strong>Average Score:</strong> ${data.average_score ?? 0}</p>
        <p><strong>Last Predicted Label:</strong> ${data.last_predicted_label ?? "None"}</p>
      `;
    }

    renderCharts(
      Number(data.total_requirements_analyzed || 0),
      Number(data.ambiguous_count || 0)
    );
  } catch (error) {
    console.log("Dashboard load failed");
  }
}

function renderCharts(totalRequirements, ambiguousCount) {
  const clearCount = Math.max(totalRequirements - ambiguousCount, 0);

  const barCanvas = document.getElementById("barChart");
  const doughnutCanvas = document.getElementById("doughnutChart");

  if (barCanvas && typeof Chart !== "undefined") {
    if (barChartInstance) barChartInstance.destroy();

    barChartInstance = new Chart(barCanvas, {
      type: "bar",
      data: {
        labels: ["Total", "Ambiguous", "Clear"],
        datasets: [
          {
            label: "Requirements",
            data: [totalRequirements, ambiguousCount, clearCount]
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        animation: false,
        plugins: {
          legend: { display: false }
        }
      }
    });
  }

  if (doughnutCanvas && typeof Chart !== "undefined") {
    if (doughnutChartInstance) doughnutChartInstance.destroy();

    doughnutChartInstance = new Chart(doughnutCanvas, {
      type: "doughnut",
      data: {
        labels: ["Ambiguous", "Clear"],
        datasets: [
          {
            data: [ambiguousCount, clearCount]
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        animation: false
      }
    });
  }
}

/* ================= HISTORY ================= */
async function loadHistory() {
  const historyContainer = document.getElementById("historyContainer");
  if (!historyContainer) return;

  historyContainer.innerHTML = "Loading your history...";

  try {
    const response = await fetch("/history");
    const data = await response.json();

    if (!response.ok) {
      historyContainer.innerHTML = "<p>Could not load your history.</p>";
      return;
    }

    if (!data.history || data.history.length === 0) {
      historyContainer.innerHTML = "<p>No saved history for your profile yet.</p>";
      return;
    }

    let html = "";
    data.history.forEach((item, index) => {
      html += `
        <div class="sentence-card">
          <h4>History ${index + 1}</h4>
          <p><strong>Input:</strong> ${escapeHtml(item.input_text)}</p>
          <p><strong>Predicted Label:</strong> ${escapeHtml(item.predicted_label)}</p>
          <p><strong>Score:</strong> ${escapeHtml(item.score)}</p>
          <p><strong>Rewrite:</strong> ${escapeHtml(item.rewrite)}</p>
          <p><strong>Date:</strong> ${escapeHtml(item.created_at)}</p>
        </div>
      `;
    });

    historyContainer.innerHTML = html;
  } catch (error) {
    historyContainer.innerHTML = "<p>Error loading history.</p>";
  }
}

/* ================= ADMIN ================= */
async function loadAdmin() {
  const adminUsers = document.getElementById("adminUsers");
  const adminHistory = document.getElementById("adminHistory");

  if (!adminUsers || !adminHistory) return;

  try {
    const response = await fetch("/admin-data");
    const data = await response.json();

    if (!response.ok) {
      adminUsers.innerHTML = "<p>Failed to load users.</p>";
      adminHistory.innerHTML = "<p>Failed to load history.</p>";
      return;
    }

    if (!data.users || data.users.length === 0) {
      adminUsers.innerHTML = "<p>No users found.</p>";
    } else {
      let usersHtml = "";
      data.users.forEach((user, index) => {
        usersHtml += `
          <div class="sentence-card">
            <h4>User ${index + 1}</h4>
            <p><strong>Name:</strong> ${escapeHtml(user.name)}</p>
            <p><strong>Email:</strong> ${escapeHtml(user.email)}</p>
            <p><strong>Created:</strong> ${escapeHtml(user.created_at)}</p>
          </div>
        `;
      });
      adminUsers.innerHTML = usersHtml;
    }

    if (!data.history || data.history.length === 0) {
      adminHistory.innerHTML = "<p>No history found.</p>";
    } else {
      let historyHtml = "";
      data.history.forEach((item, index) => {
        historyHtml += `
          <div class="sentence-card">
            <h4>Record ${index + 1}</h4>
            <p><strong>User:</strong> ${escapeHtml(item.user_name)}</p>
            <p><strong>Email:</strong> ${escapeHtml(item.user_email)}</p>
            <p><strong>Input:</strong> ${escapeHtml(item.input_text)}</p>
            <p><strong>Label:</strong> ${escapeHtml(item.predicted_label)}</p>
            <p><strong>Score:</strong> ${escapeHtml(item.score)}</p>
            <p><strong>Date:</strong> ${escapeHtml(item.created_at)}</p>
          </div>
        `;
      });
      adminHistory.innerHTML = historyHtml;
    }
  } catch (error) {
    adminUsers.innerHTML = "<p>Error loading users.</p>";
    adminHistory.innerHTML = "<p>Error loading history.</p>";
  }
}

/* ================= PREMIUM ================= */
function copyResult() {
  const text =
    document.getElementById("rewriteOutput")?.innerText ||
    document.getElementById("correctedOutput")?.innerText ||
    "";

  if (!text) {
    alert("Nothing to copy");
    return;
  }

  navigator.clipboard.writeText(text)
    .then(() => alert("Copied"))
    .catch(() => alert("Copy failed"));
}

function downloadReport() {
  const originalText = document.getElementById("requirementText")?.value || "";
  const correctedText = document.getElementById("correctedOutput")?.innerText || "";
  const rewriteText = document.getElementById("rewriteOutput")?.innerText || "";
  const issuesText = document.getElementById("issuesOutput")?.innerText || "";

  const text = `
=== REQUIREMENT ANALYSIS REPORT ===

Original:
${originalText}

----------------------------------

Corrected:
${correctedText}

----------------------------------

Rewrite:
${rewriteText}

----------------------------------

Issues:
${issuesText}
`;

  const blob = new Blob([text], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "report.txt";
  a.click();

  URL.revokeObjectURL(a.href);
}

/* ================= INIT ================= */
document.addEventListener("DOMContentLoaded", () => {
  applySavedTheme();
  loadDashboard();
  loadHistory();
  loadAdmin();
  attachRealtimeAnalyzer();
});