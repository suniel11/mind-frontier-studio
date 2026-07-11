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


const workspace = document.querySelector("#project-workspace");
let activeWorkspaceProject = null;

function prettyJson(value) {
  return `<pre>${escapeHtml(JSON.stringify(value || {}, null, 2))}</pre>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderWorkspacePane(name) {
  document.querySelectorAll(".workspace-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });

  document.querySelectorAll(".workspace-pane").forEach((pane) => {
    pane.classList.remove("active");
  });

  const map = {
    script: "#workspace-script",
    quality: "#workspace-quality-pane",
    metadata: "#workspace-metadata",
    beats: "#workspace-beats",
    render: "#workspace-render"
  };

  document.querySelector(map[name]).classList.add("active");
}

function scriptHtml(project) {
  const script = project.project?.script || {};
  const title = escapeHtml(script.title || project.title);
  const hook = escapeHtml(script.hook || "");
  const voiceover = escapeHtml(script.voiceover || "");

  return `
    <article class="workspace-document">
      <h3>${title}</h3>
      ${hook ? `<h4>Hook</h4><p>${hook}</p>` : ""}
      <h4>Voiceover</h4>
      <p class="workspace-voiceover">${voiceover || "No script saved."}</p>
    </article>
  `;
}

function qualityHtml(project) {
  const report = project.quality_report || {};
  const issues = report.issues || [];
  const recommendations = report.recommendations || [];

  return `
    <div class="quality-grid">
      ${[
        ["Overall", report.overall_score],
        ["Hook", report.hook_score],
        ["Story", report.story_score],
        ["Continuity", report.continuity_score],
        ["Camera", report.cinematography_score],
        ["Captions", report.caption_score],
        ["Audio", report.audio_score]
      ].map(([label, score]) => `
        <div class="quality-card">
          <span>${label}</span>
          <strong>${score ?? "—"}</strong>
        </div>
      `).join("")}
    </div>

    <h4>Issues</h4>
    ${issues.length
      ? `<ul>${issues.map((issue) => `<li><strong>${escapeHtml(issue.severity || "")}</strong> — ${escapeHtml(issue.message || "")}</li>`).join("")}</ul>`
      : "<p>No issues recorded.</p>"}

    <h4>Recommendations</h4>
    ${recommendations.length
      ? `<ul>${recommendations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
      : "<p>No recommendations recorded.</p>"}
  `;
}

function metadataHtml(project) {
  const data = project.release_package || {};
  return `
    <article class="workspace-document">
      <h4>Title</h4>
      <p>${escapeHtml(data.title || "")}</p>

      <h4>Description</h4>
      <p>${escapeHtml(data.description || "")}</p>

      <h4>Hashtags</h4>
      <p>${escapeHtml((data.hashtags || []).join(" "))}</p>

      <h4>Pinned Comment</h4>
      <p>${escapeHtml(data.pinned_comment || "")}</p>

      <h4>Publish Ready</h4>
      <p>${data.publish_ready ? "Yes" : "No"}</p>
    </article>
  `;
}

async function openProjectWorkspace(projectId) {
  const response = await fetch(`/api/dashboard/projects/${encodeURIComponent(projectId)}`);
  const project = await response.json();

  if (!response.ok) {
    throw new Error(project.detail || "Could not open project.");
  }

  activeWorkspaceProject = project;

  document.querySelector("#workspace-title").textContent = project.title;
  document.querySelector("#workspace-status").textContent = project.status;
  document.querySelector("#workspace-quality").textContent = project.quality_score || "—";
  document.querySelector("#workspace-topic").textContent = project.topic || "Not saved";

  const video = document.querySelector("#workspace-video");
  if (project.video_url) {
    video.src = project.video_url;
    video.hidden = false;
    video.load();
  } else {
    video.removeAttribute("src");
    video.hidden = true;
  }

  const thumbnail = document.querySelector("#workspace-thumbnail");
  if (project.thumbnail_url) {
    thumbnail.src = project.thumbnail_url;
    thumbnail.hidden = false;
  } else {
    thumbnail.hidden = true;
  }

  document.querySelector("#workspace-script").innerHTML = scriptHtml(project);
  document.querySelector("#workspace-quality-pane").innerHTML = qualityHtml(project);
  document.querySelector("#workspace-metadata").innerHTML = metadataHtml(project);
  document.querySelector("#workspace-beats").innerHTML = prettyJson(project.beat_map);
  document.querySelector("#workspace-render").innerHTML = prettyJson(project.render_graph);

  const base = `/projects/${encodeURIComponent(project.id)}`;
  document.querySelector("#workspace-download-video").href = `${base}/mind-frontier-short.mp4`;
  document.querySelector("#workspace-download-thumbnail").href = `${base}/thumbnail.jpg`;
  document.querySelector("#workspace-download-metadata").href = `${base}/release-package.json`;

  renderWorkspacePane("script");
  workspace.showModal();
}

document.querySelector("#close-workspace").addEventListener("click", () => {
  workspace.close();
});

workspace.addEventListener("click", (event) => {
  if (event.target === workspace) {
    workspace.close();
  }
});

document.querySelectorAll(".workspace-tab").forEach((button) => {
  button.addEventListener("click", () => renderWorkspacePane(button.dataset.tab));
});

document.querySelector("#workspace-copy-metadata").addEventListener("click", async () => {
  if (!activeWorkspaceProject) return;

  const metadata = activeWorkspaceProject.release_package || {};
  const text = [
    `TITLE\n${metadata.title || ""}`,
    `DESCRIPTION\n${metadata.description || ""}`,
    `HASHTAGS\n${(metadata.hashtags || []).join(" ")}`,
    `PINNED COMMENT\n${metadata.pinned_comment || ""}`
  ].join("\n\n");

  await navigator.clipboard.writeText(text);
  alert("Metadata copied.");
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest(".open-project");
  if (!button) return;

  event.preventDefault();

  try {
    await openProjectWorkspace(button.dataset.project);
  } catch (error) {
    alert(error.message);
  }
});


async function loadProducerBrief() {
  const recommendation = document.querySelector("#producer-recommendation");
  if (!recommendation) return;

  try {
    const response = await fetch("/api/producer/brief");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Producer unavailable.");

    document.querySelector("#producer-greeting").textContent =
      `${data.greeting}, Sunil. Today's studio brief`;

    document.querySelector("#producer-health-score").textContent =
      `${data.channel_health.health_score}/100`;

    const item = data.recommendation;
    recommendation.innerHTML = item ? `
      <p class="eyebrow">${item.category.toUpperCase()}</p>
      <h3>${item.title}</h3>
      <div class="producer-metrics">
        <span>Recommendation ${item.score}</span>
        <span>Confidence ${item.confidence}%</span>
        <span>Audience fit ${item.assessment.audience_fit}</span>
      </div>
      <ul>
        ${item.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}
      </ul>
      <button
        type="button"
        class="producer-use-topic"
        data-prompt="${encodeURIComponent(item.prompt)}"
      >
        Use Producer Recommendation
      </button>
    ` : "<p>No recommendation available.</p>";

    document.querySelector("#producer-calendar").innerHTML =
      data.weekly_calendar.map((entry) => `
        <article class="calendar-card">
          <div>
            <p class="eyebrow">${entry.day.toUpperCase()}</p>
            <strong>${entry.title}</strong>
            <small>${entry.category} · ${entry.score}/100</small>
          </div>
          <button
            type="button"
            class="producer-use-topic small-button"
            data-prompt="${encodeURIComponent(entry.prompt)}"
          >
            Use
          </button>
        </article>
      `).join("");
  } catch (error) {
    recommendation.innerHTML = `<p class="fine">Producer unavailable: ${error.message}</p>`;
  }
}

document.addEventListener("click", (event) => {
  const button = event.target.closest(".producer-use-topic");
  if (!button) return;

  const topic = document.querySelector("#topic");
  topic.value = decodeURIComponent(button.dataset.prompt);
  topic.focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

document.querySelector("#analyze-topic")?.addEventListener("click", async () => {
  const topic = document.querySelector("#producer-topic").value.trim();
  const output = document.querySelector("#producer-analysis");

  if (topic.length < 8) {
    output.innerHTML = '<p class="fine">Enter a more specific topic.</p>';
    return;
  }

  output.innerHTML = '<p class="fine">Analyzing…</p>';

  try {
    const response = await fetch("/api/producer/analyze", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({topic})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Analysis failed.");

    output.innerHTML = `
      <div class="producer-analysis-card">
        <div class="producer-verdict-row">
          <strong>${data.verdict}</strong>
          <span>${data.overall_score}/100</span>
        </div>
        <div class="producer-metrics">
          <span>Hook ${data.hook_score}</span>
          <span>Curiosity ${data.curiosity_score}</span>
          <span>Audience ${data.audience_fit}</span>
          <span>Originality ${data.originality_score}</span>
        </div>
        <ul>
          ${data.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}
        </ul>
        <p><strong>Suggested angle:</strong> ${escapeHtml(data.suggested_angle)}</p>
      </div>
    `;
  } catch (error) {
    output.innerHTML = `<p class="fine">Analysis failed: ${error.message}</p>`;
  }
});

loadProducerBrief();


let atlasData = null;

function atlasNumber(value) {
  return Number(value || 0).toLocaleString();
}

function renderAtlas(data, evidence) {
  atlasData = data;

  const values = [
    data.summary.total_projects,
    data.summary.published_projects,
    data.summary.average_quality || 0,
    data.summary.average_cinema || 0,
    data.youtube_summary.total_views || 0,
    data.youtube_summary.average_percentage_viewed || 0
  ];

  document.querySelectorAll("#atlas-summary strong").forEach((element, index) => {
    const value = values[index];
    element.textContent = index === 4 ? atlasNumber(value) : value;
  });

  const recommendations = document.querySelector("#atlas-recommendations");
  recommendations.innerHTML = `
    <p class="fine">Published sample size: ${evidence.sample_size}</p>
    <ul>
      ${evidence.recommendations.map((item) =>
        `<li>${escapeHtml(item)}</li>`
      ).join("")}
    </ul>
  `;

  const topics = document.querySelector("#atlas-topics");
  const maxCount = Math.max(
    1,
    ...data.topic_distribution.map((item) => Number(item.count || 0))
  );
  topics.innerHTML = data.topic_distribution.map((item) => `
    <div class="atlas-bar-row">
      <span>${escapeHtml(item.category)}</span>
      <div class="atlas-bar-track">
        <div class="atlas-bar-fill"
          style="width:${Math.round(Number(item.count) / maxCount * 100)}%">
        </div>
      </div>
      <strong>${item.count}</strong>
    </div>
  `).join("") || '<p class="fine">No projects recorded.</p>';

  const select = document.querySelector("#atlas-project");
  select.innerHTML = data.projects.map((project) => `
    <option value="${escapeHtml(project.project_id)}">
      ${escapeHtml(project.title)}
    </option>
  `).join("");

  const table = document.querySelector("#atlas-project-table");
  table.innerHTML = data.projects.map((project) => `
    <div class="atlas-project-row">
      <div>
        <strong>${escapeHtml(project.title)}</strong>
        <small>${escapeHtml(project.category)} · ${escapeHtml(project.status)}</small>
      </div>
      <span>Q ${project.quality_score || "—"}</span>
      <span>C ${project.cinema_score || "—"}</span>
      <span>${atlasNumber(project.views)} views</span>
      <span>${project.average_percentage_viewed || "—"}% retained</span>
    </div>
  `).join("") || '<p class="fine">No Atlas projects yet.</p>';
}

async function loadAtlas() {
  const recommendations = document.querySelector("#atlas-recommendations");
  if (!recommendations) return;

  try {
    const [dashboardResponse, evidenceResponse] = await Promise.all([
      fetch("/api/atlas/dashboard"),
      fetch("/api/atlas/recommendations")
    ]);
    const dashboard = await dashboardResponse.json();
    const evidence = await evidenceResponse.json();

    if (!dashboardResponse.ok) {
      throw new Error(dashboard.detail || "Atlas dashboard failed.");
    }
    if (!evidenceResponse.ok) {
      throw new Error(evidence.detail || "Atlas learning failed.");
    }

    renderAtlas(dashboard, evidence);
  } catch (error) {
    recommendations.innerHTML =
      `<p class="fine">Atlas unavailable: ${escapeHtml(error.message)}</p>`;
  }
}

document.querySelector("#atlas-refresh")?.addEventListener("click", async () => {
  await fetch("/api/atlas/sync", {method: "POST"});
  await loadAtlas();
});

document.querySelector("#atlas-save-metrics")?.addEventListener("click", async () => {
  const status = document.querySelector("#atlas-metric-status");
  const projectId = document.querySelector("#atlas-project").value;

  if (!projectId) {
    status.textContent = "Select a project first.";
    return;
  }

  status.textContent = "Saving…";

  const payload = {
    project_id: projectId,
    views: Number(document.querySelector("#atlas-views").value || 0),
    likes: Number(document.querySelector("#atlas-likes").value || 0),
    comments: Number(document.querySelector("#atlas-comments").value || 0),
    subscribers_gained: Number(document.querySelector("#atlas-subs").value || 0),
    average_percentage_viewed:
      Number(document.querySelector("#atlas-retention").value || 0),
    viewed_percentage:
      Number(document.querySelector("#atlas-viewed").value || 0),
    swiped_away_percentage:
      Math.max(0, 100 - Number(document.querySelector("#atlas-viewed").value || 0))
  };

  try {
    const response = await fetch("/api/atlas/youtube-metrics", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not save metrics.");

    status.textContent = "Metrics saved.";
    await loadAtlas();
  } catch (error) {
    status.textContent = `Error: ${error.message}`;
  }
});

loadAtlas();
