from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn
import os
import shutil
import zipfile
import uuid
import threading
from converter_service import convert_audiobook

app = FastAPI()

jobs: dict = {}
jobs_lock = threading.Lock()

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PostRipM4B — Audiobook Converter</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js" crossorigin="anonymous"></script>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --border: #2a2d3e;
    --accent: #6c63ff;
    --accent-hover: #8a83ff;
    --text: #e8e8f0;
    --muted: #7b7d8e;
    --success: #4ade80;
    --error: #f87171;
    --radius: 12px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 2.5rem 1rem;
  }
  .container {
    width: 100%;
    max-width: 580px;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }
  header { text-align: center; }
  header h1 {
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6c63ff 0%, #a78bfa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.02em;
  }
  header p {
    color: var(--muted);
    margin-top: 0.4rem;
    font-size: 0.95rem;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    margin-bottom: 1.2rem;
  }
  label {
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.07em;
  }
  input[type="text"] {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-size: 0.95rem;
    padding: 0.65rem 0.9rem;
    width: 100%;
    transition: border-color 0.2s;
    outline: none;
    font-family: inherit;
  }
  input[type="text"]:focus { border-color: var(--accent); }
  input[type="text"]::placeholder { color: var(--muted); }
  .drop-zone {
    border: 2px dashed var(--border);
    border-radius: 10px;
    padding: 2.5rem 1.5rem;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
    position: relative;
    user-select: none;
  }
  .drop-zone.drag-over {
    border-color: var(--accent);
    background: rgba(108,99,255,0.08);
  }
  .drop-zone input[type="file"] {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
    width: 100%;
    height: 100%;
  }
  .drop-zone .icon { font-size: 2.8rem; margin-bottom: 0.6rem; display: block; }
  .drop-zone .hint { color: var(--muted); font-size: 0.9rem; line-height: 1.5; }
  .drop-zone .hint strong { color: var(--text); }
  .drop-zone .filename {
    color: var(--accent);
    font-weight: 600;
    margin-top: 0.5rem;
    font-size: 0.9rem;
    word-break: break-all;
  }
  .submit-btn {
    width: 100%;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 0.85rem;
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
    margin-top: 0.5rem;
    font-family: inherit;
    letter-spacing: 0.01em;
  }
  .submit-btn:hover { background: var(--accent-hover); }
  .submit-btn:active { transform: scale(0.98); }
  .submit-btn:disabled { opacity: 0.45; cursor: not-allowed; transform: none; }
  #status-area { display: none; }
  .status-header {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 0.75rem;
  }
  .progress-wrap {
    height: 6px;
    background: var(--border);
    border-radius: 99px;
    overflow: hidden;
    margin-bottom: 0.8rem;
  }
  .progress-bar {
    height: 100%;
    width: 0%;
    background: linear-gradient(90deg, var(--accent), #a78bfa);
    border-radius: 99px;
    transition: width 0.4s ease;
  }
  .progress-bar.indeterminate {
    width: 35%;
    animation: slide 1.3s infinite ease-in-out;
  }
  @keyframes slide {
    0%   { transform: translateX(-200%); }
    100% { transform: translateX(400%); }
  }
  #status-msg {
    color: var(--muted);
    font-size: 0.9rem;
    text-align: center;
    min-height: 1.25rem;
  }
  .download-btn {
    display: none;
    width: 100%;
    background: var(--success);
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 0.85rem;
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
    margin-top: 1rem;
    transition: opacity 0.2s;
    font-family: inherit;
  }
  .download-btn:hover { opacity: 0.88; }
  #error-msg {
    display: none;
    color: var(--error);
    font-size: 0.9rem;
    text-align: center;
    margin-top: 0.75rem;
    padding: 0.75rem;
    background: rgba(248,113,113,0.1);
    border-radius: 8px;
    border: 1px solid rgba(248,113,113,0.25);
  }
  .convert-again {
    display: none;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--muted);
    font-size: 0.85rem;
    font-weight: 600;
    padding: 0.6rem 1rem;
    width: 100%;
    cursor: pointer;
    margin-top: 0.75rem;
    font-family: inherit;
    transition: border-color 0.2s, color 0.2s;
  }
  .convert-again:hover { border-color: var(--accent); color: var(--text); }
  .autofill-badge {
    display: none;
    font-size: 0.72rem;
    color: var(--accent);
    font-weight: 600;
    margin-top: 0.2rem;
  }
  footer {
    color: var(--muted);
    font-size: 0.78rem;
    text-align: center;
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>PostRipM4B</h1>
    <p>Convert MP3 audiobooks to M4B with chapters &amp; cover art</p>
  </header>

  <div class="card">
    <form id="upload-form">
      <div class="field">
        <label for="title">Title</label>
        <input type="text" id="title" name="title" placeholder="Auto-detected if left blank">
        <span class="autofill-badge" id="title-badge">✦ Filled from metadata.json</span>
      </div>
      <div class="field">
        <label for="author">Author</label>
        <input type="text" id="author" name="author" placeholder="Auto-detected if left blank">
        <span class="autofill-badge" id="author-badge">✦ Filled from metadata.json</span>
      </div>
      <div class="field">
        <label>Audio File or ZIP Archive</label>
        <div class="drop-zone" id="drop-zone">
          <input type="file" id="file" name="file" accept=".zip,.mp3" required>
          <span class="icon">📦</span>
          <p class="hint">Drag &amp; drop here or click to browse<br>
            Accepts <strong>.zip</strong> (multiple MP3s) or single <strong>.mp3</strong>
          </p>
          <div class="filename" id="chosen-file"></div>
        </div>
      </div>
      <button type="submit" class="submit-btn" id="submit-btn">Convert to M4B</button>
    </form>

    <div id="status-area">
      <p class="status-header">Conversion Status</p>
      <div class="progress-wrap">
        <div class="progress-bar indeterminate" id="progress-bar"></div>
      </div>
      <p id="status-msg">Starting…</p>
      <a class="download-btn" id="download-link" href="#">⬇ Download M4B</a>
      <p id="error-msg"></p>
      <button class="convert-again" id="convert-again-btn">Convert another file</button>
    </div>
  </div>

  <footer>PostRipM4B v1.2.1</footer>
</div>

<script>
const form          = document.getElementById('upload-form');
const fileInput     = document.getElementById('file');
const chosenFile    = document.getElementById('chosen-file');
const dropZone      = document.getElementById('drop-zone');
const submitBtn     = document.getElementById('submit-btn');
const statusArea    = document.getElementById('status-area');
const progressBar   = document.getElementById('progress-bar');
const statusMsg     = document.getElementById('status-msg');
const downloadLink  = document.getElementById('download-link');
const errorMsg      = document.getElementById('error-msg');
const againBtn      = document.getElementById('convert-again-btn');

const titleInput  = document.getElementById('title');
const authorInput = document.getElementById('author');
const titleBadge  = document.getElementById('title-badge');
const authorBadge = document.getElementById('author-badge');

fileInput.addEventListener('change', () => handleFileSelected(fileInput.files[0]));

async function handleFileSelected(file) {
  if (!file) return;
  chosenFile.textContent = file.name;
  titleBadge.style.display = 'none';
  authorBadge.style.display = 'none';

  if (!file.name.endsWith('.zip')) return;
  try {
    const zip = await JSZip.loadAsync(file);
    const metaPath = Object.keys(zip.files).find(p => p.endsWith('metadata.json'));
    if (!metaPath) return;
    const raw  = await zip.files[metaPath].async('text');
    const meta = JSON.parse(raw);

    if (meta.title) {
      titleInput.value = meta.title;
      titleBadge.style.display = 'block';
    }
    const authorCreator = (meta.creator || []).find(c => c.role === 'author');
    if (authorCreator?.name) {
      authorInput.value = authorCreator.name;
      authorBadge.style.display = 'block';
    }
  } catch { /* not a valid zip or no metadata — silently ignore */ }
}

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
['dragleave', 'drop'].forEach(ev =>
  dropZone.addEventListener(ev, () => dropZone.classList.remove('drag-over'))
);
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  if (e.dataTransfer.files.length) {
    fileInput.files = e.dataTransfer.files;
    handleFileSelected(fileInput.files[0]);
  }
});

form.addEventListener('submit', async e => {
  e.preventDefault();
  submitBtn.disabled = true;
  form.style.display = 'none';
  statusArea.style.display = 'block';
  errorMsg.style.display = 'none';
  downloadLink.style.display = 'none';
  againBtn.style.display = 'none';
  progressBar.className = 'progress-bar indeterminate';
  statusMsg.textContent = 'Uploading file…';

  let jobId;
  try {
    const res = await fetch('/convert', { method: 'POST', body: new FormData(form) });
    if (!res.ok) throw new Error('Upload failed (' + res.status + ')');
    const json = await res.json();
    jobId = json.job_id;
  } catch (err) {
    showError(err.message || 'Upload failed. Please try again.');
    return;
  }

  statusMsg.textContent = 'Converting — this may take a few minutes…';
  poll(jobId);
});

function poll(jobId) {
  const iv = setInterval(async () => {
    try {
      const res  = await fetch('/status/' + jobId);
      const json = await res.json();
      if (json.status === 'done') {
        clearInterval(iv);
        progressBar.classList.remove('indeterminate');
        progressBar.style.width = '100%';
        statusMsg.textContent = 'All done!';
        downloadLink.href = '/download/' + jobId;
        downloadLink.style.display = 'block';
        againBtn.style.display = 'block';
      } else if (json.status === 'error') {
        clearInterval(iv);
        showError(json.message || 'Conversion failed.');
      }
    } catch { /* transient network error — keep polling */ }
  }, 2500);
}

function showError(msg) {
  progressBar.classList.remove('indeterminate');
  progressBar.style.width = '0';
  statusMsg.textContent = '';
  errorMsg.textContent = '⚠ ' + msg;
  errorMsg.style.display = 'block';
  againBtn.style.display = 'block';
}

againBtn.addEventListener('click', () => {
  form.reset();
  chosenFile.textContent = '';
  titleBadge.style.display = 'none';
  authorBadge.style.display = 'none';
  submitBtn.disabled = false;
  form.style.display = 'block';
  statusArea.style.display = 'none';
});
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML


@app.post("/convert")
async def start_conversion(
    background_tasks: BackgroundTasks,
    title: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    job_id = str(uuid.uuid4())
    upload_dir = os.path.join("uploads", os.path.splitext(file.filename)[0])
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if file.filename.endswith(".zip"):
        with zipfile.ZipFile(file_path, "r") as zip_ref:
            zip_ref.extractall(upload_dir)
        os.remove(file_path)

    with jobs_lock:
        jobs[job_id] = {"status": "processing", "output_dir": None, "message": ""}

    background_tasks.add_task(run_conversion, job_id, upload_dir, title, author)
    return {"job_id": job_id, "status": "processing"}


def run_conversion(job_id: str, upload_dir: str, title: Optional[str], author: Optional[str]):
    try:
        result = convert_audiobook(upload_dir, title, author)
        with jobs_lock:
            jobs[job_id] = {"status": "done", "output_dir": result["output"], "message": ""}
    except Exception as e:
        with jobs_lock:
            jobs[job_id] = {"status": "error", "output_dir": None, "message": str(e)}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    return job


@app.get("/download/{job_id}")
async def download_result(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return {"error": "Not ready"}
    output_dir = job["output_dir"]
    for fname in os.listdir(output_dir):
        if fname.endswith(".m4b"):
            return FileResponse(
                os.path.join(output_dir, fname),
                media_type="audio/mp4",
                filename=fname,
            )
    return {"error": "Output file not found"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
