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


let dashboardProjects = [];

function renderDashboard() {
  const search = document.querySelector("#project-search").value.trim().toLowerCase();
  const filter = document.querySelector("#project-filter").value;
  const list = document.querySelector("#project-list");

  const projects = dashboardProjects.filter((project) => {
    const matchesSearch = !search || [
      project.title,
      project.topic,
      project.status,
      project.id
    ].join(" ").toLowerCase().includes(search);

    const matchesFilter = filter === "all" || project.status === filter;
    return matchesSearch && matchesFilter;
  });

  if (!projects.length) {
    list.innerHTML = '<p class="fine">No matching projects.</p>';
    return;
  }

  list.innerHTML = projects.map((project) => `
    <article class="project-card">
      <div class="project-thumb">
        ${project.thumbnail_url
          ? `<img src="${project.thumbnail_url}" alt="">`
          : '<div class="thumb-placeholder">MF</div>'}
      </div>
      <div class="project-info">
        <div class="project-title-row">
          <div>
            <p class="eyebrow">${project.status.toUpperCase()}</p>
            <h3>${project.title}</h3>
          </div>
          <span class="quality-pill">${project.quality_score || "—"}</span>
        </div>
        <p class="project-topic">${project.topic || "No topic saved"}</p>
        <div class="project-flags">
          <span>${project.has_quality_report ? "Quality ✓" : "Quality —"}</span>
          <span>${project.has_beat_map ? "Beat Map ✓" : "Beat Map —"}</span>
          <span>${project.has_metadata ? "Metadata ✓" : "Metadata —"}</span>
        </div>
        <div class="project-actions">
          ${project.video_url
            ? `<a class="small-button" href="${project.video_url}" target="_blank">Open Video</a>`
            : ""}
          <button class="small-button open-project" type="button" data-project="${project.id}">
            Details
          </button>
        </div>
      </div>
    </article>
  `).join("");
}

async function loadDashboard() {
  const list = document.querySelector("#project-list");
  try {
    const response = await fetch("/api/dashboard");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Dashboard failed.");

    dashboardProjects = data.projects;
    const statValues = [
      data.stats.total_projects,
      data.stats.ready_projects,
      data.stats.published_projects,
      data.stats.average_quality
    ];

    document.querySelectorAll("#studio-stats strong").forEach((element, index) => {
      element.textContent = statValues[index];
    });

    renderDashboard();
  } catch (error) {
    list.innerHTML = `<p class="fine">Dashboard error: ${error.message}</p>`;
  }
}

async function openProjectDetails(projectId) {
  const response = await fetch(`/api/dashboard/projects/${encodeURIComponent(projectId)}`);
  const project = await response.json();
  if (!response.ok) throw new Error(project.detail || "Could not open project.");

  const details = [
    `Title: ${project.title}`,
    `Status: ${project.status}`,
    `Quality: ${project.quality_score || "Not scored"}`,
    `Topic: ${project.topic || "Not saved"}`,
    "",
    project.release_package.description || ""
  ].join("\n");

  alert(details);
}

document.querySelector("#project-search").addEventListener("input", renderDashboard);
document.querySelector("#project-filter").addEventListener("change", renderDashboard);
document.querySelector("#refresh-projects").addEventListener("click", loadDashboard);

document.addEventListener("click", async (event) => {
  const button = event.target.closest(".open-project");
  if (!button) return;

  try {
    await openProjectDetails(button.dataset.project);
  } catch (error) {
    alert(error.message);
  }
});

loadDashboard();
