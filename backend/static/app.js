let barChartInstance = null;
let doughnutChartInstance = null;

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

function renderAnalysisData(data) {
  const resultBox = document.getElementById("analysisResult");
  const highlightedOutput = document.getElementById("highlightedOutput");
  const rewriteOutput = document.getElementById("rewriteOutput");
  const changesOutput = document.getElementById("changesOutput");
  const sentenceOutput = document.getElementById("sentenceOutput");

  let output = "";
  output += "Input: " + (data.input || "") + "\n\n";

  if (data.source_file) {
    output += "Source File: " + data.source_file + "\n";
  }

  output += "Predicted Label: " + (data.ml_label || "") + "\n";
  output += "Score: " + (data.score ?? "") + "\n";
  output += "Score Label: " + (data.score_label || "") + "\n\n";
  output += "Detected Issues:\n";

  if (!data.issues || data.issues.length === 0) {
    output += "No ambiguity detected.";
  } else {
    data.issues.forEach((item, index) => {
      output += "\n" + (index + 1) + ". Term: " + item.term + "\n";
      output += "   Category: " + item.category + "\n";
      output += "   Explanation: " + item.explanation + "\n";
      output += "   Suggestion: " + item.suggestion + "\n";
      output += "   Severity: " + item.severity + "\n";
    });
  }

  if (resultBox) {
    resultBox.innerText = output;
  }

  if (highlightedOutput) {
    highlightedOutput.innerHTML = data.highlighted_html || "No highlighted issues.";
  }

  if (rewriteOutput) {
    rewriteOutput.innerText = data.rewrite || "No rewrite available.";
  }

  if (changesOutput) {
    if (!data.changes || data.changes.length === 0) {
      changesOutput.innerHTML = "<p>No changes needed.</p>";
    } else {
      let changesHtml = "<ul class='changes-list'>";
      data.changes.forEach((item) => {
        changesHtml += `
          <li>
            <strong>${item.term}</strong>
            → <span class="replacement-text">${item.replace_with || "See suggestion"}</span>
            <br>
            <span class="change-meta">${item.category} | ${item.severity}</span>
          </li>
        `;
      });
      changesHtml += "</ul>";
      changesOutput.innerHTML = changesHtml;
    }
  }

  if (sentenceOutput) {
    if (!data.sentence_analysis || data.sentence_analysis.length === 0) {
      sentenceOutput.innerHTML = "<p>No sentence analysis available.</p>";
    } else {
      let sentenceHtml = "";
      data.sentence_analysis.forEach((item, index) => {
        sentenceHtml += `
          <div class="sentence-card">
            <h4>Sentence ${index + 1}</h4>
            <p>${item.sentence}</p>
        `;

        if (!item.issues || item.issues.length === 0) {
          sentenceHtml += `<p class="sentence-ok">No ambiguity detected.</p>`;
        } else {
          sentenceHtml += "<ul class='sentence-issue-list'>";
          item.issues.forEach((issue) => {
            sentenceHtml += `
              <li>
                <strong>${issue.term}</strong> - ${issue.category}
                <br>
                Replace with: <span class="replacement-text">${issue.replacement || issue.suggestion}</span>
              </li>
            `;
          });
          sentenceHtml += "</ul>";
        }

        sentenceHtml += "</div>";
      });
      sentenceOutput.innerHTML = sentenceHtml;
    }
  }
}

async function analyzeRequirement() {
  const textBox = document.getElementById("requirementText");
  const resultBox = document.getElementById("analysisResult");

  if (!textBox || !resultBox) {
    return;
  }

  const text = textBox.value.trim();

  if (!text) {
    resultBox.innerText = "Enter requirement text first.";
    return;
  }

  resultBox.innerText = "Analyzing...";

  try {
    const response = await fetch("/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ text: text })
    });

    const data = await response.json();

    if (!response.ok) {
      resultBox.innerText = data.error || "Analysis failed.";
      return;
    }

    renderAnalysisData(data);
    loadDashboard();
  } catch (error) {
    resultBox.innerText = "Error connecting to backend.";
  }
}

async function analyzeUploadedFile() {
  const fileInput = document.getElementById("fileInput");
  const resultBox = document.getElementById("analysisResult");

  if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
    if (resultBox) {
      resultBox.innerText = "Select a .txt, .docx, or .pdf file first.";
    }
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  if (resultBox) {
    resultBox.innerText = "Analyzing uploaded file...";
  }

  try {
    const response = await fetch("/analyze-file", {
      method: "POST",
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
      if (resultBox) {
        resultBox.innerText = data.error || "File analysis failed.";
      }
      return;
    }

    renderAnalysisData(data);
    loadDashboard();
  } catch (error) {
    if (resultBox) {
      resultBox.innerText = "Error uploading file.";
    }
  }
}

function renderCharts(totalRequirements, ambiguousCount) {
  const clearCount = Math.max(totalRequirements - ambiguousCount, 0);

  const barCanvas = document.getElementById("barChart");
  const doughnutCanvas = document.getElementById("doughnutChart");

  if (barCanvas && typeof Chart !== "undefined") {
    if (barChartInstance) {
      barChartInstance.destroy();
    }

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
        plugins: {
          legend: {
            display: false
          }
        }
      }
    });
  }

  if (doughnutCanvas && typeof Chart !== "undefined") {
    if (doughnutChartInstance) {
      doughnutChartInstance.destroy();
    }

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
        maintainAspectRatio: true
      }
    });
  }
}

async function loadDashboard() {
  try {
    const response = await fetch("/stats");
    const data = await response.json();

    if (!response.ok) {
      return;
    }

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

  if (!historyContainer) {
    return;
  }

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

  if (!adminUsers || !adminHistory) {
    return;
  }

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
});