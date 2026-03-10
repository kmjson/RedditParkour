let pollTimer = null;

// ── Step 1: fetch the Reddit post and show the edit card ──────────────────────
async function fetchPost() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) {
    showError('Please paste a Reddit post URL.');
    return;
  }
  if (!url.includes('reddit.com')) {
    showError("That doesn't look like a Reddit URL.");
    return;
  }

  hideError();
  setGenBtn(true);

  try {
    const res  = await fetch('/api/fetch', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ url }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to fetch post');

    document.getElementById('edit-title').value = data.title || '';
    document.getElementById('edit-story').value = data.story || '';
    showCard('edit');
  } catch (err) {
    showError(err.message);
  } finally {
    setGenBtn(false);
  }
}

// ── Step 2: generate video from the (possibly edited) text ────────────────────
async function startGeneration() {
  const title = document.getElementById('edit-title').value.trim();
  const story = document.getElementById('edit-story').value.trim();
  if (!title && !story) {
    showError('Title and story cannot both be empty.');
    return;
  }

  hideError();
  document.getElementById('make-btn').disabled = true;
  showCard('progress');
  setStep('fetch', 'done');
  setStep('tts',   'active');
  setStep('vid',   'idle');

  try {
    const res  = await fetch('/api/generate', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ title, story }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to start job');
    pollStatus(data.job_id);
  } catch (err) {
    showError(err.message);
    document.getElementById('make-btn').disabled = false;
    showCard('edit');
  }
}

// ── Back to URL input ─────────────────────────────────────────────────────────
function backToInput() {
  hideError();
  showCard('input');
}

// ── Poll job status every 1.5 s ───────────────────────────────────────────────
function pollStatus(jobId) {
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${jobId}`);
      const job = await res.json();
      applyJobState(job);
      if (job.status === 'done' || job.status === 'error') {
        clearInterval(pollTimer);
        if (job.status === 'done') {
          finishWithVideo(job.video_url);
        } else {
          showError(job.error || 'Something went wrong.');
          document.getElementById('make-btn').disabled = false;
          showCard('edit');
        }
      }
    } catch {
      /* network hiccup — keep polling */
    }
  }, 1500);
}

// ── Map server job status to UI step states ───────────────────────────────────
function applyJobState(job) {
  if (job.status === 'generating_tts') {
    setStep('fetch', 'done');
    setStep('tts',   'active');
  } else if (job.status === 'creating_video') {
    setStep('fetch', 'done');
    setStep('tts',   'done');
    setStep('vid',   'active');
  }
}

// ── Show the finished video ───────────────────────────────────────────────────
function finishWithVideo(videoUrl) {
  setStep('fetch', 'done');
  setStep('tts',   'done');
  setStep('vid',   'done');
  setTimeout(() => {
    const vid   = document.getElementById('result-video');
    const dlBtn = document.getElementById('dl-btn');
    vid.src       = videoUrl;
    dlBtn.href    = videoUrl;
    dlBtn.download = `reddit-parkour-${Date.now()}.mp4`;
    showCard('video');
  }, 700);
}

// ── Reset everything back to the start ───────────────────────────────────────
function startOver() {
  if (pollTimer) clearInterval(pollTimer);
  document.getElementById('url-input').value   = '';
  document.getElementById('edit-title').value  = '';
  document.getElementById('edit-story').value  = '';
  document.getElementById('result-video').src  = '';
  document.getElementById('make-btn').disabled = false;
  hideError();
  setGenBtn(false);
  showCard('input');
  ['fetch', 'tts', 'vid'].forEach(s => setStep(s, 'idle'));
}

// ── Step indicator helpers ────────────────────────────────────────────────────
const STEP_NUMS = { fetch: '1', tts: '2', vid: '3' };

function setStep(id, state) {
  const el   = document.getElementById(`s-${id}`);
  const icon = document.getElementById(`si-${id}`);
  el.className = `step${state === 'active' ? ' active' : state === 'done' ? ' done' : ''}`;
  if (state === 'active') {
    icon.innerHTML = '<div class="spinner"></div>';
  } else if (state === 'done') {
    icon.innerHTML = '✓';
  } else {
    icon.textContent = STEP_NUMS[id];
  }
}

// ── Card visibility ───────────────────────────────────────────────────────────
function showCard(name) {
  ['input', 'edit', 'progress', 'video'].forEach(n => {
    document.getElementById(`${n}-card`).classList.toggle('hidden', n !== name);
  });
}

function setGenBtn(disabled) {
  document.getElementById('gen-btn').disabled = disabled;
}

// ── Error banner ──────────────────────────────────────────────────────────────
function showError(msg) {
  const box = document.getElementById('error-box');
  box.textContent = '⚠ ' + msg;
  box.classList.remove('hidden');
}

function hideError() {
  document.getElementById('error-box').classList.add('hidden');
}

// ── Enter key on URL field ────────────────────────────────────────────────────
document.getElementById('url-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') fetchPost();
});
