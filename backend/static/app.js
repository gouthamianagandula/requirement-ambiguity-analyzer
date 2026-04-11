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

    let output = "";
    output += "Input: " + data.input + "\n\n";
    output += "Predicted Label: " + data.ml_label + "\n";
    output += "Score: " + data.score + "\n";
    output += "Score Label: " + data.score_label + "\n\n";
    output += "Suggested Rewrite:\n" + data.rewrite + "\n\n";
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

    loadDashboard();
  } catch (error) {
    resultBox.innerText = "Error connecting to backend.";
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

    if (totalRequirements) {
      totalRequirements.innerText = data.total_requirements_analyzed;
    }

    if (ambiguousCount) {
      ambiguousCount.innerText = data.ambiguous_count;
    }

    if (averageScore) {
      averageScore.innerText = data.average_score;
    }

    if (lastLabel) {
      lastLabel.innerText = data.last_predicted_label;
    }

    if (profileName) {
      profileName.innerText = data.user_name;
    }

    if (profileEmail) {
      profileEmail.innerText = data.user_email;
    }

    if (profileAvatar && data.user_name) {
      profileAvatar.innerText = data.user_name.charAt(0).toUpperCase();
    }
  } catch (error) {
    console.log("Dashboard load failed");
  }
}

window.onload = function () {
  loadDashboard();
};