(() => {
  "use strict";

  const chat = document.querySelector("#director-chat");
  const promptBox = document.querySelector("#director-prompt");
  const send = document.querySelector("#director-send");
  const status = document.querySelector("#director-status");
  const preferenceSummary = document.querySelector("#director-preferences-summary");
  const preferenceForm = document.querySelector("#director-preferences-form");
  const preferenceStatus = document.querySelector("#director-preferences-status");
  const preferenceReset = document.querySelector("#director-preferences-reset");

  if (!chat || !promptBox || !send) return;

  const PREFERENCE_FIELDS = [
    "target_seconds",
    "aspect_ratio",
    "tone",
    "visual_style",
    "narration_style",
    "caption_style",
    "music_preference"
  ];

  let originalPrompt = "";
  let answers = {};
  let questions = [];
  let currentQuestion = 0;
  let currentPreferences = {};

  async function requestJSON(url, options = {}, timeoutMs = 20000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {...options, signal: controller.signal});
      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }
      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "The Creative Director could not complete that request."
        );
      }
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("The Creative Director timed out. Please try again.");
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  function addMessage(role, text) {
    const message = document.createElement("div");
    message.className = `director-message ${role}`;
    message.textContent = String(text || "");
    chat.appendChild(message);
    chat.scrollTop = chat.scrollHeight;
    return message;
  }

  function setBusy(busy, label = "Continue") {
    promptBox.disabled = busy;
    send.disabled = busy;
    send.textContent = busy ? "Thinking…" : label;
    chat.setAttribute("aria-busy", String(busy));
  }

  function showError(error) {
    addMessage("assistant", error.message || "Something went wrong. Please try again.");
    status.textContent = "The request did not complete.";
    setBusy(false);
    promptBox.focus();
  }

  function normalizedPreferences(payload) {
    const value = payload?.preferences || payload || {};
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return Object.fromEntries(
      PREFERENCE_FIELDS
        .filter((key) => value[key] !== undefined && value[key] !== null && value[key] !== "")
        .map((key) => [key, value[key]])
    );
  }

  function preferenceLabel(key) {
    return {
      target_seconds: "Runtime",
      aspect_ratio: "Aspect",
      tone: "Tone",
      visual_style: "Visual",
      narration_style: "Narration",
      caption_style: "Captions",
      music_preference: "Music"
    }[key] || key;
  }

  function renderPreferences(preferences) {
    currentPreferences = normalizedPreferences(preferences);
    preferenceSummary.replaceChildren();
    Object.entries(currentPreferences).forEach(([key, rawValue]) => {
      const value = key === "target_seconds" ? `${rawValue}s` : rawValue;
      const chip = document.createElement("span");
      chip.textContent = `${preferenceLabel(key)}: ${value}`;
      preferenceSummary.appendChild(chip);
    });
    if (!preferenceSummary.children.length) {
      const empty = document.createElement("span");
      empty.className = "fine";
      empty.textContent = "No saved preferences yet.";
      preferenceSummary.appendChild(empty);
    }

    if (preferenceForm) {
      PREFERENCE_FIELDS.forEach((key) => {
        const field = preferenceForm.elements.namedItem(key);
        if (field) field.value = currentPreferences[key] ?? "";
      });
    }
  }

  async function loadPreferences() {
    try {
      const data = await requestJSON("/api/creative-director/preferences", {}, 10000);
      renderPreferences(data);
    } catch (error) {
      renderPreferences({});
      if (preferenceStatus) {
        preferenceStatus.textContent = error.status === 404
          ? "Preference memory is not available in this build."
          : "Saved preferences could not be loaded.";
      }
    }
  }

  function preferencesFromForm() {
    const preferences = {};
    PREFERENCE_FIELDS.forEach((key) => {
      const field = preferenceForm?.elements.namedItem(key);
      if (!field || field.value === "") return;
      preferences[key] = key === "target_seconds" ? Number(field.value) : field.value.trim();
    });
    return preferences;
  }

  preferenceForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = preferenceForm.querySelector("button[type='submit']");
    submit.disabled = true;
    preferenceStatus.textContent = "Saving preferences…";
    try {
      const data = await requestJSON("/api/creative-director/preferences", {
        method: "PUT",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(preferencesFromForm())
      });
      renderPreferences(data);
      preferenceStatus.textContent = "Preferences saved. Every project can still override them.";
    } catch (error) {
      preferenceStatus.textContent = error.message || "Preferences could not be saved.";
    } finally {
      submit.disabled = false;
    }
  });

  preferenceReset?.addEventListener("click", async () => {
    preferenceReset.disabled = true;
    preferenceStatus.textContent = "Clearing preferences…";
    try {
      await requestJSON("/api/creative-director/preferences", {method: "DELETE"});
      renderPreferences({});
      preferenceStatus.textContent = "Saved preferences cleared.";
    } catch (error) {
      preferenceStatus.textContent = error.message || "Preferences could not be cleared.";
    } finally {
      preferenceReset.disabled = false;
    }
  });

  async function beginConversation() {
    originalPrompt = promptBox.value.trim();
    if (!originalPrompt) {
      status.textContent = "Describe what you want to create first.";
      promptBox.focus();
      return;
    }

    answers = {};
    questions = [];
    currentQuestion = 0;
    addMessage("user", originalPrompt);
    status.textContent = "Finding only the decisions that materially affect production…";
    setBusy(true);

    try {
      const data = await requestJSON("/api/creative-director/questions", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({prompt: originalPrompt})
      }, 60000);
      questions = Array.isArray(data.questions) ? data.questions.slice(0, 5) : [];
      status.textContent = questions.length
        ? `Question 1 of ${questions.length}`
        : "Your prompt already contains enough production direction.";
      if (questions.length) showQuestion();
      else await buildBrief();
    } catch (error) {
      showError(error);
    }
  }

  send.addEventListener("click", beginConversation);
  promptBox.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      beginConversation();
    }
  });

  function showQuestion() {
    const question = questions[currentQuestion];
    if (!question || !Array.isArray(question.options)) {
      buildBrief().catch(showError);
      return;
    }
    addMessage("assistant", question.question);

    const options = document.createElement("div");
    options.className = "director-options";
    options.setAttribute("role", "group");
    options.setAttribute("aria-label", question.question);
    question.options.slice(0, 6).forEach((option) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = option;
      button.addEventListener("click", async () => {
        options.querySelectorAll("button").forEach((item) => {
          item.disabled = true;
        });
        answers[question.id] = option;
        addMessage("user", option);
        options.remove();
        currentQuestion += 1;
        if (currentQuestion < questions.length) {
          status.textContent = `Question ${currentQuestion + 1} of ${questions.length}`;
          showQuestion();
        } else {
          await buildBrief();
        }
      });
      options.appendChild(button);
    });

    chat.appendChild(options);
    options.querySelector("button")?.focus();
    chat.scrollTop = chat.scrollHeight;
  }

  async function buildBrief() {
    addMessage("assistant", "I have what I need. Building your production brief…");
    status.textContent = "Building a structured production brief…";
    try {
      const brief = await requestJSON("/api/creative-director/brief", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({prompt: originalPrompt, answers})
      }, 60000);
      if (!brief.production_specification && !brief.production_spec && !brief.specification) {
        brief.production_specification = {
          original_prompt: brief.topic || originalPrompt,
          subject: brief.topic || originalPrompt,
          target_seconds: Number(brief.target_seconds || 45),
          hook_strategy: brief.hook_type || null,
          source_brief_text: brief.creative_brief || ""
        };
      }
      addMessage("assistant", "Your production brief is ready. Review it below before starting production.");
      status.textContent = "Production brief ready.";
      window.CreatorWorkspace?.presentBrief(brief, {
        answers: {...answers},
        preferences: {...currentPreferences}
      });
    } catch (error) {
      showError(error);
    }
  }

  function resetConversation() {
    originalPrompt = "";
    answers = {};
    questions = [];
    currentQuestion = 0;
    chat.replaceChildren();
    promptBox.value = "";
    status.textContent = "";
    setBusy(false);
    addMessage(
      "assistant",
      "What would you like to create? I’ll ask only for decisions that change the production."
    );
    promptBox.focus();
  }

  document.addEventListener("mindfrontier:new-creative-project", resetConversation);
  document.addEventListener("mindfrontier:use-idea", (event) => {
    resetConversation();
    promptBox.value = String(event.detail?.prompt || "").slice(0, 3000);
    window.MindFrontierShell?.activateView("create");
    promptBox.focus();
  });

  addMessage(
    "assistant",
    "What would you like to create? I’ll ask only for decisions that change the production."
  );
  loadPreferences();
})();
