async function analyzeRequirement() {
  const textBox = document.getElementById("requirementText");
  const resultBox = document.getElementById("analysisResult");
  const highlightedOutput = document.getElementById("highlightedOutput");
  const rewriteOutput = document.getElementById("rewriteOutput");
  const changesOutput = document.getElementById("changesOutput");
  const sentenceOutput = document.getElementById("sentenceOutput");

  if (!textBox || !resultBox) {
    return;
  }

  const text = textBox.value.trim();

  if (!text) {
    resultBox.innerText = "Enter requirement text first.";
    if (highlightedOutput) highlightedOutput.innerHTML = "";
    if (rewriteOutput) rewriteOutput.innerText = "";
    if (changesOutput) changesOutput.innerHTML = "";
    if (sentenceOutput) sentenceOutput.innerHTML = "";
    return;
  }

  resultBox.innerText = "Analyzing...";
  if (highlightedOutput) highlightedOutput.innerHTML = "Analyzing...";
  if (rewriteOutput) rewriteOutput.innerText = "Analyzing...";
  if (changesOutput) changesOutput.innerHTML = "Analyzing...";
  if (sentenceOutput) sentenceOutput.innerHTML = "Analyzing...";

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

    let output = "";
    output += "Input: " + data.input + "\n\n";
    output += "Predicted Label: " + data.ml_label + "\n";
    output += "Score: " + data.score + "\n";
    output += "Score Label: " + data.score_label + "\n\n";
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

    resultBox.innerText = output;

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

    loadDashboard();
  } catch (error) {
    resultBox.innerText = "Error connecting to backend.";
    if (highlightedOutput) highlightedOutput.innerHTML = "";
    if (rewriteOutput) rewriteOutput.innerText = "";
    if (changesOutput) changesOutput.innerHTML = "";
    if (sentenceOutput) sentenceOutput.innerHTML = "";
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

    if (totalRequirements) totalRequirements.innerText = data.total_requirements_analyzed;
    if (ambiguousCount) ambiguousCount.innerText = data.ambiguous_count;
    if (averageScore) averageScore.innerText = data.average_score;
    if (lastLabel) lastLabel.innerText = data.last_predicted_label;
    if (profileName) profileName.innerText = data.user_name;
    if (profileEmail) profileEmail.innerText = data.user_email;
    if (profileAvatar && data.user_name) {
      profileAvatar.innerText = data.user_name.charAt(0).toUpperCase();
    }
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

document.addEventListener("DOMContentLoaded", function () {
  loadDashboard();
  loadHistory();
});