function login() {
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value.trim();

  if (!email || !password) {
    alert("Enter email and password");
    return;
  }

  if (!email.endsWith("@gmail.com")) {
    alert("Use Gmail only");
    return;
  }

  localStorage.setItem("user", email);
  alert("Login success");
}

async function analyze() {
  const text = document.getElementById("text").value.trim();

  if (!text) {
    alert("Enter requirement text");
    return;
  }

  try {
    const response = await fetch("http://127.0.0.1:8000/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ text: text })
    });

    const data = await response.json();

    document.getElementById("result").innerText = JSON.stringify(data, null, 2);
  } catch (error) {
    document.getElementById("result").innerText =
      "Error: backend not connected or not running.";
  }
}

async function loadDashboard() {
  try {
    const response = await fetch("http://127.0.0.1:8000/stats");
    const data = await response.json();

    document.getElementById("total").innerText = data.total_requirements_analyzed;
    document.getElementById("ambiguous").innerText = data.ambiguous_count;
    document.getElementById("avg").innerText = data.average_score;
    document.getElementById("label").innerText = data.last_predicted_label;
  } catch (error) {
    document.getElementById("total").innerText = "Error";
    document.getElementById("ambiguous").innerText = "Error";
    document.getElementById("avg").innerText = "Error";
    document.getElementById("label").innerText = "Error";
  }
}