let currentAudioPath = "";
let currentDuration = 0;
let detectedResult = null;
let currentStart = 0;
let currentEnd = 0;
let timelineData = [];
let uploadedCoverArtPath = null;
let watcherPollTimer = null;

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

function triggerCoverArtUpload() {
  document.getElementById('coverArtInput').click();
}

document.getElementById('coverArtInput').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  const preview = document.getElementById('coverArtPreview');
  preview.innerHTML = '<span class="cover-art-icon">⏳</span><span class="cover-art-label">Uploading art...</span>';

  try {
    const res = await fetch('/api/upload-cover-art', {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    uploadedCoverArtPath = data.path;
    preview.innerHTML = `<img class="cover-art-img" src="${data.url}?t=${Date.now()}" alt="Cover Art" />`;
  } catch (err) {
    alert('Failed to upload cover art: ' + err.message);
    preview.innerHTML = '<span class="cover-art-icon">🖼️</span><span class="cover-art-label">Click to Upload Church Flyer / Logo</span>';
  }
});

function onServiceTypeChange(val) {
  const albumInput = document.getElementById('metaAlbum');
  if (albumInput) {
    if (val === 'Sunday Morning Service') albumInput.value = 'Sunday Morning Service';
    else if (val === 'Sunday School (Adult Teaching)') albumInput.value = 'Adult Sunday School Teaching';
    else if (val === 'Wednesday Evening Service') albumInput.value = 'Wednesday Evening Service';
    else if (val === 'Friday Evening Service') albumInput.value = 'Friday Evening Service';
    else if (val === 'Revival / Special Service') albumInput.value = 'Revival Services';
    else albumInput.value = 'Church Service Audio';
  }
}

function syncMessageTitle(val) {
  const aiTitle = document.getElementById('aiSermonTitle');
  if (aiTitle && aiTitle.value !== val) {
    aiTitle.value = val;
  }
}

function syncMetaTitle(val) {
  const metaTitle = document.getElementById('metaMessageTitle');
  if (metaTitle && metaTitle.value !== val) {
    metaTitle.value = val;
  }
}

function onMessageTitleInput(val) {
  syncMessageTitle(val);
}

function getMetadataPayload() {
  const preacher = document.getElementById('metaPreacher') ? document.getElementById('metaPreacher').value.trim() : "";
  const album = document.getElementById('metaAlbum') ? document.getElementById('metaAlbum').value.trim() : "";
  const year = document.getElementById('metaYear') ? document.getElementById('metaYear').value.trim() : "";
  const genre = document.getElementById('metaGenre') ? document.getElementById('metaGenre').value.trim() : "";
  const msgTitleInput = document.getElementById('metaMessageTitle');
  const aiTitleInput = document.getElementById('aiSermonTitle');
  const title = (msgTitleInput && msgTitleInput.value.trim()) || (aiTitleInput && aiTitleInput.value.trim()) || "";
  const serviceType = document.getElementById('metaServiceType') ? document.getElementById('metaServiceType').value : "";
  const normalize = document.getElementById('normalizeLoudnessCheck') ? document.getElementById('normalizeLoudnessCheck').checked : false;
  const exportMp3 = document.getElementById('exportFormatSelect') ? document.getElementById('exportFormatSelect').value === 'mp3' : false;

  const metadata = {};
  if (preacher) metadata.artist = preacher;
  if (album) metadata.album = album;
  if (year) metadata.date = year;
  if (genre) metadata.genre = genre;
  if (title) metadata.title = title;
  if (serviceType) metadata.comment = serviceType;

  return {
    metadata: Object.keys(metadata).length > 0 ? metadata : null,
    cover_art_path: uploadedCoverArtPath,
    normalize_loudness: normalize,
    export_mp3: exportMp3,
    service_type: serviceType,
    title: title
  };
}

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
  renderTracks();

  // If transcript available, display it and extract AI scripture summary
  if (result.sermon_transcript) {
    document.getElementById('transcriptText').innerText = result.sermon_transcript;
    autoExtractSermonSummary(result.sermon_transcript);
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
  document.getElementById('exportBtnText').innerText = '✂️ Splitting & Tagging audio...';

  const combineWorship = document.getElementById('combineWorshipCheck').checked;
  const exportTranscript = document.getElementById('exportTranscriptCheck').checked;
  const metaPayload = getMetadataPayload();

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
        sermon_transcript: detectedResult ? detectedResult.sermon_transcript : "",
        metadata: metaPayload.metadata,
        cover_art_path: metaPayload.cover_art_path,
        normalize_loudness: metaPayload.normalize_loudness,
        export_mp3: metaPayload.export_mp3
      })
    });

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    renderExportResults(data);
  } catch (err) {
    alert('Export error: ' + err.message);
  } finally {
    exportBtn.disabled = false;
    document.getElementById('exportBtnText').innerText = '✂️ Execute Standard 3-Way Split (Opening / Sermon / Closing)';
  }
}

function renderExportResults(summary) {
  const outputSection = document.getElementById('outputSection');
  const filesList = document.getElementById('filesList');
  outputSection.classList.remove('hidden');

  filesList.innerHTML = '';
  const sourcePath = summary.source_file || currentAudioPath;

  summary.files.forEach((f, idx) => {
    const isAudio = f.filename.endsWith('.wav') || f.filename.endsWith('.mp3') || f.filename.endsWith('.m4a');
    const item = document.createElement('div');
    item.className = 'file-card';
    item.id = `fileCard_${idx}`;

    const streamUrl = `/api/audio-stream?path=${encodeURIComponent(f.path)}`;
    const startVal = f.start !== undefined ? f.start : 0;
    const endVal = f.end !== undefined ? f.end : (f.duration || 0);

    item.innerHTML = `
      <div class="file-card-header">
        <div class="file-card-title-group">
          <span class="file-num">${idx + 1}</span>
          <div>
            <h4 class="file-card-title">${f.label}</h4>
            <span class="file-card-path">${f.filename}</span>
          </div>
        </div>
        <div class="file-card-meta">
          <span class="badge badge-tech" id="rangeBadge_${idx}">${f.formatted_range || formatTime(f.duration)}</span>
          <span class="badge badge-whisper" id="durBadge_${idx}">${formatDuration(f.duration)}</span>
        </div>
      </div>

      ${isAudio ? `
        <div class="file-player-row">
          <audio controls preload="none" class="split-audio-player" id="player_${idx}" src="${streamUrl}"></audio>
          <button class="btn btn-secondary btn-small" onclick="toggleEditPanel(${idx})">✏️ Edit & Re-Cut</button>
        </div>

        <div class="inline-edit-panel hidden" id="editPanel_${idx}">
          <div class="edit-panel-grid">
            <div class="edit-bound-col">
              <label>Start Timestamp:</label>
              <div class="quick-adjust-row">
                <input type="text" class="time-input" id="editStart_${idx}" value="${formatTime(startVal)}" />
                <button class="btn-micro" onclick="nudgeFileTime(${idx}, 'start', -5)">-5s</button>
                <button class="btn-micro" onclick="nudgeFileTime(${idx}, 'start', -1)">-1s</button>
                <button class="btn-micro" onclick="nudgeFileTime(${idx}, 'start', 1)">+1s</button>
                <button class="btn-micro" onclick="nudgeFileTime(${idx}, 'start', 5)">+5s</button>
              </div>
              <button class="btn-micro-listen" onclick="previewSourceAt('${sourcePath}', ${idx}, 'start')">🎧 Listen Start Transition</button>
            </div>

            <div class="edit-bound-col">
              <label>End Timestamp:</label>
              <div class="quick-adjust-row">
                <input type="text" class="time-input" id="editEnd_${idx}" value="${formatTime(endVal)}" />
                <button class="btn-micro" onclick="nudgeFileTime(${idx}, 'end', -5)">-5s</button>
                <button class="btn-micro" onclick="nudgeFileTime(${idx}, 'end', -1)">-1s</button>
                <button class="btn-micro" onclick="nudgeFileTime(${idx}, 'end', 1)">+1s</button>
                <button class="btn-micro" onclick="nudgeFileTime(${idx}, 'end', 5)">+5s</button>
              </div>
              <button class="btn-micro-listen" onclick="previewSourceAt('${sourcePath}', ${idx}, 'end')">🎧 Listen End Transition</button>
            </div>
          </div>

          <div class="edit-panel-footer">
            <button class="btn btn-primary btn-small" id="recutBtn_${idx}" onclick="recutSingleFile('${sourcePath}', '${f.path.replace(/\\/g, '\\\\')}', ${idx})">
              ✂️ Re-cut This File Losslessly (-c copy)
            </button>
            <span class="recut-status" id="recutStatus_${idx}"></span>
          </div>
        </div>
      ` : ''}
    `;
    filesList.appendChild(item);
  });

  outputSection.scrollIntoView({ behavior: 'smooth' });
}

function toggleEditPanel(idx) {
  const panel = document.getElementById(`editPanel_${idx}`);
  if (panel) {
    panel.classList.toggle('hidden');
  }
}

function nudgeFileTime(idx, type, delta) {
  const input = document.getElementById(type === 'start' ? `editStart_${idx}` : `editEnd_${idx}`);
  if (!input) return;
  let t = parseTime(input.value);
  t = Math.max(0, t + delta);
  input.value = formatTime(t);
}

function previewSourceAt(src, idx, type) {
  const input = document.getElementById(type === 'start' ? `editStart_${idx}` : `editEnd_${idx}`);
  if (!input) return;
  const t = parseTime(input.value);
  const audioEl = document.getElementById('audioPreview');
  const streamUrl = `/api/audio-stream?path=${encodeURIComponent(src)}`;
  if (!audioEl.src.includes(encodeURIComponent(src))) {
    audioEl.src = streamUrl;
  }
  audioEl.currentTime = Math.max(0, t - 6);
  audioEl.play();
}

async function recutSingleFile(src, dst, idx) {
  const startInput = document.getElementById(`editStart_${idx}`);
  const endInput = document.getElementById(`editEnd_${idx}`);
  const statusEl = document.getElementById(`recutStatus_${idx}`);
  const recutBtn = document.getElementById(`recutBtn_${idx}`);

  const s = parseTime(startInput.value);
  const e = parseTime(endInput.value);

  if (e <= s) {
    alert('End time must be after start time.');
    return;
  }

  recutBtn.disabled = true;
  statusEl.innerText = '⏳ Cutting...';
  statusEl.style.color = '#38bdf8';

  try {
    const metaPayload = getMetadataPayload();
    const res = await fetch('/api/resplit-single-track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_audio_path: src,
        output_path: dst,
        start: s,
        end: e,
        metadata: metaPayload.metadata,
        cover_art_path: metaPayload.cover_art_path,
        normalize_loudness: metaPayload.normalize_loudness
      })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    // Update player and badges
    const player = document.getElementById(`player_${idx}`);
    if (player) {
      player.src = `/api/audio-stream?path=${encodeURIComponent(dst)}&v=${Date.now()}`;
      player.load();
    }
    const rangeBadge = document.getElementById(`rangeBadge_${idx}`);
    if (rangeBadge) rangeBadge.innerText = data.formatted_range;
    const durBadge = document.getElementById(`durBadge_${idx}`);
    if (durBadge) durBadge.innerText = formatDuration(data.duration);

    statusEl.innerText = '✓ Re-cut successfully!';
    statusEl.style.color = '#34d399';
  } catch (err) {
    statusEl.innerText = '❌ Error: ' + err.message;
    statusEl.style.color = '#f87171';
  } finally {
    recutBtn.disabled = false;
  }
}

async function loadSavedSplitsFolder() {
  const folderInput = document.getElementById('loadFolderInput');
  const folderPath = folderInput ? folderInput.value.trim() : '';
  if (!folderPath) {
    alert('Please enter a folder path with split files.');
    return;
  }

  try {
    const res = await fetch('/api/load-split-summary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folderPath })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    if (data.source_file) {
      currentAudioPath = data.source_file;
      document.getElementById('audioPath').value = data.source_file;
      setupAudioPlayer(data.source_file);
    }
    if (data.source_duration_seconds) {
      currentDuration = data.source_duration_seconds;
    }

    // Populate customTracks table
    if (data.files && data.files.length > 0) {
      customTracks = data.files.filter(f => f.start !== undefined).map(f => ({
        label: f.label,
        start: f.start,
        end: f.end
      }));
      document.getElementById('resultsSection').classList.remove('hidden');
      renderTracks();
    }

    renderExportResults(data);
  } catch (err) {
    alert('Failed to load saved cuts: ' + err.message);
  }
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

// --- Multi-Track Service Builder Logic ---
let customTracks = [];

function renderTracks() {
  const tbody = document.getElementById('tracksTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (customTracks.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: #94a3b8; padding: 20px;">No custom tracks added yet. Click <strong>☀️ Sunday School</strong>, <strong>📖 Sunday Morning</strong>, <strong>🕯️ Wednesday</strong>, <strong>🔥 Friday</strong>, or <strong>+ Add Track</strong> above.</td></tr>`;
    updateSelectionCountUI();
    return;
  }

  customTracks.forEach((t, i) => {
    if (t.selected === undefined) t.selected = true;
    const isSelected = t.selected !== false;
    const durSec = Math.max(0, t.end - t.start);
    const tr = document.createElement('tr');
    if (isSelected) tr.className = 'track-selected-row';

    tr.innerHTML = `
      <td style="text-align: center;">
        <input type="checkbox" class="track-check" ${isSelected ? 'checked' : ''} onchange="toggleTrackSelected(${i}, this.checked)" title="Include in export" />
      </td>
      <td style="color: #64748b; font-weight: 600;">${i + 1}</td>
      <td>
        <input type="text" value="${t.label}" onchange="updateTrack(${i}, 'label', this.value)" style="width: 100%;" />
      </td>
      <td>
        <div style="display: flex; gap: 2px; align-items: center;">
          <input type="text" class="time-input" value="${formatTime(t.start)}" onchange="updateTrack(${i}, 'start', this.value)" style="width: 75px;" />
          <button class="btn-micro" onclick="nudgeTrack(${i}, 'start', -1)">-1</button>
          <button class="btn-micro" onclick="nudgeTrack(${i}, 'start', 1)">+1</button>
        </div>
      </td>
      <td>
        <div style="display: flex; gap: 2px; align-items: center;">
          <input type="text" class="time-input" value="${formatTime(t.end)}" onchange="updateTrack(${i}, 'end', this.value)" style="width: 75px;" />
          <button class="btn-micro" onclick="nudgeTrack(${i}, 'end', -1)">-1</button>
          <button class="btn-micro" onclick="nudgeTrack(${i}, 'end', 1)">+1</button>
        </div>
      </td>
      <td style="font-family: var(--font-mono); color: #38bdf8;">${formatDuration(durSec)}</td>
      <td>
        <div style="display: flex; gap: 4px;">
          <button class="btn-track-play" onclick="previewTrack(${i})" title="Play this entire track">▶ Play</button>
          <button class="btn-micro" onclick="previewTrackTransition(${i}, 'start')" title="Listen to cut start">🎧 Start</button>
          <button class="btn-micro" onclick="previewTrackTransition(${i}, 'end')" title="Listen to cut end">🎧 End</button>
        </div>
      </td>
      <td style="text-align: center;">
        <button class="btn-micro-export" onclick="exportSingleTrackByIndex(${i})" title="Export only this individual track">✂️ Export This</button>
      </td>
      <td>
        <button class="btn-delete" onclick="deleteTrack(${i})" title="Remove track">✕</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  updateSelectionCountUI();
}

function toggleTrackSelected(index, isChecked) {
  if (customTracks[index]) {
    customTracks[index].selected = isChecked;
  }
  const tbody = document.getElementById('tracksTableBody');
  if (tbody && tbody.children[index]) {
    if (isChecked) {
      tbody.children[index].classList.add('track-selected-row');
    } else {
      tbody.children[index].classList.remove('track-selected-row');
    }
  }
  updateSelectionCountUI();
}

function selectAllTracks(isSelected) {
  customTracks.forEach(t => t.selected = isSelected);
  renderTracks();
}

function selectPreachingOnly() {
  customTracks.forEach(t => {
    const lbl = (t.label || "").toLowerCase();
    t.selected = lbl.includes("preach") || lbl.includes("sermon") || lbl.includes("message") || lbl.includes("teaching");
  });
  renderTracks();
}

function selectSongsOnly() {
  customTracks.forEach(t => {
    const lbl = (t.label || "").toLowerCase();
    t.selected = lbl.includes("song") || lbl.includes("worship") || lbl.includes("praise") || lbl.includes("hymn") || lbl.includes("music");
  });
  renderTracks();
}

function updateSelectionCountUI() {
  const total = customTracks.length;
  const selectedCount = customTracks.filter(t => t.selected !== false).length;

  const counterEl = document.getElementById('selectedTracksCounter');
  if (counterEl) {
    if (total === 0) {
      counterEl.innerText = 'No tracks added';
    } else if (selectedCount === total) {
      counterEl.innerText = `All ${total} tracks selected`;
    } else {
      counterEl.innerText = `${selectedCount} of ${total} tracks selected`;
    }
  }

  const btnCountEl = document.getElementById('btnSelectedCount');
  if (btnCountEl) {
    btnCountEl.innerText = selectedCount === total ? 'All' : `${selectedCount} tracks`;
  }

  const selectAllCb = document.getElementById('selectAllCheckbox');
  if (selectAllCb) {
    selectAllCb.checked = total > 0 && selectedCount === total;
    selectAllCb.indeterminate = selectedCount > 0 && selectedCount < total;
  }
}

function nudgeTrack(index, field, delta) {
  if (field === 'start') {
    customTracks[index].start = Math.max(0, customTracks[index].start + delta);
  } else if (field === 'end') {
    customTracks[index].end = Math.max(0, customTracks[index].end + delta);
  }
  renderTracks();
}

function previewTrackTransition(index, edge) {
  const t = customTracks[index];
  if (!t) return;
  const targetTime = edge === 'start' ? t.start : t.end;
  const audioEl = document.getElementById('audioPreview');
  audioEl.currentTime = Math.max(0, targetTime - 5);
  audioEl.play();
  const stopTime = targetTime + 5;
  const onTimeUpdate = () => {
    if (audioEl.currentTime >= stopTime) {
      audioEl.pause();
      audioEl.removeEventListener('timeupdate', onTimeUpdate);
    }
  };
  audioEl.addEventListener('timeupdate', onTimeUpdate);
}

function updateTrack(index, field, val) {
  if (field === 'start') {
    customTracks[index].start = parseTime(val);
  } else if (field === 'end') {
    customTracks[index].end = parseTime(val);
  } else if (field === 'label') {
    customTracks[index].label = val.trim();
  }
  renderTracks();
}

function addNewTrack(label = "", start = 0, end = 0) {
  if (!label) {
    const lastEnd = customTracks.length > 0 ? customTracks[customTracks.length - 1].end : 0;
    start = lastEnd;
    end = Math.min(currentDuration || (start + 300), start + 300);
    label = `Track ${customTracks.length + 1}`;
  }
  customTracks.push({ label, start, end, selected: true });
  renderTracks();
}

function deleteTrack(index) {
  customTracks.splice(index, 1);
  renderTracks();
}

function previewTrack(index) {
  const t = customTracks[index];
  if (!t) return;
  const audioEl = document.getElementById('audioPreview');
  audioEl.currentTime = t.start;
  audioEl.play();
  const onTimeUpdate = () => {
    if (audioEl.currentTime >= t.end) {
      audioEl.pause();
      audioEl.removeEventListener('timeupdate', onTimeUpdate);
    }
  };
  audioEl.addEventListener('timeupdate', onTimeUpdate);
}

// Preset: Sunday School (11 AM) + Sunday Worship Service (12 PM)
function prefillSundaySchoolAndService() {
  const sStart = currentStart || 3954;
  const sEnd = currentEnd || 6136;
  const msgTitle = (document.getElementById('metaMessageTitle') && document.getElementById('metaMessageTitle').value.trim()) || "Preaching";

  const totalDur = currentDuration || (sEnd + 1800);
  const ssEnd = Math.min(sStart, 2700);

  customTracks = [
    { label: "Sunday School Opening Praise & Prayer", start: 0, end: Math.min(300, ssEnd), selected: true },
    { label: "Adult Sunday School Teaching", start: Math.min(300, ssEnd), end: Math.max(Math.min(300, ssEnd), ssEnd - 300), selected: true },
    { label: "Sunday School Dismissal / Service Transition", start: Math.max(Math.min(300, ssEnd), ssEnd - 300), end: ssEnd, selected: true },
    { label: "Worship Song 1 (Opening Praise)", start: ssEnd, end: ssEnd + Math.floor((sStart - ssEnd) * 0.35), selected: true },
    { label: "Worship Song 2", start: ssEnd + Math.floor((sStart - ssEnd) * 0.35), end: ssEnd + Math.floor((sStart - ssEnd) * 0.70), selected: true },
    { label: "Worship Song 3 / Congregational Praise", start: ssEnd + Math.floor((sStart - ssEnd) * 0.70), end: sStart, selected: true },
    { label: `Preaching - ${msgTitle}`, start: sStart, end: sEnd, selected: true },
    { label: "Altar Call Worship & Prayer", start: sEnd, end: Math.min(totalDur, sEnd + 600), selected: true },
    { label: "Dismissal & Fellowship", start: Math.min(totalDur, sEnd + 600), end: totalDur, selected: true }
  ];

  const serviceSelect = document.getElementById('metaServiceType');
  if (serviceSelect) {
    serviceSelect.value = "Sunday Morning Service";
    onServiceTypeChange("Sunday Morning Service");
  }
  renderTracks();
}

// Preset: Sunday Morning Worship Service (12:00 PM)
function prefillSundayMorning() {
  const sStart = currentStart || 1125; // approx 18m 45s
  const sEnd = currentEnd || 3270;   // approx 54m 30s
  const totalDur = currentDuration || (sEnd + 600);
  const msgTitle = (document.getElementById('metaMessageTitle') && document.getElementById('metaMessageTitle').value.trim()) || "Preaching";

  const songCount = 4;
  const songDur = Math.max(120, Math.floor(sStart / songCount));

  customTracks = [
    { label: "Worship Song 1 (Opening)", start: 0, end: songDur, selected: true },
    { label: "Worship Song 2", start: songDur, end: songDur * 2, selected: true },
    { label: "Worship Song 3", start: songDur * 2, end: songDur * 3, selected: true },
    { label: "Worship Song 4 / Congregational Praise", start: songDur * 3, end: sStart, selected: true },
    { label: `Preaching - ${msgTitle}`, start: sStart, end: sEnd, selected: true },
    { label: "Altar Call Worship & Ministry", start: sEnd, end: Math.min(totalDur, sEnd + 450), selected: true },
    { label: "Closing Prayer & Announcements", start: Math.min(totalDur, sEnd + 450), end: totalDur, selected: true }
  ];

  const serviceSelect = document.getElementById('metaServiceType');
  if (serviceSelect) {
    serviceSelect.value = "Sunday Morning Service";
    onServiceTypeChange("Sunday Morning Service");
  }
  renderTracks();
}

// Preset: Midweek Evening Service (Wednesday or Friday)
function prefillMidweekService(day) {
  const sStart = currentStart || 900; // 15 mins
  const sEnd = currentEnd || 2700;   // 45 mins
  const totalDur = currentDuration || (sEnd + 600);
  const msgTitle = (document.getElementById('metaMessageTitle') && document.getElementById('metaMessageTitle').value.trim()) || `${day} Night Teaching`;

  const worshipBreak = Math.floor(sStart / 2);

  customTracks = [
    { label: "Opening Worship Song 1", start: 0, end: worshipBreak, selected: true },
    { label: "Worship Song 2 & Prayer", start: worshipBreak, end: sStart, selected: true },
    { label: `Preaching / Bible Study - ${msgTitle}`, start: sStart, end: sEnd, selected: true },
    { label: "Altar Call & Corporate Prayer", start: sEnd, end: Math.min(totalDur, sEnd + 480), selected: true },
    { label: "Closing Benediction", start: Math.min(totalDur, sEnd + 480), end: totalDur, selected: true }
  ];

  const serviceSelect = document.getElementById('metaServiceType');
  const serviceVal = `${day} Evening Service`;
  if (serviceSelect) {
    serviceSelect.value = serviceVal;
    onServiceTypeChange(serviceVal);
  }
  renderTracks();
}

function prefillRevivalTracks() {
  customTracks = [
    { label: "Worship Song 1 (God Will Make A Way)", start: 0, end: 277, selected: true },
    { label: "Worship Song 2", start: 277, end: 743, selected: true },
    { label: "Worship Song 3", start: 743, end: 955, selected: true },
    { label: "Worship Song 4", start: 955, end: 1590, selected: true },
    { label: "Worship Song 5", start: 1590, end: 1970, selected: true },
    { label: "Worship Song 6", start: 1970, end: 2525, selected: true },
    { label: "Worship Song 7 / Congregational Praise", start: 2525, end: 3954, selected: true },
    { label: "Preaching Part 1 (Matthew 6 - One Look)", start: 3954, end: 6136, selected: true },
    { label: "Altar Call Worship & Prayer", start: 6136, end: 6797, selected: true },
    { label: "Preaching Part 2 (Spirit-Led Exhortation)", start: 6797, end: 8159, selected: true },
    { label: "Testimonies & Closing Prayer", start: 8159, end: currentDuration || 10583, selected: true }
  ];
  const serviceSelect = document.getElementById('metaServiceType');
  if (serviceSelect) {
    serviceSelect.value = "Revival / Special Service";
    onServiceTypeChange("Revival / Special Service");
  }
  renderTracks();
}

async function autoDetectWorshipSongs() {
  const audioPath = document.getElementById('audioPath').value.trim();
  if (!audioPath) {
    alert('Please enter or upload an audio file first.');
    return;
  }
  const preachingStart = parseTime(document.getElementById('sermonStartInput').value) || 3954;
  try {
    const res = await fetch('/api/detect-songs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audio_path: audioPath, worship_end: preachingStart })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    if (data.songs && data.songs.length > 0) {
      customTracks = data.songs.map(s => ({
        label: s.label,
        start: s.start,
        end: s.end,
        selected: true
      }));
      const msgTitle = (document.getElementById('metaMessageTitle') && document.getElementById('metaMessageTitle').value.trim()) || "Preaching Part 1";
      customTracks.push({
        label: `Preaching - ${msgTitle}`,
        start: preachingStart,
        end: parseTime(document.getElementById('sermonEndInput').value) || (preachingStart + 2100),
        selected: true
      });
      renderTracks();
    }
  } catch (err) {
    alert('Auto song detection error: ' + err.message);
  }
}

// Export only the tracks selected with checkboxes (or all if all checked)
async function exportSelectedTracks() {
  const audioPath = document.getElementById('audioPath').value.trim();
  let outputDir = document.getElementById('outputDir').value.trim();
  if (!audioPath) {
    alert('Please enter or upload an audio file first.');
    return;
  }
  if (!outputDir) {
    outputDir = audioPath.replace(/\.[^/.]+$/, "") + "_splits";
  }

  const selectedTracks = customTracks
    .map((t, idx) => ({ ...t, track_number: idx + 1 }))
    .filter(t => t.selected !== false);

  if (selectedTracks.length === 0) {
    alert('Please select at least one track to export using the checkboxes.');
    return;
  }

  const exportBtn = document.getElementById('exportTracksBtn');
  exportBtn.disabled = true;
  const originalBtnHtml = document.getElementById('exportTracksBtnText').innerHTML;
  document.getElementById('exportTracksBtnText').innerText = `Cutting & Tagging ${selectedTracks.length} Track(s)...`;

  const metaPayload = getMetadataPayload();

  try {
    const res = await fetch('/api/export-tracks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        audio_path: audioPath,
        output_dir: outputDir,
        tracks: selectedTracks,
        metadata: metaPayload.metadata,
        cover_art_path: metaPayload.cover_art_path,
        normalize_loudness: metaPayload.normalize_loudness,
        export_mp3: metaPayload.export_mp3
      })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderExportResults(data);
  } catch (err) {
    alert('Export error: ' + err.message);
  } finally {
    exportBtn.disabled = false;
    document.getElementById('exportTracksBtnText').innerHTML = originalBtnHtml;
  }
}

// Quick export a single track by row index
async function exportSingleTrackByIndex(index) {
  const audioPath = document.getElementById('audioPath').value.trim();
  let outputDir = document.getElementById('outputDir').value.trim();
  if (!audioPath) {
    alert('Please enter or upload an audio file first.');
    return;
  }
  if (!outputDir) {
    outputDir = audioPath.replace(/\.[^/.]+$/, "") + "_splits";
  }

  const t = customTracks[index];
  if (!t) return;

  const trackToExport = [{
    label: t.label,
    start: t.start,
    end: t.end,
    track_number: index + 1
  }];

  const metaPayload = getMetadataPayload();

  try {
    const res = await fetch('/api/export-tracks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        audio_path: audioPath,
        output_dir: outputDir,
        tracks: trackToExport,
        metadata: metaPayload.metadata,
        cover_art_path: metaPayload.cover_art_path,
        normalize_loudness: metaPayload.normalize_loudness,
        export_mp3: metaPayload.export_mp3
      })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderExportResults(data);
  } catch (err) {
    alert(`Failed to export track "${t.label}": ` + err.message);
  }
}

// Quick export preaching track directly for Spotify for Creators
async function exportPreachingOnlyQuick() {
  const audioPath = document.getElementById('audioPath').value.trim();
  let outputDir = document.getElementById('outputDir').value.trim();
  if (!audioPath) {
    alert('Please enter or upload an audio file first.');
    return;
  }
  if (!outputDir) {
    outputDir = audioPath.replace(/\.[^/.]+$/, "") + "_splits";
  }

  let preachingTracks = customTracks
    .map((t, idx) => ({ ...t, track_number: idx + 1 }))
    .filter(t => {
      const lbl = (t.label || "").toLowerCase();
      return lbl.includes("preach") || lbl.includes("sermon") || lbl.includes("message") || lbl.includes("teaching");
    });

  if (preachingTracks.length === 0) {
    const sStart = currentStart || parseTime(document.getElementById('sermonStartInput').value) || 0;
    const sEnd = currentEnd || parseTime(document.getElementById('sermonEndInput').value) || currentDuration;
    const msgTitle = (document.getElementById('metaMessageTitle') && document.getElementById('metaMessageTitle').value.trim()) || "Preaching";
    preachingTracks = [{
      label: `Preaching - ${msgTitle}`,
      start: sStart,
      end: sEnd,
      track_number: 1
    }];
  }

  const metaPayload = getMetadataPayload();

  try {
    const res = await fetch('/api/export-tracks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        audio_path: audioPath,
        output_dir: outputDir,
        tracks: preachingTracks,
        metadata: metaPayload.metadata,
        cover_art_path: metaPayload.cover_art_path,
        normalize_loudness: metaPayload.normalize_loudness,
        export_mp3: metaPayload.export_mp3
      })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderExportResults(data);
  } catch (err) {
    alert('Failed to export preaching track: ' + err.message);
  }
}

// ================= AI Scripture & Social Summary =================

async function autoExtractSermonSummary(transcript) {
  if (!transcript) return;
  const preacher = document.getElementById('metaPreacher') ? document.getElementById('metaPreacher').value.trim() : "";
  const series = document.getElementById('metaAlbum') ? document.getElementById('metaAlbum').value.trim() : "";
  const serviceType = document.getElementById('metaServiceType') ? document.getElementById('metaServiceType').value : "";
  const msgTitle = (document.getElementById('metaMessageTitle') && document.getElementById('metaMessageTitle').value.trim()) || 
                   (document.getElementById('aiSermonTitle') && document.getElementById('aiSermonTitle').value.trim()) || "";

  try {
    const res = await fetch('/api/extract-sermon-info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transcript: transcript,
        preacher: preacher,
        series: series,
        service_type: serviceType,
        title: msgTitle || undefined
      })
    });
    if (!res.ok) return;
    const data = await res.json();
    populateAISummary(data);
  } catch (err) {
    console.error('Error auto-extracting sermon info:', err);
  }
}

async function generateAISummary() {
  const transcript = detectedResult && detectedResult.sermon_transcript 
    ? detectedResult.sermon_transcript 
    : document.getElementById('transcriptText').innerText;

  if (!transcript || transcript.trim().length === 0) {
    alert('No sermon transcript available. Please run analysis first or load a service.');
    return;
  }
  const preacher = document.getElementById('metaPreacher') ? document.getElementById('metaPreacher').value.trim() : "";
  const series = document.getElementById('metaAlbum') ? document.getElementById('metaAlbum').value.trim() : "";
  const serviceType = document.getElementById('metaServiceType') ? document.getElementById('metaServiceType').value : "";
  const msgTitle = (document.getElementById('metaMessageTitle') && document.getElementById('metaMessageTitle').value.trim()) || 
                   (document.getElementById('aiSermonTitle') && document.getElementById('aiSermonTitle').value.trim()) || "";

  try {
    const res = await fetch('/api/extract-sermon-info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transcript: transcript,
        preacher: preacher,
        series: series,
        service_type: serviceType,
        title: msgTitle || undefined
      })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    populateAISummary(data);
  } catch (err) {
    alert('AI Summary generation error: ' + err.message);
  }
}

function populateAISummary(data) {
  const section = document.getElementById('aiSummarySection');
  if (section) section.classList.remove('hidden');

  const titleInput = document.getElementById('aiSermonTitle');
  const metaTitleInput = document.getElementById('metaMessageTitle');
  if (data.title) {
    if (titleInput && (!titleInput.value || titleInput.value.trim().length === 0)) {
      titleInput.value = data.title;
    }
    if (metaTitleInput && (!metaTitleInput.value || metaTitleInput.value.trim().length === 0)) {
      metaTitleInput.value = data.title;
    }
  }
  
  const pillsContainer = document.getElementById('scripturePills');
  if (pillsContainer) {
    pillsContainer.innerHTML = '';
    if (data.scriptures && data.scriptures.length > 0) {
      data.scriptures.forEach(sc => {
        const pill = document.createElement('span');
        pill.className = 'scripture-pill';
        pill.innerText = `📖 ${sc}`;
        pillsContainer.appendChild(pill);
      });
    } else {
      pillsContainer.innerHTML = '<span style="color: var(--text-secondary); font-size: 0.85rem;">None detected</span>';
    }
  }

  const quoteEl = document.getElementById('aiQuoteText');
  if (quoteEl) {
    quoteEl.innerText = data.summary_quote ? `"${data.summary_quote}"` : 'No highlighted quote extracted.';
  }

  const postEl = document.getElementById('aiSocialPostText');
  if (postEl) {
    postEl.value = data.social_post || '';
  }

  const spotifyNotesEl = document.getElementById('aiSpotifyNotesText');
  if (spotifyNotesEl) {
    spotifyNotesEl.value = data.spotify_notes || '';
  }
}

function copySocialPost() {
  const textarea = document.getElementById('aiSocialPostText');
  if (!textarea) return;
  textarea.select();
  navigator.clipboard.writeText(textarea.value).then(() => {
    alert('✓ Social media post copied to clipboard!');
  }).catch(() => {
    document.execCommand('copy');
    alert('✓ Social media post copied to clipboard!');
  });
}

function copySpotifyNotes() {
  const textarea = document.getElementById('aiSpotifyNotesText');
  if (!textarea) return;
  textarea.select();
  navigator.clipboard.writeText(textarea.value).then(() => {
    alert('✓ Spotify for Creators notes copied to clipboard!\nReady to paste into Spotify & website.');
  }).catch(() => {
    document.execCommand('copy');
    alert('✓ Spotify for Creators notes copied to clipboard!');
  });
}

// ================= Watch Folder & Automation =================

function toggleWatcherCollapse() {
  const body = document.getElementById('watcherBody');
  const icon = document.getElementById('watcherToggleIcon');
  if (body.classList.contains('hidden')) {
    body.classList.remove('hidden');
    icon.innerText = '▼';
  } else {
    body.classList.add('hidden');
    icon.innerText = '▲';
  }
}

async function checkWatcherStatus() {
  try {
    const res = await fetch('/api/watcher/status');
    if (!res.ok) return;
    const data = await res.json();
    updateWatcherUI(data);
  } catch (e) {
    console.error('Watcher poll error:', e);
  }
}

function updateWatcherUI(data) {
  const badge = document.getElementById('watcherStatusBadge');
  const startBtn = document.getElementById('watcherStartBtn');
  const stopBtn = document.getElementById('watcherStopBtn');
  const logEl = document.getElementById('watcherLogs');
  const msgEl = document.getElementById('watcherCurrentMsg');

  if (!badge) return;

  if (data.is_running) {
    badge.innerText = (data.status || 'RUNNING').toUpperCase();
    badge.style.background = data.status === 'processing' ? '#f59e0b' : '#10b981';
    badge.style.color = '#fff';
    startBtn.classList.add('hidden');
    stopBtn.classList.remove('hidden');
    msgEl.innerText = data.current_file ? `Processing: ${data.current_file}` : 'Watching folder for new audio recordings...';
  } else {
    badge.innerText = 'STOPPED';
    badge.style.background = '#475569';
    badge.style.color = '#fff';
    startBtn.classList.remove('hidden');
    stopBtn.classList.add('hidden');
    msgEl.innerText = '';
  }

  if (data.logs && data.logs.length > 0 && logEl) {
    logEl.innerText = data.logs.join('\n');
    logEl.scrollTop = logEl.scrollHeight;
  }
}

async function startFolderWatcher() {
  const watchFolder = document.getElementById('watcherWatchFolder').value.trim();
  const outputFolder = document.getElementById('watcherOutputFolder').value.trim();
  const preacher = document.getElementById('watcherPreacher').value.trim();
  const series = document.getElementById('watcherSeries').value.trim();
  const metaPayload = getMetadataPayload();

  if (!watchFolder) {
    alert('Please enter a watch folder path to monitor.');
    return;
  }

  try {
    const res = await fetch('/api/watcher/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        watch_folder: watchFolder,
        output_folder: outputFolder || null,
        default_preacher: preacher,
        default_series: series,
        default_genre: "Sermon",
        normalize_loudness: metaPayload.normalize_loudness,
        export_mp3: metaPayload.export_mp3,
        cover_art_path: metaPayload.cover_art_path,
        model_size: document.getElementById('modelSize').value
      })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    updateWatcherUI(data);
    if (!watcherPollTimer) {
      watcherPollTimer = setInterval(checkWatcherStatus, 3000);
    }
    alert(`✓ Watcher is now active! Monitoring:\n${watchFolder}`);
  } catch (err) {
    alert('Failed to start watcher: ' + err.message);
  }
}

async function stopFolderWatcher() {
  try {
    const res = await fetch('/api/watcher/stop', { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    updateWatcherUI(data);
    if (watcherPollTimer) {
      clearInterval(watcherPollTimer);
      watcherPollTimer = null;
    }
  } catch (err) {
    alert('Failed to stop watcher: ' + err.message);
  }
}

// Initial watcher poll on load
checkWatcherStatus();
setInterval(checkWatcherStatus, 6000);
