let currentAudioPath = "";
let currentDuration = 0;
let detectedResult = null;
let currentStart = 0;
let currentEnd = 0;
let timelineData = [];

function formatTime(seconds) {
  seconds = Math.max(0, Math.floor(seconds));
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hrs > 0) {
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function parseTime(str) {
  const parts = str.trim().split(':').map(Number);
  if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  } else if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  } else if (parts.length === 1 && !isNaN(parts[0])) {
    return parts[0];
  }
  return 0;
}

function formatDuration(sec) {
  const s = Math.round(sec);
  const m = Math.floor(s / 60);
  const remS = s % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    const remM = m % 60;
    return `${h}h ${remM}m ${remS}s`;
  }
  return `${m}m ${remS}s`;
}

function triggerFileUpload() {
  document.getElementById('hiddenFileInput').click();
}

document.getElementById('hiddenFileInput').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  const analyzeBtn = document.getElementById('analyzeBtn');
  analyzeBtn.disabled = true;
  document.getElementById('analyzeBtnText').innerText = 'Uploading local audio...';

  try {
    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    currentAudioPath = data.path;
    document.getElementById('audioPath').value = data.path;
    currentDuration = data.info.duration;

    // Set default output dir
    const defaultOut = data.path.replace(/\.[^/.]+$/, "") + "_splits";
    document.getElementById('outputDir').value = defaultOut;

    // Setup audio player
    setupAudioPlayer(data.path);
  } catch (err) {
    alert('Failed to load audio: ' + err.message);
  } finally {
    analyzeBtn.disabled = false;
    document.getElementById('analyzeBtnText').innerText = '⚡ Analyze & Detect Sermon';
  }
});

function setupAudioPlayer(filePath) {
  const audioEl = document.getElementById('audioPreview');
  audioEl.src = `/api/audio-stream?path=${encodeURIComponent(filePath)}`;
}

async function startAnalysis() {
  const audioPath = document.getElementById('audioPath').value.trim();
  if (!audioPath) {
    alert('Please enter or select an audio file path (.wav or .mp3).');
    return;
  }

  currentAudioPath = audioPath;
  const modelSize = document.getElementById('modelSize').value;
  const minSermonMin = parseFloat(document.getElementById('minSermonMin').value) || 10.0;
  const densityThreshold = parseFloat(document.getElementById('densityThreshold').value) || 0.55;
  const paddingSec = parseFloat(document.getElementById('paddingSec').value) || 2.0;

  const progressContainer = document.getElementById('progressContainer');
  const progressStatus = document.getElementById('progressStatus');
  const progressPercent = document.getElementById('progressPercent');
  const progressBarFill = document.getElementById('progressBarFill');
  const analyzeBtn = document.getElementById('analyzeBtn');

  progressContainer.classList.remove('hidden');
  analyzeBtn.disabled = true;
  document.getElementById('analyzeBtnText').innerText = 'Analyzing...';
  setupAudioPlayer(audioPath);

  try {
    const startRes = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        audio_path: audioPath,
        model_size: modelSize,
        min_sermon_minutes: minSermonMin,
        density_threshold: densityThreshold,
        padding_seconds: paddingSec
      })
    });

    if (!startRes.ok) {
      const err = await startRes.json();
      throw new Error(err.detail || 'Failed to start analysis');
    }

    const { job_id } = await startRes.json();

    // Poll status
    const pollInterval = setInterval(async () => {
      try {
        const pollRes = await fetch(`/api/analyze-status/${job_id}`);
        if (!pollRes.ok) return;
        const job = await pollRes.json();

        const pct = Math.round(job.progress * 100);
        progressPercent.innerText = `${pct}%`;
        progressBarFill.style.width = `${pct}%`;
        progressStatus.innerText = job.message || 'Processing...';

        if (job.status === 'completed') {
          clearInterval(pollInterval);
          analyzeBtn.disabled = false;
          document.getElementById('analyzeBtnText').innerText = '⚡ Re-Analyze';
          renderResults(job.result);
        } else if (job.status === 'failed') {
          clearInterval(pollInterval);
          analyzeBtn.disabled = false;
          document.getElementById('analyzeBtnText').innerText = '⚡ Analyze & Detect Sermon';
          alert('Analysis failed: ' + job.error);
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 1000);

  } catch (err) {
    alert('Error: ' + err.message);
    analyzeBtn.disabled = false;
    document.getElementById('analyzeBtnText').innerText = '⚡ Analyze & Detect Sermon';
  }
}

function renderResults(result) {
  detectedResult = result;
  currentDuration = result.total_duration;
  currentStart = result.sermon_start;
  currentEnd = result.sermon_end;
  timelineData = result.timeline_density || [];

  document.getElementById('resultsSection').classList.remove('hidden');
  document.getElementById('confidenceBadge').innerText = `Confidence: ${Math.round(result.confidence * 100)}%`;

  document.getElementById('sermonStartInput').value = formatTime(currentStart);
  document.getElementById('sermonEndInput').value = formatTime(currentEnd);

  document.getElementById('rulerMid').innerText = formatTime(currentDuration / 2);
  document.getElementById('rulerEnd').innerText = formatTime(currentDuration);

  updateCalculatedDurations();
  drawDensityTimeline();

  // If transcript available, display it
  if (result.sermon_transcript) {
    document.getElementById('transcriptText').innerText = result.sermon_transcript;
  }
}

function updateCalculatedDurations() {
  const w1 = Math.max(0, currentStart);
  const sermon = Math.max(0, currentEnd - currentStart);
  const w2 = Math.max(0, currentDuration - currentEnd);

  document.getElementById('durWorship1').innerText = formatDuration(w1);
  document.getElementById('durSermon').innerText = formatDuration(sermon);
  document.getElementById('durWorship2').innerText = formatDuration(w2);
}

function adjustTime(type, deltaSeconds) {
  if (type === 'start') {
    currentStart = Math.max(0, Math.min(currentEnd - 10, currentStart + deltaSeconds));
    document.getElementById('sermonStartInput').value = formatTime(currentStart);
  } else if (type === 'end') {
    currentEnd = Math.max(currentStart + 10, Math.min(currentDuration, currentEnd + deltaSeconds));
    document.getElementById('sermonEndInput').value = formatTime(currentEnd);
  }
  updateCalculatedDurations();
  drawDensityTimeline();
}

document.getElementById('sermonStartInput').addEventListener('change', (e) => {
  currentStart = parseTime(e.target.value);
  updateCalculatedDurations();
  drawDensityTimeline();
});

document.getElementById('sermonEndInput').addEventListener('change', (e) => {
  currentEnd = parseTime(e.target.value);
  updateCalculatedDurations();
  drawDensityTimeline();
});

function previewAt(type) {
  const audioEl = document.getElementById('audioPreview');
  let targetTime = 0;
  if (type === 'start') {
    targetTime = Math.max(0, currentStart - 8); // Play 8 seconds before sermon starts
  } else if (type === 'end') {
    targetTime = Math.max(0, currentEnd - 8); // Play 8 seconds before sermon ends
  }
  audioEl.currentTime = targetTime;
  audioEl.play();
}

function drawDensityTimeline() {
  const canvas = document.getElementById('densityCanvas');
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * window.devicePixelRatio;
  canvas.height = 130 * window.devicePixelRatio;
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

  const W = rect.width;
  const H = 130;

  ctx.clearRect(0, 0, W, H);

  if (currentDuration <= 0) return;

  const startX = (currentStart / currentDuration) * W;
  const endX = (currentEnd / currentDuration) * W;

  // Background zones
  // 1. Opening Worship
  ctx.fillStyle = 'rgba(56, 189, 248, 0.15)';
  ctx.fillRect(0, 0, startX, H);

  // 2. Sermon
  ctx.fillStyle = 'rgba(245, 158, 11, 0.22)';
  ctx.fillRect(startX, 0, endX - startX, H);

  // 3. Closing Worship
  ctx.fillStyle = 'rgba(45, 212, 191, 0.15)';
  ctx.fillRect(endX, 0, W - endX, H);

  // Draw speech density bars/curve
  if (timelineData.length > 0) {
    ctx.fillStyle = '#cbd5e1';
    ctx.strokeStyle = '#8b5cf6';
    ctx.lineWidth = 2;
    ctx.beginPath();

    for (let i = 0; i < timelineData.length; i++) {
      const pt = timelineData[i];
      const x = (pt.time / currentDuration) * W;
      const densityH = pt.density * (H - 25);
      const y = (H - 10) - densityH;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }

      // Density vertical bars
      const inSermon = pt.time >= currentStart && pt.time <= currentEnd;
      ctx.fillStyle = inSermon ? 'rgba(245, 158, 11, 0.7)' : 'rgba(56, 189, 248, 0.4)';
      ctx.fillRect(x - 1, (H - 10) - densityH, 2, densityH);
    }
    ctx.stroke();
  }

  // Draw boundary marker lines
  // Start marker
  ctx.strokeStyle = '#f59e0b';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(startX, 0);
  ctx.lineTo(startX, H);
  ctx.stroke();

  // End marker
  ctx.beginPath();
  ctx.moveTo(endX, 0);
  ctx.lineTo(endX, H);
  ctx.stroke();

  // Marker handle flags
  ctx.fillStyle = '#f59e0b';
  ctx.font = 'bold 11px Inter, sans-serif';
  ctx.fillText('Sermon Start', Math.max(5, startX - 35), 15);
  ctx.fillText('Sermon End', Math.min(W - 75, endX - 35), 15);
}

// Canvas click to seek or position
document.getElementById('densityCanvas').addEventListener('click', (e) => {
  const canvas = document.getElementById('densityCanvas');
  const rect = canvas.getBoundingClientRect();
  const clickX = e.clientX - rect.width;
  const clickFraction = (e.clientX - rect.left) / rect.width;
  const clickedTime = clickFraction * currentDuration;

  const audioEl = document.getElementById('audioPreview');
  audioEl.currentTime = clickedTime;
});

async function runLosslessExport() {
  const audioPath = document.getElementById('audioPath').value.trim();
  let outputDir = document.getElementById('outputDir').value.trim();
  if (!outputDir) {
    outputDir = audioPath.replace(/\.[^/.]+$/, "") + "_splits";
  }

  const exportBtn = document.getElementById('exportBtn');
  exportBtn.disabled = true;
  document.getElementById('exportBtnText').innerText = '✂️ Splitting losslessly (-c copy)...';

  const combineWorship = document.getElementById('combineWorshipCheck').checked;
  const exportTranscript = document.getElementById('exportTranscriptCheck').checked;

  try {
    const res = await fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        audio_path: audioPath,
        output_dir: outputDir,
        sermon_start: currentStart,
        sermon_end: currentEnd,
        combine_worship: combineWorship,
        export_transcript: exportTranscript,
        sermon_transcript: detectedResult ? detectedResult.sermon_transcript : ""
      })
    });

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    renderExportResults(data);
  } catch (err) {
    alert('Export error: ' + err.message);
  } finally {
    exportBtn.disabled = false;
    document.getElementById('exportBtnText').innerText = '✂️ Execute Lossless Split (-c copy)';
  }
}

function renderExportResults(summary) {
  const outputSection = document.getElementById('outputSection');
  const filesList = document.getElementById('filesList');
  outputSection.classList.remove('hidden');

  filesList.innerHTML = '';
  summary.files.forEach(f => {
    const item = document.createElement('div');
    item.className = 'file-item';
    item.innerHTML = `
      <div class="file-info">
        <span class="file-label">${f.label}</span>
        <span class="file-path">${f.path}</span>
      </div>
      <span class="badge badge-tech">${f.formatted_range || 'File'}</span>
    `;
    filesList.appendChild(item);
  });

  outputSection.scrollIntoView({ behavior: 'smooth' });
}

function toggleTranscript() {
  const body = document.getElementById('transcriptBody');
  const icon = document.getElementById('transcriptToggleIcon');
  body.classList.toggle('hidden');
  icon.innerText = body.classList.contains('hidden') ? '▼' : '▲';
}

window.addEventListener('resize', () => {
  if (detectedResult) {
    drawDensityTimeline();
  }
});
