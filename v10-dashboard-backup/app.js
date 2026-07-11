const form = document.querySelector("#project-form");
const statusBox = document.querySelector("#status");
const resultBox = document.querySelector("#result");
const generateButton = document.querySelector("#generate");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  resultBox.hidden = true;
  generateButton.disabled = true;
  generateButton.textContent = "Generating…";
  statusBox.textContent =
    "Writing, generating narration and six visuals, then rendering the MP4. This may take several minutes. Keep this page open.";

  try {
    const response = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: document.querySelector("#topic").value.trim(),
        target_seconds: Number(document.querySelector("#seconds").value)
      })
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Video generation failed.");

    document.querySelector("#title").textContent = data.script.title;
    document.querySelector("#voiceover").textContent = data.script.voiceover;
    document.querySelector("#description").textContent = data.seo.description;
    document.querySelector("#hashtags").textContent = data.seo.hashtags.join(" ");

    const video = document.querySelector("#video");
    video.src = data.video_url;
    video.load();

    const download = document.querySelector("#download");
    download.href = data.video_url;

    resultBox.hidden = false;
    statusBox.textContent = `Finished and saved as project: ${data.project_id}`;
  } catch (error) {
    statusBox.textContent = `Error: ${error.message}`;
  } finally {
    generateButton.disabled = false;
    generateButton.textContent = "Generate Video";
  }
});


async function loadContentIdeas() {
  const panel = document.querySelector("#content-ideas");
  if (!panel) return;

  try {
    const response = await fetch("/api/content-plan?limit=5");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not load ideas.");

    panel.innerHTML = data.ideas.map((idea, index) => `
      <article class="idea-card">
        <div class="idea-rank">#${index + 1}</div>
        <div class="idea-body">
          <div class="idea-head">
            <div>
              <p class="eyebrow">${idea.category.toUpperCase()}</p>
              <h3>${idea.title}</h3>
            </div>
            <span class="idea-score">${idea.overall_score}/100</span>
          </div>
          <p>${idea.reason}</p>
          <div class="idea-meta">
            <span>Curiosity ${idea.curiosity_score}</span>
            <span>Evergreen ${idea.evergreen_score}</span>
            <span>Emotion ${idea.emotional_score}</span>
          </div>
          <button
            type="button"
            class="use-idea"
            data-prompt="${encodeURIComponent(idea.prompt)}"
          >
            Use This Topic
          </button>
        </div>
      </article>
    `).join("");
  } catch (error) {
    panel.innerHTML = `<p class="fine">Content planner unavailable: ${error.message}</p>`;
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest(".use-idea");
  if (!button) return;

  const topic = document.querySelector("#topic");
  topic.value = decodeURIComponent(button.dataset.prompt);
  topic.focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

loadContentIdeas();
