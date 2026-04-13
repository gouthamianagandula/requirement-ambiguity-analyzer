let barChartInstance = null;
let doughnutChartInstance = null;
let realtimeTimer = null;
let lastRealtimeValue = "";
let isAnalyzing = false;

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

function showLoginTab(tabName) {
  const loginTab = document.getElementById("loginTab");
  const registerTab = document.getElementById("registerTab");
  const buttons = document.querySelectorAll(".tab-btn");

  buttons.forEach((btn) => btn.classList.remove("active-tab"));

  if (tabName === "login") {
    if (loginTab) loginTab.classList.add("active-auth-tab");
    if (registerTab) registerTab.classList.remove("active-auth-tab");
    if (buttons[0]) buttons[0].classList.add("active-tab");
  } else {
    if (registerTab) registerTab.classList.add("active-auth-tab");
    if (loginTab) loginTab.classList.remove("active-auth-tab");
    if (buttons[1]) buttons[1].classList.add("active-tab");
  }
}

async function loginWithEmail() {
  const email = document.getElementById("loginEmail")?.value.trim() || "";
  const password = document.getElementById("loginPassword")?.value.trim() || "";
  const authMessage = document.getElementById("authMessage");

  if (!email || !password) {
    if (authMessage) authMessage.innerText = "Enter email and password.";
    return;
  }

  try {
    const response = await fetch("/login-email", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ email, password })
    });

    const data = await response.json();

    if (!response.ok) {
      if (authMessage) authMessage.innerText = data.error || "Login failed.";
      return;
    }

    if (authMessage) authMessage.innerText = "Login successful.";
    window.location.href = "/analyzer";
  } catch (error) {
    if (authMessage) authMessage.innerText = "Login error.";
  }
}

async function registerWithEmail() {
  const name = document.getElementById("registerName")?.value.trim() || "";
  const email = document.getElementById("registerEmail")?.value.trim() || "";
  const password = document.getElementById("registerPassword")?.value.trim() || "";
  const authMessage = document.getElementById("authMessage");

  if (!name || !email || !password) {
    if (authMessage) authMessage.innerText = "Enter name, email, and password.";
    return;
  }

  try {
    const response = await fetch("/register-email", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ name, email, password })
    });

    const data = await response.json();

    if (!response.ok) {
      if (authMessage) authMessage.innerText = data.error || "Registration failed.";
      return;
    }

    if (authMessage) authMessage.innerText = data.message || "Registration successful.";
    showLoginTab("login");
  } catch (error) {
    if (authMessage) authMessage.innerText = "Registration error.";
  }
}

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function getAnalyzeButtons() {
  return document.querySelectorAll(".analyze-btn");
}

function setAnalyzeButtonsBusy(isBusy) {
  const buttons = getAnalyzeButtons();
  buttons.forEach((btn) => {
    btn.disabled = isBusy;
    btn.classList.toggle("btn-loading", isBusy);
    if (isBusy) {
      btn.dataset.originalText = btn.dataset.originalText || btn.innerText;
      btn.innerText = "RAA analyzing...";
    } else if (btn.dataset.originalText) {
      btn.innerText = btn.dataset.originalText;
    }
  });
}

function renderIssueCards(issues) {
  const issuesOutput = document.getElementById("issuesOutput");
  if (!issuesOutput) return;

  if (!issues || issues.length === 0) {
    issuesOutput.innerHTML = "<p>No AI issues detected.</p>";
    return;
  }

  let html = "";

  issues.forEach((issue) => {
    const category = escapeHtml(issue.category || "Issue");
    const explanation = escapeHtml(issue.explanation || "");
    const suggestion = escapeHtml(issue.suggestion || "");
    const replacement = escapeHtml(issue.replacement || "");
    const severity = escapeHtml(issue.severity || "");
    const term = escapeHtml(issue.term || "");

    html += `
      <div class="issue-card">
        <div class="issue-card-head">
          <h4>${category}</h4>
          <span class="issue-severity">${severity}</span>
        </div>
        ${term ? `<p><strong>Highlighted Part:</strong> ${term}</p>` : ""}
        ${explanation ? `<p><strong>Problem:</strong> ${explanation}</p>` : ""}
        ${suggestion ? `<p><strong>Suggestion:</strong> ${suggestion}</p>` : ""}
        ${replacement ? `<p><strong>Suggested Fix:</strong> ${replacement}</p>` : ""}
    `;

    if (issue.alternatives && issue.alternatives.length > 0) {
      html += `<div class="issue-list-block"><strong>Better Options:</strong><ul>`;
      issue.alternatives.forEach((alt) => {
        html += `<li>${escapeHtml(alt)}</li>`;
      });
      html += `</ul></div>`;
    }

    if (issue.meanings && issue.meanings.length > 0) {
      html += `<div class="issue-list-block"><strong>Possible Meanings:</strong><ul>`;
      issue.meanings.forEach((meaning) => {
        html += `<li>${escapeHtml(meaning)}</li>`;
      });
      html += `</ul></div>`;
    }

    html += `</div>`;
  });

  issuesOutput.innerHTML = html;
}

function renderAnalyzerResult(data) {
  const highlightedOutput = document.getElementById("highlightedOutput");
  const correctedOutput = document.getElementById("correctedOutput");
  const rewriteOutput = document.getElementById("rewriteOutput");
  const analyzerStatus = document.getElementById("analyzerStatus");

  if (highlightedOutput) {
    highlightedOutput.innerHTML = data.highlighted_html || "No highlighted issues.";
  }

  if (correctedOutput) {
    correctedOutput.innerText = data.corrected_text || data.input || "No corrected sentence.";
  }

  if (rewriteOutput) {
    rewriteOutput.innerText = data.rewrite || data.corrected_text || data.input || "No rewrite available.";
  }

  if (analyzerStatus) {
    analyzerStatus.innerHTML = `<span class="status-success">RAA analysis completed.</span>`;
  }

  renderIssueCards(data.issues || []);
}

function renderAnalyzerError(message) {
  const highlightedOutput = document.getElementById("highlightedOutput");
  const correctedOutput = document.getElementById("correctedOutput");
  const rewriteOutput = document.getElementById("rewriteOutput");
  const issuesOutput = document.getElementById("issuesOutput");
  const analyzerStatus = document.getElementById("analyzerStatus");

  if (highlightedOutput) highlightedOutput.innerText = message || "Analysis failed.";
  if (correctedOutput) correctedOutput.innerText = "";
  if (rewriteOutput) rewriteOutput.innerText = "";
  if (issuesOutput) issuesOutput.innerHTML = "";
  if (analyzerStatus) {
    analyzerStatus.innerHTML = `<span class="status-error">${escapeHtml(message || "Analysis failed.")}</span>`;
  }
}

function setAnalyzerLoading(message = "RAA analyzing...") {
  const highlightedOutput = document.getElementById("highlightedOutput");
  const correctedOutput = document.getElementById("correctedOutput");
  const rewriteOutput = document.getElementById("rewriteOutput");
  const issuesOutput = document.getElementById("issuesOutput");
  const analyzerStatus = document.getElementById("analyzerStatus");

  if (highlightedOutput) highlightedOutput.innerHTML = `<span class="status-loading">${escapeHtml(message)}</span>`;
  if (correctedOutput) correctedOutput.innerText = "Processing...";
  if (rewriteOutput) rewriteOutput.innerText = "Processing...";
  if (issuesOutput) issuesOutput.innerHTML = "Preparing AI analysis...";
  if (analyzerStatus) {
    analyzerStatus.innerHTML = `<span class="status-loading">${escapeHtml(message)}</span>`;
  }
}

async function callAnalyzeApi(payload, isFile = false) {
  const options = isFile
    ? {
        method: "POST",
        body: payload
      }
    : {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      };

  const endpoint = isFile ? "/analyze-file" : "/analyze";

  const response = await fetch(endpoint, options);

  let data = {};
  try {
    data = await response.json();
  } catch (jsonError) {
    throw new Error("Backend returned invalid JSON.");
  }

  if (!response.ok || data.error) {
    throw new Error(data.error || `Analysis failed with status ${response.status}.`);
  }

  return data;
}

async function analyzeRequirement() {
  const textBox = document.getElementById("requirementText");
  if (!textBox || isAnalyzing) return;

  const text = textBox.value.trim();

  if (!text) {
    renderAnalyzerError("Enter requirement text first.");
    return;
  }

  isAnalyzing = true;
  setAnalyzeButtonsBusy(true);
  setAnalyzerLoading("RAA analyzing requirement...");

  try {
    const data = await callAnalyzeApi({ text }, false);
    renderAnalyzerResult(data);
    loadDashboard();
  } catch (error) {
    renderAnalyzerError(error.message || "RAA analysis failed.");
  } finally {
    isAnalyzing = false;
    setAnalyzeButtonsBusy(false);
  }
}

async function analyzeUploadedFile() {
  const fileInput = document.getElementById("fileInput");
  if (!fileInput || isAnalyzing) return;

  if (!fileInput.files || fileInput.files.length === 0) {
    renderAnalyzerError("Select a .txt, .docx, or .pdf file first.");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  isAnalyzing = true;
  setAnalyzeButtonsBusy(true);
  setAnalyzerLoading("RAA analyzing uploaded file...");

  try {
    const data = await callAnalyzeApi(formData, true);
    renderAnalyzerResult(data);
    loadDashboard();
  } catch (error) {
    renderAnalyzerError(error.message || "RAA file analysis failed.");
  } finally {
    isAnalyzing = false;
    setAnalyzeButtonsBusy(false);
  }
}

function scheduleRealtimeAnalysis() {
  const textBox = document.getElementById("requirementText");
  if (!textBox) return;

  const currentValue = textBox.value.trim();

  if (currentValue.length < 12) {
    const analyzerStatus = document.getElementById("analyzerStatus");
    if (analyzerStatus) {
      analyzerStatus.innerHTML = `<span class="status-muted">Realtime analysis starts after more text is entered.</span>`;
    }
    return;
  }

  if (currentValue === lastRealtimeValue) return;

  clearTimeout(realtimeTimer);
  realtimeTimer = setTimeout(async () => {
    if (isAnalyzing) return;

    const latestText = textBox.value.trim();
    if (latestText.length < 12 || latestText === lastRealtimeValue) return;

    lastRealtimeValue = latestText;
    isAnalyzing = true;
    setAnalyzeButtonsBusy(true);
    setAnalyzerLoading("RAA realtime analysis...");

    try {
      const data = await callAnalyzeApi({ text: latestText }, false);
      renderAnalyzerResult(data);
    } catch (error) {
      renderAnalyzerError(error.message || "RAA realtime analysis failed.");
    } finally {
      isAnalyzing = false;
      setAnalyzeButtonsBusy(false);
    }
  }, 900);
}

function attachRealtimeAnalyzer() {
  const textBox = document.getElementById("requirementText");
  if (!textBox) return;

  textBox.addEventListener("input", scheduleRealtimeAnalysis);
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

async function loadDashboard() {
  try {
    const response = await fetch("/stats");
    const data = await response.json();

    if (!response.ok) return;

    const totalRequirements = document.getElementById("totalRequirements");
    const ambiguousCount = document.getElementById("ambiguousCount");
    const averageScore = document.getElementById("averageScore");
    const lastLabel = document.getElementById("lastLabel");
    const profileName = document.getElementById("profileName");
    const profileEmail = document.getElementById("profileEmail");
    const profileAvatar = document.querySelector(".profile-avatar");
    const dashboardSummary = document.getElementById("dashboardSummary");

    if (totalRequirements) totalRequirements.innerText = data.total_requirements_analyzed;
    if (ambiguousCount) ambiguousCount.innerText = data.ambiguous_count;
    if (averageScore) averageScore.innerText = data.average_score;
    if (lastLabel) lastLabel.innerText = data.last_predicted_label;
    if (profileName) profileName.innerText = data.user_name;
    if (profileEmail) profileEmail.innerText = data.user_email;
    if (profileAvatar && data.user_name) {
      profileAvatar.innerText = data.user_name.charAt(0).toUpperCase();
    }

    if (dashboardSummary) {
      dashboardSummary.innerHTML = `
        <p><strong>Total Requirements:</strong> ${data.total_requirements_analyzed}</p>
        <p><strong>Ambiguous Count:</strong> ${data.ambiguous_count}</p>
        <p><strong>Average Score:</strong> ${data.average_score}</p>
        <p><strong>Last Predicted Label:</strong> ${data.last_predicted_label}</p>
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
          <p><strong>Input:</strong> ${item.input_text}</p>
          <p><strong>Predicted Label:</strong> ${item.predicted_label}</p>
          <p><strong>Score:</strong> ${item.score}</p>
          <p><strong>Rewrite:</strong> ${item.rewrite}</p>
          <p><strong>Date:</strong> ${item.created_at}</p>
        </div>
      `;
    });

    historyContainer.innerHTML = html;
  } catch (error) {
    historyContainer.innerHTML = "<p>Error loading history.</p>";
  }
}

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
            <p><strong>Name:</strong> ${user.name}</p>
            <p><strong>Email:</strong> ${user.email}</p>
            <p><strong>Created:</strong> ${user.created_at}</p>
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
            <p><strong>User:</strong> ${item.user_name}</p>
            <p><strong>Email:</strong> ${item.user_email}</p>
            <p><strong>Input:</strong> ${item.input_text}</p>
            <p><strong>Label:</strong> ${item.predicted_label}</p>
            <p><strong>Score:</strong> ${item.score}</p>
            <p><strong>Date:</strong> ${item.created_at}</p>
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

document.addEventListener("DOMContentLoaded", function () {
  applySavedTheme();
  loadDashboard();
  loadHistory();
  loadAdmin();
  attachRealtimeAnalyzer();
});