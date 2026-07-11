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
