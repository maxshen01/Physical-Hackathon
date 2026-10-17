const form = document.querySelector("#analyse-form");
const fileInput = document.querySelector("#video");
const submitButton = document.querySelector("#submit-button");
const progress = document.querySelector("#progress");
const error = document.querySelector("#error");
const results = document.querySelector("#results");
const audio = document.querySelector("#audio");
let audioUrl = null;

function setText(selector, value) {
  document.querySelector(selector).textContent = value;
}

function renderList(selector, items) {
  const list = document.querySelector(selector);
  list.replaceChildren();
  for (const item of items) {
    const row = document.createElement("li");
    row.textContent = item;
    list.append(row);
  }
}

function clearAudio() {
  audio.pause();
  audio.removeAttribute("src");
  audio.hidden = true;
  audio.load();
  if (audioUrl) URL.revokeObjectURL(audioUrl);
  audioUrl = null;
}

function playAudio(encoded, mimeType) {
  const raw = atob(encoded);
  const bytes = new Uint8Array(raw.length);
  for (let index = 0; index < raw.length; index += 1) {
    bytes[index] = raw.charCodeAt(index);
  }
  audioUrl = URL.createObjectURL(new Blob([bytes], { type: mimeType }));
  audio.src = audioUrl;
  audio.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.hidden = true;
  results.hidden = true;
  clearAudio();

  const file = fileInput.files[0];
  if (!file || file.size > 50 * 1024 * 1024) {
    error.textContent = "Choose a video smaller than 50 MB.";
    error.hidden = false;
    return;
  }

  submitButton.disabled = true;
  progress.textContent = "Uploading and analysing your clip. This may take a moment…";
  progress.hidden = false;
  try {
    const response = await fetch("/api/analyse", {
      method: "POST",
      body: new FormData(form),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(typeof data.detail === "string" ? data.detail : "The clip could not be analysed.");
    }

    const feedback = data.feedback;
    setText(
      "#result-status",
      feedback.status === "unable_to_assess"
        ? "We couldn’t assess this clip clearly."
        : "Here is what was visible in your clip."
    );
    renderList("#observations", feedback.observations);
    renderList("#cues", feedback.cues);
    document.querySelector("#cues").previousElementSibling.hidden = feedback.cues.length === 0;
    setText("#spoken-text", feedback.spoken_text);
    if (data.audio_base64) playAudio(data.audio_base64, data.audio_mime_type || "audio/mpeg");
    const audioError = document.querySelector("#audio-error");
    audioError.textContent = data.audio_error || "";
    audioError.hidden = !data.audio_error;
    results.hidden = false;
  } catch (caught) {
    error.textContent = caught instanceof Error ? caught.message : "Something went wrong.";
    error.hidden = false;
  } finally {
    submitButton.disabled = false;
    progress.hidden = true;
  }
});

window.addEventListener("beforeunload", clearAudio);

