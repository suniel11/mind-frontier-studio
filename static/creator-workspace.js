(() => {
  "use strict";

  const ACTIVE_JOB_KEY = "mind-frontier-active-production-job";
  const POLL_DELAY_MS = 2000;
  const TERMINAL_STATUSES = new Set(["complete", "completed", "failed", "cancelled", "canceled"]);
  const PIPELINE_STAGES = [
    "preflight",
    "research",
    "script",
    "producer_review",
    "character",
    "storyboard",
    "narrative_beats",
    "director",
    "visual_storytelling",
    "cinema_direction",
    "prompt_compilation",
    "seo",
    "storage",
    "voice_generation",
    "image_generation",
    "render",
    "quality_inspection",
    "thumbnail",
    "release_package",
    "publish_package",
    "memory",
    "complete"
  ];

  const elements = {
    workspace: document.querySelector("#creator-workspace"),
    brief: document.querySelector("#production-brief-text"),
    preferences: document.querySelector("#production-preferences-used"),
    status: document.querySelector("#production-workspace-status"),
    badge: document.querySelector("#production-job-badge"),
    start: document.querySelector("#production-start"),
    cancel: document.querySelector("#production-cancel"),
    retry: document.querySelector("#production-retry"),
    newVersion: document.querySelector("#production-new-version"),
    newIdea: document.querySelector("#production-new-idea"),
    progressPanel: document.querySelector("#production-progress-panel"),
    progress: document.querySelector("#production-progress"),
    progressValue: document.querySelector("#production-progress-value"),
    currentStage: document.querySelector("#production-current-stage"),
    timeline: document.querySelector("#production-stage-timeline"),
    warningsPanel: document.querySelector("#production-warnings-panel"),
    warnings: document.querySelector("#production-warnings-list"),
    errorPanel: document.querySelector("#production-error-panel"),
    error: document.querySelector("#production-error-message"),
    results: document.querySelector("#production-results"),
    research: document.querySelector("#production-research"),
    script: document.querySelector("#production-script"),
    storyboard: document.querySelector("#production-storyboard"),
    media: document.querySelector("#production-media"),
    video: document.querySelector("#production-final-video"),
    videoEmpty: document.querySelector("#production-video-empty"),
    thumbnail: document.querySelector("#production-thumbnail"),
    thumbnailEmpty: document.querySelector("#production-thumbnail-empty"),
    publishTitle: document.querySelector("#production-publish-title"),
    publishDescription: document.querySelector("#production-publish-description"),
    publishHashtags: document.querySelector("#production-publish-hashtags"),
    links: document.querySelector("#production-output-links")
  };

  if (!elements.workspace) return;

  let currentBrief = null;
  let currentSpecification = null;
  let currentJobId = null;
  let currentJob = null;
  let pollTimer = null;
  let pollController = null;

  function safeStorageGet(key) {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  }

  function safeStorageSet(key, value) {
    try {
      if (value) localStorage.setItem(key, value);
      else localStorage.removeItem(key);
    } catch {
      // A blocked storage API should not prevent production.
    }
  }

  function normalizedStatus(value) {
    return String(value || "queued").trim().toLowerCase();
  }

  function titleCase(value) {
    return String(value || "")
      .replaceAll("-", "_")
      .split("_")
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");
  }

  function clampPercent(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return 0;
    return Math.max(0, Math.min(100, Math.round(number)));
  }

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
        const message = typeof data.detail === "string" ? data.detail : "The request could not be completed.";
        const error = new Error(message);
        error.status = response.status;
        throw error;
      }
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("The Studio did not respond in time.");
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  function safeOutputUrl(value) {
    if (typeof value !== "string" || !value.trim()) return null;
    try {
      const parsed = new URL(value, window.location.origin);
      if (parsed.origin !== window.location.origin) return null;
      const allowed = ["/projects/", "/api/production/", "/api/projects/"];
      if (!allowed.some((prefix) => parsed.pathname.startsWith(prefix))) return null;
      return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    } catch {
      return null;
    }
  }

  function clearElement(element) {
    if (element) element.replaceChildren();
  }

  function appendParagraph(parent, text, className = "") {
    if (!parent || text === undefined || text === null || text === "") return;
    const paragraph = document.createElement("p");
    if (className) paragraph.className = className;
    paragraph.textContent = String(text);
    parent.appendChild(paragraph);
  }

  function appendDefinition(parent, label, value) {
    if (value === undefined || value === null || value === "") return;
    const wrapper = document.createElement("div");
    const term = document.createElement("strong");
    term.textContent = label;
    const description = document.createElement("span");
    description.textContent = Array.isArray(value) ? value.join(", ") : String(value);
    wrapper.append(term, description);
    parent.appendChild(wrapper);
  }

  function normalizedSpecification(brief) {
    const supplied = brief?.production_specification || brief?.production_spec || brief?.specification;
    if (supplied && typeof supplied === "object" && !Array.isArray(supplied)) return supplied;
    return {
      original_prompt: brief?.topic || "Untitled creative project",
      subject: brief?.topic || "Untitled creative project",
      target_seconds: Number(brief?.target_seconds || 45),
      hook_strategy: brief?.hook_type || null,
      source_brief_text: brief?.creative_brief || ""
    };
  }

  function renderPreferenceChips(values) {
    clearElement(elements.preferences);
    const stableKeys = [
      ["target_seconds", "Runtime", (value) => `${value}s`],
      ["aspect_ratio", "Aspect", String],
      ["tone", "Tone", String],
      ["visual_style", "Visual", String],
      ["narration_style", "Narration", String],
      ["caption_style", "Captions", String],
      ["music_preference", "Music", String],
      ["music_direction", "Music", String]
    ];
    const seen = new Set();
    stableKeys.forEach(([key, label, format]) => {
      const value = values?.[key];
      if (value === undefined || value === null || value === "" || seen.has(label)) return;
      seen.add(label);
      const chip = document.createElement("span");
      chip.textContent = `${label}: ${format(value)}`;
      elements.preferences.appendChild(chip);
    });
    if (!elements.preferences.children.length) {
      appendParagraph(elements.preferences, "No saved preferences were applied.", "fine");
    }
  }

  function presentBrief(brief, context = {}) {
    currentBrief = brief;
    currentSpecification = normalizedSpecification(brief);
    elements.workspace.hidden = false;
    elements.brief.textContent = brief?.creative_brief || "Production brief ready.";
    renderPreferenceChips({...context.preferences, ...currentSpecification});
    elements.status.textContent = "Review the brief, then start production.";
    elements.badge.textContent = "BRIEF READY";
    elements.badge.dataset.status = "brief";
    elements.start.hidden = false;
    elements.start.disabled = false;
    elements.retry.hidden = true;
    elements.cancel.hidden = true;
    elements.newVersion.hidden = true;
    elements.progressPanel.hidden = true;
    elements.errorPanel.hidden = true;
    elements.results.hidden = true;
    elements.workspace.scrollIntoView({behavior: "smooth", block: "start"});
  }

  function normalizeJobResponse(payload) {
    if (payload?.job && typeof payload.job === "object") return {...payload.job};
    return {...(payload || {})};
  }

  function stageNames(job) {
    if (Array.isArray(job.stages) && job.stages.length) {
      return job.stages.map((stage) =>
        typeof stage === "string" ? stage : stage.name || stage.stage || stage.id
      ).filter(Boolean);
    }
    return PIPELINE_STAGES;
  }

  function completedStageSet(job) {
    const completed = Array.isArray(job.completed_stages) ? job.completed_stages : [];
    return new Set(
      completed.map((stage) =>
        String(typeof stage === "string" ? stage : stage.name || stage.stage || stage.id || "")
      )
    );
  }

  function stageRecord(job, name) {
    if (!Array.isArray(job.stages)) return null;
    return job.stages.find((stage) => {
      if (typeof stage === "string") return stage === name;
      return (stage.name || stage.stage || stage.id) === name;
    });
  }

  function renderTimeline(job) {
    clearElement(elements.timeline);
    const completed = completedStageSet(job);
    const current = String(job.current_stage || "");
    const jobStatus = normalizedStatus(job.status);
    stageNames(job).forEach((name) => {
      const record = stageRecord(job, name);
      let status = String(record?.status || "pending").toLowerCase();
      if (completed.has(name)) status = "complete";
      else if (name === current && !TERMINAL_STATUSES.has(jobStatus)) status = "running";
      else if (name === current && jobStatus === "failed") status = "failed";
      else if (name === current && (jobStatus === "cancelled" || jobStatus === "canceled")) status = "cancelled";

      const item = document.createElement("li");
      item.className = `production-stage ${status}`;
      item.dataset.stage = name;
      const marker = document.createElement("span");
      marker.className = "production-stage-marker";
      marker.setAttribute("aria-hidden", "true");
      const label = document.createElement("strong");
      label.textContent = titleCase(name);
      const state = document.createElement("span");
      state.textContent = titleCase(status);
      item.append(marker, label, state);
      elements.timeline.appendChild(item);
    });
  }

  function renderWarnings(job) {
    clearElement(elements.warnings);
    const warnings = Array.isArray(job.warnings) ? job.warnings : [];
    elements.warningsPanel.hidden = !warnings.length;
    warnings.forEach((warning) => {
      const item = document.createElement("li");
      item.textContent = typeof warning === "string" ? warning : warning.message || "Production warning";
      elements.warnings.appendChild(item);
    });
  }

  function contentRoot(job) {
    return job.result || job.output || job.outputs || {};
  }

  function projectRoot(job) {
    const output = contentRoot(job);
    return job.project_detail || output.project_detail || output.project || job.project || output;
  }

  function renderResearch(value) {
    clearElement(elements.research);
    if (!value) return;
    if (typeof value === "string") return appendParagraph(elements.research, value);
    appendParagraph(elements.research, value.research_brief || value.summary || value.core_insight || "");
    const points = value.verified_points || value.key_points || value.content_gaps || [];
    if (Array.isArray(points) && points.length) {
      const list = document.createElement("ul");
      points.forEach((point) => {
        const item = document.createElement("li");
        item.textContent = String(point);
        list.appendChild(item);
      });
      elements.research.appendChild(list);
    }
  }

  function renderScript(value) {
    clearElement(elements.script);
    if (!value) return;
    if (typeof value === "string") return appendParagraph(elements.script, value);
    appendDefinition(elements.script, "Title", value.title);
    appendDefinition(elements.script, "Hook", value.hook);
    appendParagraph(elements.script, value.voiceover || value.script || value.body || "");
    appendDefinition(elements.script, "Ending", value.ending);
  }

  function renderStoryboard(value) {
    clearElement(elements.storyboard);
    if (!value) return;
    const scenes = Array.isArray(value) ? value : value.scenes || [];
    if (!scenes.length) {
      appendParagraph(elements.storyboard, value.story_arc_summary || "Storyboard stored with the project.");
      return;
    }
    scenes.forEach((scene, index) => {
      const card = document.createElement("article");
      const heading = document.createElement("strong");
      heading.textContent = `Scene ${scene.number || index + 1}`;
      card.appendChild(heading);
      appendParagraph(card, scene.visual_direction || scene.description || scene.narration || "");
      if (scene.start_second !== undefined && scene.end_second !== undefined) {
        appendParagraph(card, `${scene.start_second}s–${scene.end_second}s`, "fine");
      }
      elements.storyboard.appendChild(card);
    });
  }

  function collectMedia(job, project) {
    const output = contentRoot(job);
    const candidates = [
      output.image_urls,
      output.images,
      output.generated_media,
      project.image_urls,
      project.images,
      project.generated_media
    ];
    return candidates.find(Array.isArray) || [];
  }

  function mediaUrl(item) {
    if (typeof item === "string") return item;
    return item?.url || item?.image_url || item?.src || null;
  }

  function renderMedia(job, project) {
    clearElement(elements.media);
    collectMedia(job, project).forEach((item, index) => {
      const url = safeOutputUrl(mediaUrl(item));
      if (!url) return;
      const figure = document.createElement("figure");
      const image = document.createElement("img");
      image.src = url;
      image.loading = "lazy";
      image.alt = `Generated production image ${index + 1}`;
      figure.appendChild(image);
      elements.media.appendChild(figure);
    });
    if (!elements.media.children.length) appendParagraph(elements.media, "No media previews are available yet.", "fine");
  }

  function firstSafeUrl(...values) {
    for (const value of values) {
      const safe = safeOutputUrl(typeof value === "object" ? value?.url : value);
      if (safe) return safe;
    }
    return null;
  }

  function renderVideoAndThumbnail(job, project) {
    const output = contentRoot(job);
    const links = job.output_links || output.output_links || output.artifacts || {};
    const videoUrl = firstSafeUrl(
      job.video_url,
      output.video_url,
      project.video_url,
      links.video,
      links.final_video,
      links.mp4
    );
    if (videoUrl) {
      elements.video.src = videoUrl;
      elements.video.hidden = false;
      elements.videoEmpty.hidden = true;
      elements.video.load();
    } else {
      elements.video.removeAttribute("src");
      elements.video.hidden = true;
      elements.videoEmpty.hidden = false;
    }

    const thumbnailUrl = firstSafeUrl(
      job.thumbnail_url,
      output.thumbnail_url,
      project.thumbnail_url,
      links.thumbnail
    );
    if (thumbnailUrl) {
      elements.thumbnail.src = thumbnailUrl;
      elements.thumbnail.hidden = false;
      elements.thumbnailEmpty.hidden = true;
    } else {
      elements.thumbnail.removeAttribute("src");
      elements.thumbnail.hidden = true;
      elements.thumbnailEmpty.hidden = false;
    }
  }

  function renderPublishing(job, project) {
    const output = contentRoot(job);
    const packageData =
      output.publish_package ||
      output.release_package ||
      project.publish_package ||
      project.release_package ||
      project.project?.seo ||
      output.seo ||
      {};
    elements.publishTitle.textContent = packageData.title || "—";
    elements.publishDescription.textContent = packageData.description || "—";
    const hashtags = Array.isArray(packageData.hashtags)
      ? packageData.hashtags.join(" ")
      : packageData.hashtags;
    elements.publishHashtags.textContent = hashtags || "—";
  }

  function outputLinkEntries(job, project) {
    const output = contentRoot(job);
    const raw = job.output_links || output.output_links || output.artifacts || project.output_links || {};
    if (Array.isArray(raw)) {
      return raw.map((item, index) => [item.label || item.name || `Output ${index + 1}`, item.url || item]);
    }
    return Object.entries(raw);
  }

  function renderOutputLinks(job, project) {
    clearElement(elements.links);
    const seen = new Set();
    outputLinkEntries(job, project).forEach(([label, raw]) => {
      const url = safeOutputUrl(typeof raw === "object" ? raw?.url : raw);
      if (!url || seen.has(url)) return;
      seen.add(url);
      const link = document.createElement("a");
      link.className = "small-button";
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = titleCase(label);
      elements.links.appendChild(link);
    });
    if (!elements.links.children.length) appendParagraph(elements.links, "No downloadable outputs are available yet.", "fine");
  }

  function renderOutputs(job) {
    const output = contentRoot(job);
    const project = projectRoot(job) || {};
    const storedProject = project.project || project;
    const research = output.research || storedProject.research || project.research;
    const script = output.script || storedProject.script || project.script;
    const storyboard = output.storyboard || storedProject.storyboard || project.storyboard;
    renderResearch(research);
    renderScript(script);
    renderStoryboard(storyboard);
    renderMedia(job, project);
    renderVideoAndThumbnail(job, project);
    renderPublishing(job, project);
    renderOutputLinks(job, project);

    const hasResult = Boolean(
      research || script || storyboard ||
      !elements.video.hidden || !elements.thumbnail.hidden ||
      elements.links.querySelector("a")
    );
    elements.results.hidden = !hasResult;
  }

  async function hydrateProjectDetail(job) {
    const projectId = job.project_id;
    if (!projectId || job.project_detail) return job;
    try {
      const detail = await requestJSON(
        `/api/dashboard/projects/${encodeURIComponent(projectId)}`,
        {},
        10000
      );
      return {...job, project_detail: detail};
    } catch {
      return job;
    }
  }

  function updateButtons(status) {
    const terminal = TERMINAL_STATUSES.has(status);
    const running = !terminal && status !== "brief";
    elements.start.hidden = status !== "brief";
    elements.cancel.hidden = !running;
    elements.retry.hidden = status !== "failed";
    elements.newVersion.hidden = !(status === "complete" || status === "completed");
  }

  async function renderJob(rawJob) {
    let job = normalizeJobResponse(rawJob);
    const status = normalizedStatus(job.status);
    if (status === "complete" || status === "completed") job = await hydrateProjectDetail(job);
    currentJob = job;
    currentJobId = job.job_id || currentJobId;
    if (currentJobId) safeStorageSet(ACTIVE_JOB_KEY, currentJobId);

    elements.workspace.hidden = false;
    elements.progressPanel.hidden = false;
    const percent = clampPercent(job.progress_percent ?? job.progress);
    elements.progress.value = percent;
    elements.progress.textContent = `${percent}%`;
    elements.progressValue.textContent = `${percent}%`;
    elements.currentStage.textContent = job.current_stage
      ? `Current stage: ${titleCase(job.current_stage)}`
      : titleCase(status);
    elements.badge.textContent = titleCase(status).toUpperCase();
    elements.badge.dataset.status = status;
    elements.status.textContent = job.project_id
      ? `Project ${job.project_id} · ${titleCase(status)}`
      : `Production ${titleCase(status)}`;

    renderTimeline(job);
    renderWarnings(job);
    renderOutputs(job);
    updateButtons(status);

    const message = typeof job.error === "string" ? job.error : job.error?.message;
    elements.errorPanel.hidden = status !== "failed";
    elements.error.textContent = status === "failed"
      ? message || "Production failed. Review the completed stages and retry when ready."
      : "";

    if (TERMINAL_STATUSES.has(status)) {
      stopPolling();
      safeStorageSet(ACTIVE_JOB_KEY, null);
      if (status === "complete" || status === "completed") {
        elements.status.textContent = job.project_id
          ? `Project ${job.project_id} is ready.`
          : "Production is complete.";
        document.dispatchEvent(
          new CustomEvent("mindfrontier:production-complete", {detail: {job}})
        );
      }
    }
  }

  function stopPolling() {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = null;
    if (pollController) pollController.abort();
    pollController = null;
  }

  function schedulePoll(delay = POLL_DELAY_MS) {
    if (!currentJobId || TERMINAL_STATUSES.has(normalizedStatus(currentJob?.status))) return;
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = setTimeout(pollJob, document.hidden ? Math.max(delay, 5000) : delay);
  }

  async function pollJob() {
    if (!currentJobId) return;
    pollController = new AbortController();
    try {
      const response = await fetch(
        `/api/production/jobs/${encodeURIComponent(currentJobId)}`,
        {signal: pollController.signal}
      );
      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {};
      }
      if (response.status === 404) {
        stopPolling();
        safeStorageSet(ACTIVE_JOB_KEY, null);
        elements.status.textContent = "The saved production job is no longer available.";
        return;
      }
      if (!response.ok) throw new Error("Job status is temporarily unavailable.");
      await renderJob(data);
      schedulePoll();
    } catch (error) {
      if (error.name === "AbortError") return;
      elements.status.textContent = "Reconnecting to the production job…";
      schedulePoll(5000);
    } finally {
      pollController = null;
    }
  }

  async function startProduction(specification = currentSpecification) {
    if (!specification || typeof specification !== "object") return;
    stopPolling();
    elements.start.disabled = true;
    elements.status.textContent = "Queueing production…";
    elements.badge.textContent = "QUEUEING";
    elements.errorPanel.hidden = true;
    try {
      const data = await requestJSON("/api/production/jobs", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({production_specification: specification})
      });
      const job = normalizeJobResponse(data);
      currentJobId = job.job_id;
      if (!currentJobId) throw new Error("The Studio did not return a production job ID.");
      safeStorageSet(ACTIVE_JOB_KEY, currentJobId);
      await renderJob(job);
      schedulePoll(500);
    } catch (error) {
      elements.status.textContent = error.message || "Production could not be started.";
      elements.badge.textContent = "NOT STARTED";
      elements.badge.dataset.status = "failed";
      elements.errorPanel.hidden = false;
      elements.error.textContent = error.message || "Production could not be started.";
      elements.start.disabled = false;
      elements.start.hidden = false;
    }
  }

  async function cancelJob() {
    if (!currentJobId) return;
    elements.cancel.disabled = true;
    elements.status.textContent = "Requesting cancellation…";
    try {
      const data = await requestJSON(
        `/api/production/jobs/${encodeURIComponent(currentJobId)}/cancel`,
        {method: "POST"}
      );
      await renderJob(data);
    } catch (error) {
      elements.status.textContent = error.message || "Cancellation could not be requested.";
    } finally {
      elements.cancel.disabled = false;
    }
  }

  async function retryJob() {
    if (!currentJobId) return;
    elements.retry.disabled = true;
    elements.status.textContent = "Retrying from the last safe stage…";
    try {
      const data = await requestJSON(
        `/api/production/jobs/${encodeURIComponent(currentJobId)}/retry`,
        {method: "POST"}
      );
      const job = normalizeJobResponse(data);
      currentJobId = job.job_id || currentJobId;
      safeStorageSet(ACTIVE_JOB_KEY, currentJobId);
      await renderJob({...job, job_id: currentJobId});
      schedulePoll(500);
    } catch (error) {
      elements.status.textContent = error.message || "The job could not be retried.";
    } finally {
      elements.retry.disabled = false;
    }
  }

  function resetForNewIdea() {
    stopPolling();
    currentBrief = null;
    currentSpecification = null;
    currentJob = null;
    currentJobId = null;
    safeStorageSet(ACTIVE_JOB_KEY, null);
    elements.workspace.hidden = true;
    document.dispatchEvent(new CustomEvent("mindfrontier:new-creative-project"));
    window.MindFrontierShell?.activateView("create");
  }

  async function restoreJob() {
    const saved = safeStorageGet(ACTIVE_JOB_KEY);
    if (!saved || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(saved)) {
      if (saved) safeStorageSet(ACTIVE_JOB_KEY, null);
      return;
    }
    currentJobId = saved;
    elements.workspace.hidden = false;
    elements.progressPanel.hidden = false;
    elements.status.textContent = "Restoring the active production job…";
    await pollJob();
  }

  elements.start.addEventListener("click", () => startProduction());
  elements.cancel.addEventListener("click", cancelJob);
  elements.retry.addEventListener("click", retryJob);
  elements.newVersion.addEventListener("click", () => startProduction(currentSpecification));
  elements.newIdea.addEventListener("click", resetForNewIdea);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && currentJobId && !TERMINAL_STATUSES.has(normalizedStatus(currentJob?.status))) {
      schedulePoll(100);
    }
  });
  window.addEventListener("beforeunload", stopPolling);

  window.CreatorWorkspace = {
    presentBrief,
    startProduction,
    restoreJob,
    safeOutputUrl
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", restoreJob, {once: true});
  } else {
    restoreJob();
  }
})();
