(() => {
  "use strict";

  const chat = document.getElementById("director-chat");
  const promptBox = document.getElementById("director-prompt");
  const send = document.getElementById("director-send");

  if (!chat || !promptBox || !send) return;

  let originalPrompt = "";
  let answers = {};
  let questions = [];
  let currentQuestion = 0;

  function addMessage(role, text, allowHtml = false) {
    const div = document.createElement("div");
    div.className = `director-message ${role}`;

    if (allowHtml) div.innerHTML = text;
    else div.textContent = text;

    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  function showError(error) {
    addMessage("assistant", `Something went wrong: ${error.message}`);
    promptBox.disabled = false;
    send.disabled = false;
  }

  send.addEventListener("click", async () => {
    originalPrompt = promptBox.value.trim();
    if (!originalPrompt) return;

    answers = {};
    addMessage("user", originalPrompt);
    promptBox.disabled = true;
    send.disabled = true;

    try {
      const response = await fetch("/api/creative-director/questions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: originalPrompt })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load questions.");

      questions = data.questions || [];
      currentQuestion = 0;
      if (questions.length) showQuestion();
      else await buildBrief();
    } catch (error) {
      showError(error);
    }
  });

  promptBox.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send.click();
    }
  });

  function showQuestion() {
    const question = questions[currentQuestion];
    addMessage("assistant", question.question);

    const container = document.createElement("div");
    container.className = "director-options";

    question.options.forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = option;
      button.addEventListener("click", async () => {
        answers[question.id] = option;
        addMessage("user", option);
        container.remove();
        currentQuestion += 1;

        if (currentQuestion < questions.length) showQuestion();
        else await buildBrief();
      });
      container.appendChild(button);
    });

    chat.appendChild(container);
    chat.scrollTop = chat.scrollHeight;
  }

  async function buildBrief() {
    addMessage("assistant", "Perfect. Creating production brief...");

    try {
      const response = await fetch("/api/creative-director/brief", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: originalPrompt, answers })
      });
      const brief = await response.json();
      if (!response.ok) throw new Error(brief.detail || "Could not build the brief.");
      showBrief(brief);
    } catch (error) {
      showError(error);
    }
  }

  function showBrief(brief) {
    const pre = document.createElement("pre");
    pre.className = "director-brief";
    pre.textContent = brief.creative_brief;
    chat.appendChild(pre);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "director-production-button";
    button.textContent = "Start Production";
    button.addEventListener("click", () => {
      button.disabled = true;
      startProduction(brief).catch(showError);
    });
    chat.appendChild(button);
    chat.scrollTop = chat.scrollHeight;
  }

  async function startProduction(brief) {
    const response = await fetch("/api/orchestrator/create-project", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: brief.creative_brief,
        target_seconds: brief.target_seconds,
        hook_type: brief.hook_type,
        save_workspace: true
      })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Could not create the project.");

    addMessage(
      "assistant",
      `Project created.<br><br>Project ID<br><b>${escapeHtml(result.project_id || "")}</b><br><br>Readiness<br>${Number(result.readiness_score || 0)}%<br><br>Confidence<br>${Math.round(Number(result.confidence || 0) * 100)}%`,
      true
    );
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
})();
