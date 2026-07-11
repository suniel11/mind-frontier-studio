(() => {
  "use strict";

  const endpoint = "/api/orchestrator/create-project";

  const state = {
    step: 0,
    answers: {
      prompt: "",
      format: "cinematic documentary",
      audience: "general audience",
      tone: "reflective",
      visualStyle: "realistic cinematic",
      narration: "calm and authoritative",
      ending: "reflective conclusion",
      targetSeconds: 45,
      constraints: []
    }
  };

  const steps = [
    {
      key: "prompt",
      title: "What do you want to create?",
      type: "textarea",
      placeholder:
        "Example: Create a documentary about why cities make people feel lonely."
    },
    {
      key: "format",
      title: "What format should it use?",
      type: "choices",
      choices: [
        "cinematic documentary",
        "video essay",
        "explainer",
        "story",
        "educational short",
        "motivational short"
      ]
    },
    {
      key: "audience",
      title: "Who is this for?",
      type: "choices",
      choices: [
        "general audience",
        "students",
        "young adults",
        "professionals",
        "creators",
        "children"
      ]
    },
    {
      key: "tone",
      title: "What should it feel like?",
      type: "choices",
      choices: [
        "reflective",
        "serious",
        "emotional",
        "suspenseful",
        "hopeful",
        "humorous"
      ]
    },
    {
      key: "visualStyle",
      title: "How should it look?",
      type: "choices",
      choices: [
        "realistic cinematic",
        "documentary",
        "symbolic",
        "minimal",
        "archival",
        "animated"
      ]
    },
    {
      key: "narration",
      title: "How should the narration sound?",
      type: "choices",
      choices: [
        "calm and authoritative",
        "conversational",
        "urgent",
        "philosophical",
        "warm",
        "dramatic"
      ]
    },
    {
      key: "ending",
      title: "How should it end?",
      type: "choices",
      choices: [
        "reflective conclusion",
        "practical takeaway",
        "open question",
        "emotional conclusion",
        "call to action"
      ]
    },
    {
      key: "targetSeconds",
      title: "How long should it be?",
      type: "choices",
      choices: [30, 45, 60, 75]
    },
    {
      key: "constraints",
      title: "Choose any production constraints",
      type: "multi",
      choices: [
        "one consistent protagonist",
        "no readable phone text",
        "short captions",
        "vertical 9:16",
        "background music",
        "no faces",
        "historically accurate visuals"
      ]
    }
  ];

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function addStyles() {
    if (document.querySelector("#creative-intake-styles")) {
      return;
    }

    const style = document.createElement("style");
    style.id = "creative-intake-styles";

    style.textContent = `
      .creative-intake-card {
        margin-top: 22px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.035);
      }

      .creative-intake-card h2 {
        margin: 0 0 6px;
      }

      .creative-intake-card p {
        color: #9299a8;
      }

      .creative-intake-progress {
        height: 6px;
        overflow: hidden;
        margin: 16px 0 20px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.06);
      }

      .creative-intake-progress span {
        display: block;
        height: 100%;
        background: #d8a956;
        transition: width 0.2s ease;
      }

      .creative-intake-options {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }

      .creative-intake-option {
        margin: 0;
        padding: 12px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.025);
        color: inherit;
        text-align: left;
        cursor: pointer;
      }

      .creative-intake-option.selected {
        border-color: rgba(216, 169, 86, 0.5);
        background: rgba(216, 169, 86, 0.12);
      }

      .creative-intake-card textarea {
        width: 100%;
        min-height: 120px;
        box-sizing: border-box;
      }

      .creative-intake-actions {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        margin-top: 18px;
      }

      .creative-intake-actions button {
        width: auto;
        margin: 0;
      }

      .creative-intake-summary {
        margin-top: 14px;
        padding: 14px;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.03);
        white-space: pre-wrap;
      }

      @media (max-width: 700px) {
        .creative-intake-options {
          grid-template-columns: 1fr;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function buildCreativeBrief() {
    const answers = state.answers;

    const constraints = answers.constraints.length
      ? answers.constraints.join(", ")
      : "none";

    return [
      `Create a ${answers.targetSeconds}-second ${answers.format} about: ${answers.prompt}`,
      `Audience: ${answers.audience}.`,
      `Tone: ${answers.tone}.`,
      `Visual direction: ${answers.visualStyle}.`,
      `Narration style: ${answers.narration}.`,
      `Ending: ${answers.ending}.`,
      `Production constraints: ${constraints}.`,
      "Use a clear hook, escalating structure, strong visual continuity, and a concise final reframe."
    ].join("\n");
  }

  function inferHookType() {
    const tone = state.answers.tone.toLowerCase();

    if (tone.includes("suspense")) {
      return "question";
    }

    if (tone.includes("emotional")) {
      return "story";
    }

    if (tone.includes("humorous")) {
      return "statement";
    }

    return "direct contradiction";
  }

  function renderStep(container) {
    const step = steps[state.step];

    const progress = Math.round(
      ((state.step + 1) / steps.length) * 100
    );

    container.innerHTML = `
      <div class="creative-intake-card">
        <p class="eyebrow">CREATIVE DIRECTOR</p>

        <h2>${escapeHtml(step.title)}</h2>

        <p>
          Step ${state.step + 1} of ${steps.length}
        </p>

        <div class="creative-intake-progress">
          <span style="width: ${progress}%"></span>
        </div>

        <div id="creative-intake-control"></div>

        <div class="creative-intake-actions">
          <button
            id="creative-intake-back"
            type="button"
            ${state.step === 0 ? "disabled" : ""}
          >
            Back
          </button>

          <button
            id="creative-intake-next"
            type="button"
          >
            ${
              state.step === steps.length - 1
                ? "Build Production Brief"
                : "Next"
            }
          </button>
        </div>
      </div>
    `;

    const control = container.querySelector(
      "#creative-intake-control"
    );

    if (step.type === "textarea") {
      control.innerHTML = `
        <textarea
          id="creative-intake-value"
          placeholder="${escapeHtml(step.placeholder || "")}"
        >${escapeHtml(state.answers[step.key] || "")}</textarea>
      `;
    }

    if (step.type === "choices") {
      control.className = "creative-intake-options";

      step.choices.forEach((choice) => {
        const button = document.createElement("button");

        button.type = "button";
        button.className = "creative-intake-option";
        button.textContent = String(choice);

        if (
          String(state.answers[step.key]) === String(choice)
        ) {
          button.classList.add("selected");
        }

        button.addEventListener("click", () => {
          state.answers[step.key] = choice;

          control
            .querySelectorAll(".creative-intake-option")
            .forEach((item) => {
              item.classList.remove("selected");
            });

          button.classList.add("selected");
        });

        control.appendChild(button);
      });
    }

    if (step.type === "multi") {
      control.className = "creative-intake-options";

      step.choices.forEach((choice) => {
        const button = document.createElement("button");

        button.type = "button";
        button.className = "creative-intake-option";
        button.textContent = String(choice);

        if (state.answers.constraints.includes(choice)) {
          button.classList.add("selected");
        }

        button.addEventListener("click", () => {
          const alreadySelected =
            state.answers.constraints.includes(choice);

          state.answers.constraints = alreadySelected
            ? state.answers.constraints.filter(
                (item) => item !== choice
              )
            : [...state.answers.constraints, choice];

          button.classList.toggle("selected");
        });

        control.appendChild(button);
      });
    }

    container
      .querySelector("#creative-intake-back")
      .addEventListener("click", () => {
        if (state.step > 0) {
          state.step -= 1;
          renderStep(container);
        }
      });

    container
      .querySelector("#creative-intake-next")
      .addEventListener("click", async () => {
        if (step.type === "textarea") {
          state.answers[step.key] = control
            .querySelector("#creative-intake-value")
            .value
            .trim();
        }

        if (
          step.key === "prompt" &&
          !state.answers.prompt
        ) {
          alert("Enter a prompt before continuing.");
          return;
        }

        if (state.step < steps.length - 1) {
          state.step += 1;
          renderStep(container);
          return;
        }

        await submitBrief(container);
      });
  }

  async function submitBrief(container) {
    const creativeBrief = buildCreativeBrief();
    const hookType = inferHookType();

    container.innerHTML = `
      <div class="creative-intake-card">
        <p class="eyebrow">PRODUCTION BRIEF</p>

        <h2>Sending your brief to Atlas</h2>

        <div class="creative-intake-summary">
          ${escapeHtml(creativeBrief)}
        </div>

        <p id="creative-intake-status">
          Building autonomous project…
        </p>
      </div>
    `;

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          topic: creativeBrief,
          target_seconds: Number(
            state.answers.targetSeconds
          ),
          hook_type: hookType,
          save_workspace: true
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Could not create the project."
        );
      }

      container.querySelector(
        "#creative-intake-status"
      ).innerHTML = `
        Project created successfully.<br>
        <strong>
          ${escapeHtml(data.project_id || "")}
        </strong><br>
        Readiness:
        ${Number(data.readiness_score || 0)}%
      `;
    } catch (error) {
      container.querySelector(
        "#creative-intake-status"
      ).textContent = `Error: ${error.message}`;
    }
  }

  function mount() {
    addStyles();

    const target =
      document.querySelector(".orchestrator-panel") ||
      document.querySelector(
        ".producer-workspace-panel"
      ) ||
      document.querySelector("#project-form") ||
      document.querySelector("main");

    if (
      !target ||
      document.querySelector("#creative-intake-root")
    ) {
      return;
    }

    const root = document.createElement("section");

    root.id = "creative-intake-root";
    root.className = "creative-intake-root";

    target.parentNode.insertBefore(root, target);

    renderStep(root);
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      mount
    );
  } else {
    mount();
  }
})();