const scanner = document.querySelector("#scanner");
const preview = document.querySelector("#preview");
const statusText = document.querySelector("#statusText");
const readability = document.querySelector("#readability");
const filmstrip = document.querySelector("#filmstrip");
const buttons = [...document.querySelectorAll("button")];
const addButton = document.querySelector("#addButton");
const uploadButton = document.querySelector("#uploadButton");
const newButton = document.querySelector("#newButton");

let busy = false;

function setBusy(nextBusy) {
  busy = nextBusy;
  buttons.forEach((button) => {
    button.disabled = busy;
  });
}

async function refreshQuality() {
  try {
    const response = await fetch("/quality", { cache: "no-store" });
    const report = await response.json();
    scanner.classList.toggle("readable-yes", report.readable === true);
    scanner.classList.toggle("readable-no", report.readable === false);
    scanner.classList.toggle("readable-unknown", report.readable === undefined);
    readability.textContent = `${report.message} · ${report.score}%`;
    statusText.textContent = report.readable
      ? "The page looks sharp enough to upload."
      : "Adjust focus, distance, or lighting before uploading.";
  } catch (error) {
    scanner.classList.remove("readable-yes");
    scanner.classList.add("readable-no");
    readability.textContent = "Offline";
    statusText.textContent = "The scanner service is not responding.";
  }
}

async function refreshCaptures() {
  const response = await fetch("/status", { cache: "no-store" });
  const payload = await response.json();
  const captures = [...payload.pages];
  if (payload.pending) {
    captures.push(payload.pending);
  }
  filmstrip.replaceChildren(
    ...captures.map((capture, index) => {
      const item = document.createElement("div");
      item.className = "thumb";
      const image = document.createElement("img");
      image.src = `${capture.image}?t=${Date.now()}`;
      image.alt = `Captured page ${index + 1}`;
      const label = document.createElement("span");
      label.textContent = `Page ${index + 1}`;
      item.append(image, label);
      return item;
    }),
  );
}

async function addCapture() {
  setBusy(true);
  try {
    await fetch("/capture", { method: "POST" });
    await fetch("/keep", { method: "POST" });
    await refreshCaptures();
    statusText.textContent = "Page added.";
  } finally {
    setBusy(false);
  }
}

async function upload() {
  setBusy(true);
  try {
    statusText.textContent = "Creating PDF and uploading...";
    const response = await fetch("/finalize", { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Upload failed");
    }
    await refreshCaptures();
    statusText.textContent = payload.message;
  } catch (error) {
    statusText.textContent = error.message;
    scanner.classList.remove("readable-yes");
    scanner.classList.add("readable-no");
  } finally {
    setBusy(false);
  }
}

async function clearCaptures() {
  setBusy(true);
  try {
    await fetch("/new", { method: "POST" });
    await refreshCaptures();
    statusText.textContent = "Ready for a new document.";
  } finally {
    setBusy(false);
  }
}

addButton.addEventListener("click", addCapture);
uploadButton.addEventListener("click", upload);
newButton.addEventListener("click", clearCaptures);

refreshQuality();
refreshCaptures();
setInterval(() => {
  if (!busy) {
    refreshQuality();
  }
}, 1200);
