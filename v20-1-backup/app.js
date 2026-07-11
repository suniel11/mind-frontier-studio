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


let activeOrionMission = null;

function renderOrionMission(mission) {
  activeOrionMission = mission;
  const container = document.querySelector("#orion-mission");

  container.innerHTML = `
    <div class="orion-mission-header">
      <div>
        <p class="eyebrow">${escapeHtml(mission.status.toUpperCase())}</p>
        <h3>${escapeHtml(mission.objective)}</h3>
      </div>
      <span>${mission.items.length} planned</span>
    </div>

    ${mission.items.map((item, index) => `
      <article class="orion-item">
        <div class="orion-item-main">
          <div class="orion-title-row">
            <div>
              <p class="eyebrow">${escapeHtml(item.category.toUpperCase())}</p>
              <h4>${escapeHtml(item.title)}</h4>
            </div>
            <span class="orion-score">${item.score}</span>
          </div>

          <p>${escapeHtml(item.prompt)}</p>

          <div class="orion-meta">
            <span>${escapeHtml(item.verdict)}</span>
            <span>Status: ${escapeHtml(item.status)}</span>
            ${item.project_id ? `<span>Project: ${escapeHtml(item.project_id)}</span>` : ""}
          </div>

          ${item.error ? `<p class="orion-error">${escapeHtml(item.error)}</p>` : ""}

          <ul>
            ${item.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}
          </ul>
        </div>

        <button
          type="button"
          class="orion-produce small-button"
          data-index="${index}"
          ${item.status === "running" || item.status === "complete" ? "disabled" : ""}
        >
          ${item.status === "complete" ? "Produced" : "Produce This"}
        </button>
      </article>
    `).join("")}
  `;
}

document.querySelector("#orion-plan")?.addEventListener("click", async () => {
  const status = document.querySelector("#orion-status");
  const objective = document.querySelector("#orion-objective").value.trim();
  const count = Number(document.querySelector("#orion-count").value);

  if (objective.length < 8) {
    status.textContent = "Enter a more specific production objective.";
    return;
  }

  status.textContent = "Planning mission…";

  try {
    const response = await fetch("/api/orion/plan", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        objective,
        count,
        target_seconds: Number(document.querySelector("#seconds")?.value || 45)
      })
    });
    const mission = await response.json();
    if (!response.ok) {
      throw new Error(mission.detail || "Mission planning failed.");
    }

    status.textContent =
      "Mission ready. Review the topics before spending API credits.";
    renderOrionMission(mission);
  } catch (error) {
    status.textContent = `Error: ${error.message}`;
  }
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest(".orion-produce");
  if (!button || !activeOrionMission) return;

  const status = document.querySelector("#orion-status");
  const index = Number(button.dataset.index);

  button.disabled = true;
  button.textContent = "Producing…";
  status.textContent =
    "Running the full production pipeline. Keep the Studio open.";

  try {
    const response = await fetch(
      `/api/orion/missions/${encodeURIComponent(activeOrionMission.mission_id)}/execute`,
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({item_index: index})
      }
    );
    const mission = await response.json();
    if (!response.ok) {
      throw new Error(mission.detail || "Production failed.");
    }

    status.textContent = "Production complete.";
    renderOrionMission(mission);

    if (typeof loadDashboard === "function") {
      await loadDashboard();
    }
    if (typeof loadAtlas === "function") {
      await loadAtlas();
    }
  } catch (error) {
    status.textContent = `Production error: ${error.message}`;
    button.disabled = false;
    button.textContent = "Retry";
  }
});


let activeApolloQueue = null;

function renderApolloQueue(queue) {
  activeApolloQueue = queue;
  const container = document.querySelector("#apollo-queue");

  container.innerHTML = `
    <div class="apollo-queue-header">
      <div>
        <p class="eyebrow">${escapeHtml(queue.status.toUpperCase())}</p>
        <h3>${escapeHtml(queue.objective)}</h3>
      </div>
      <div class="apollo-counts">
        <span>${queue.completed_count} complete</span>
        <span>${queue.remaining_count} remaining</span>
        <span>${queue.failed_count} failed</span>
      </div>
    </div>

    <div class="apollo-actions">
      <button id="apollo-run-one" type="button" class="small-button">
        Run Next
      </button>
      <button id="apollo-run-three" type="button" class="small-button">
        Run Next 3
      </button>
      <button id="apollo-pause" type="button" class="small-button">
        ${queue.status === "paused" ? "Resume" : "Pause"}
      </button>
    </div>

    <div class="apollo-items">
      ${queue.items.map((item, index) => `
        <article class="apollo-item">
          <div>
            <p class="eyebrow">${escapeHtml(item.category.toUpperCase())}</p>
            <h4>${index + 1}. ${escapeHtml(item.title)}</h4>
            <p>${escapeHtml(item.prompt)}</p>
            <div class="apollo-meta">
              <span>Score ${item.score}</span>
              <span>Status ${escapeHtml(item.status)}</span>
              ${item.project_id ? `<span>${escapeHtml(item.project_id)}</span>` : ""}
            </div>
            ${item.error ? `<p class="apollo-error">${escapeHtml(item.error)}</p>` : ""}
          </div>
        </article>
      `).join("")}
    </div>
  `;
}

async function runApollo(maxItems) {
  if (!activeApolloQueue) return;
  const status = document.querySelector("#apollo-status");
  status.textContent =
    `Rendering up to ${maxItems} item(s). Keep the Studio open.`;

  try {
    const response = await fetch(
      `/api/apollo/queues/${encodeURIComponent(activeApolloQueue.queue_id)}/run`,
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({max_items: maxItems})
      }
    );
    const queue = await response.json();
    if (!response.ok) throw new Error(queue.detail || "Apollo failed.");

    renderApolloQueue(queue);
    status.textContent = "Apollo queue updated.";

    if (typeof loadDashboard === "function") await loadDashboard();
    if (typeof loadAtlas === "function") await loadAtlas();
  } catch (error) {
    status.textContent = `Apollo error: ${error.message}`;
  }
}

document.querySelector("#apollo-create")?.addEventListener("click", async () => {
  const objective = document.querySelector("#apollo-objective").value.trim();
  const count = Number(document.querySelector("#apollo-count").value);
  const status = document.querySelector("#apollo-status");

  if (objective.length < 8) {
    status.textContent = "Enter a more specific batch objective.";
    return;
  }

  status.textContent = "Planning queue…";

  try {
    const response = await fetch("/api/apollo/queues", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        objective,
        count,
        target_seconds: Number(document.querySelector("#seconds")?.value || 45)
      })
    });
    const queue = await response.json();
    if (!response.ok) throw new Error(queue.detail || "Queue creation failed.");

    renderApolloQueue(queue);
    status.textContent =
      "Queue ready. Review it before starting production.";
  } catch (error) {
    status.textContent = `Apollo error: ${error.message}`;
  }
});

document.addEventListener("click", async (event) => {
  if (event.target?.id === "apollo-run-one") {
    await runApollo(1);
  }

  if (event.target?.id === "apollo-run-three") {
    await runApollo(3);
  }

  if (event.target?.id === "apollo-pause" && activeApolloQueue) {
    const pause = activeApolloQueue.status !== "paused";
    const action = pause ? "pause" : "resume";
    const response = await fetch(
      `/api/apollo/queues/${encodeURIComponent(activeApolloQueue.queue_id)}/${action}`,
      {method: "POST"}
    );
    const queue = await response.json();
    renderApolloQueue(queue);
  }
});


async function loadOperationsHealth() {
  const status = document.querySelector("#operations-status");
  if (!status) return;

  try {
    const [healthResponse, failuresResponse] = await Promise.all([
      fetch("/api/operations/health"),
      fetch("/api/operations/recent-failures")
    ]);

    const health = await healthResponse.json();
    const failures = await failuresResponse.json();

    if (!healthResponse.ok) {
      throw new Error(health.detail || "Health check failed.");
    }

    status.innerHTML = `
      <div class="operations-overall ${health.ok ? "ok" : "warning"}">
        <strong>${health.status.replaceAll("_", " ").toUpperCase()}</strong>
      </div>
      <div class="operations-checks">
        ${Object.entries(health.checks).map(([name, check]) => `
          <article class="operation-check ${check.ok ? "ok" : "warning"}">
            <span>${escapeHtml(name.replaceAll("_", " "))}</span>
            <strong>${check.ok ? "PASS" : "CHECK"}</strong>
            <small>${escapeHtml(check.detail)}</small>
          </article>
        `).join("")}
      </div>
    `;

    const failureList = document.querySelector("#operations-failure-list");
    failureList.innerHTML = failures.failures.length
      ? failures.failures.map((failure) => `
          <article class="operation-failure">
            <strong>${escapeHtml(failure.stage)}</strong>
            <span>${escapeHtml(failure.project_id)}</span>
            <p>${escapeHtml(failure.error)}</p>
          </article>
        `).join("")
      : '<p class="fine">No recent pipeline failures.</p>';
  } catch (error) {
    status.innerHTML =
      `<p class="fine">Operations unavailable: ${escapeHtml(error.message)}</p>`;
  }
}

document.querySelector("#operations-refresh")?.addEventListener(
  "click",
  loadOperationsHealth
);

loadOperationsHealth();


async function loadYouTubeSync() {
  const content = document.querySelector("#youtube-sync-content");
  const badge = document.querySelector("#youtube-sync-state");
  if (!content || !badge) return;

  try {
    const response = await fetch("/api/youtube/status");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "YouTube status failed.");
    }

    if (!data.client_secret_configured) {
      badge.textContent = "SETUP REQUIRED";
      content.innerHTML = `
        <p>Place <code>client_secret.json</code> in the Studio root folder.</p>
        <p class="fine">
          Enable YouTube Data API v3 and YouTube Analytics API in Google Cloud,
          then use the local OAuth redirect URI.
        </p>
      `;
      return;
    }

    if (!data.connected) {
      badge.textContent = "NOT CONNECTED";
      content.innerHTML = `
        <p>Connect the Google account that owns your YouTube channel.</p>
        <button id="youtube-connect" type="button" class="small-button">
          Connect YouTube
        </button>
      `;
      return;
    }

    badge.textContent = "CONNECTED";
    const channels = data.channels || [];
    content.innerHTML = `
      <div class="youtube-channel-list">
        ${channels.map((channel) => `
          <article class="youtube-channel-card">
            ${channel.thumbnail
              ? `<img src="${channel.thumbnail}" alt="">`
              : ""}
            <div>
              <strong>${escapeHtml(channel.title || "YouTube Channel")}</strong>
              <span>${Number(channel.subscriber_count || 0).toLocaleString()} subscribers</span>
              <span>${Number(channel.video_count || 0).toLocaleString()} videos</span>
              <span>${Number(channel.view_count || 0).toLocaleString()} views</span>
            </div>
          </article>
        `).join("") || "<p>No owned channel was returned.</p>"}
      </div>
      <button id="youtube-disconnect" type="button" class="small-button">
        Disconnect
      </button>
    `;
  } catch (error) {
    badge.textContent = "ERROR";
    content.innerHTML =
      `<p class="fine">YouTube Sync error: ${escapeHtml(error.message)}</p>`;
  }
}

document.addEventListener("click", async (event) => {
  if (event.target?.id === "youtube-connect") {
    const response = await fetch("/api/youtube/connect", {method: "POST"});
    const data = await response.json();

    if (!response.ok) {
      alert(data.detail || "Could not start YouTube connection.");
      return;
    }

    const popup = window.open(
      data.authorization_url,
      "youtube-oauth",
      "width=620,height=760"
    );

    if (!popup) {
      window.location.href = data.authorization_url;
      return;
    }

    const timer = setInterval(async () => {
      if (popup.closed) {
        clearInterval(timer);
        await loadYouTubeSync();
      }
    }, 800);
  }

  if (event.target?.id === "youtube-disconnect") {
    await fetch("/api/youtube/disconnect", {method: "POST"});
    await loadYouTubeSync();
  }
});

loadYouTubeSync();
