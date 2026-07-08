/* =====================================================================
   DDR Frontend — app.js
   API base: http://localhost:8000/api
   Endpoints used:
     POST /api/upload            – upload PDFs
     POST /api/process           – run AI pipeline
     GET  /api/report            – fetch JSON report
     GET  /api/export/pdf        – download PDF
   ===================================================================== */

// ─── Config & State ────────────────────────────────────────────────────────
const API = window.location.port === '8080' ? 'http://localhost:8000/api' : '/api';
let uploadedOk = false;
let reportData  = null;

// ─── DOM refs ─────────────────────────────────────────────────────────
const fileInspection  = document.getElementById('fileInspection');
const fileThermal     = document.getElementById('fileThermal');
const dropInspection  = document.getElementById('dropInspection');
const dropThermal     = document.getElementById('dropThermal');
const nameInspection  = document.getElementById('nameInspection');
const nameThermal     = document.getElementById('nameThermal');
const btnUpload       = document.getElementById('btnUpload');
const uploadProgress  = document.getElementById('uploadProgress');
const uploadProgressBar = document.getElementById('uploadProgressBar');
const uploadToast     = document.getElementById('uploadToast');

const btnProcess      = document.getElementById('btnProcess');
const processToast    = document.getElementById('processToast');
const pipeSteps       = [1,2,3,4,5,6].map(i => document.getElementById(`pipe${i}`));

const reportSection   = document.getElementById('reportSection');
const summaryGrid     = document.getElementById('summaryGrid');
const statusBadge     = document.getElementById('statusBadge');
const spinnerOverlay  = document.getElementById('spinnerOverlay');
const spinnerLabel    = document.getElementById('spinnerLabel');

const btnExportPdf    = document.getElementById('btnExportPdf');
const btnExportJson   = document.getElementById('btnExportJson');

// ─── Status helpers ───────────────────────────────────────────────────
function setStatus(type, text) {
  statusBadge.className = `status-badge status-${type}`;
  statusBadge.textContent = (type === 'loading' ? '⟳ ' : type === 'success' ? '✓ ' : type === 'error' ? '✕ ' : '● ') + text;
}
function showSpinner(label = 'Processing…') {
  spinnerLabel.textContent = label;
  spinnerOverlay.classList.remove('hidden');
}
function hideSpinner() { spinnerOverlay.classList.add('hidden'); }
function showToast(el, type, msg) {
  el.className = `toast show ${type}`;
  el.textContent = msg;
  if (type !== 'error') setTimeout(() => el.classList.remove('show'), 4000);
}

// ─── File inputs ──────────────────────────────────────────────────────
function updateUploadBtn() {
  btnUpload.disabled = !(fileInspection.files[0] && fileThermal.files[0]);
}

fileInspection.addEventListener('change', () => {
  if (fileInspection.files[0]) {
    nameInspection.textContent = fileInspection.files[0].name;
    dropInspection.classList.add('has-file');
  }
  updateUploadBtn();
});
fileThermal.addEventListener('change', () => {
  if (fileThermal.files[0]) {
    nameThermal.textContent = fileThermal.files[0].name;
    dropThermal.classList.add('has-file');
  }
  updateUploadBtn();
});

// Drag & drop
function setupDrop(zone, inputEl, nameEl) {
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.pdf')) {
      const dt = new DataTransfer();
      dt.items.add(file);
      inputEl.files = dt.files;
      nameEl.textContent = file.name;
      zone.classList.add('has-file');
      updateUploadBtn();
    }
  });
}
setupDrop(dropInspection, fileInspection, nameInspection);
setupDrop(dropThermal,    fileThermal,    nameThermal);

// ─── Upload ───────────────────────────────────────────────────────────
btnUpload.addEventListener('click', async () => {
  const insp  = fileInspection.files[0];
  const therm = fileThermal.files[0];
  if (!insp || !therm) return;

  setStatus('loading', 'Uploading…');
  uploadProgress.classList.remove('hidden');
  animateProgress(uploadProgressBar, 80, 600);
  btnUpload.disabled = true;

  const form = new FormData();
  form.append('inspection_report', insp);
  form.append('thermal_report',    therm);

  try {
    const res  = await fetch(`${API}/upload`, { method: 'POST', body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Upload failed');

    animateProgress(uploadProgressBar, 100, 200);
    setTimeout(() => uploadProgress.classList.add('hidden'), 700);
    showToast(uploadToast, 'success', '✓ Files uploaded successfully. Ready to run analysis.');
    setStatus('success', 'Uploaded');
    uploadedOk = true;
    btnProcess.disabled = false;
  } catch (err) {
    showToast(uploadToast, 'error', '✕ ' + err.message);
    setStatus('error', 'Upload failed');
    btnUpload.disabled = false;
    uploadProgress.classList.add('hidden');
  }
});

function animateProgress(bar, target, duration) {
  const start = parseFloat(bar.style.width) || 0;
  const diff  = target - start;
  const tStart = performance.now();
  function step(now) {
    const t = Math.min((now - tStart) / duration, 1);
    bar.style.width = (start + diff * t) + '%';
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ─── Process ──────────────────────────────────────────────────────────
const PIPE_LABELS = [
  'Parse PDFs', 'Extract Images', 'AI Observations',
  'Merge & Severity', 'Conflicts & Summary', 'Link Images'
];

btnProcess.addEventListener('click', async () => {
  setStatus('loading', 'Analysing…');
  showSpinner('Running AI pipeline…');
  btnProcess.disabled = true;
  pipeSteps.forEach(s => { s.classList.remove('active', 'done'); });

  // animate pipeline steps while waiting
  let stepIdx = 0;
  const pipeInterval = setInterval(() => {
    if (stepIdx > 0) pipeSteps[stepIdx - 1].classList.replace('active', 'done');
    if (stepIdx < pipeSteps.length) {
      pipeSteps[stepIdx].classList.add('active');
      spinnerLabel.textContent = PIPE_LABELS[stepIdx] + '…';
      stepIdx++;
    }
  }, 2000);

  try {
    const res  = await fetch(`${API}/process`, { method: 'POST' });
    const data = await res.json();
    clearInterval(pipeInterval);
    if (!res.ok) throw new Error(data.detail || 'Processing failed');

    // mark all steps done
    pipeSteps.forEach(s => { s.classList.remove('active'); s.classList.add('done'); });
    hideSpinner();
    showToast(processToast, 'success', '✓ Report generated successfully!');
    setStatus('success', 'Report ready');

    reportData = data;
    renderReport(data);
  } catch (err) {
    clearInterval(pipeInterval);
    hideSpinner();
    showToast(processToast, 'error', '✕ ' + err.message);
    setStatus('error', 'Analysis failed');
    btnProcess.disabled = false;
  }
});

// ─── Render Report ────────────────────────────────────────────────────
function renderReport(data) {
  reportSection.classList.remove('hidden');
  reportSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

  renderSummary(data.property_summary, data.observations, data.statistics);
  renderObservations(data.observations || []);
  renderRecommendations(data.recommendations || []);
  renderConflicts(data.conflicts || []);
  renderMissing(data.missing_information || []);
}

function renderSummary(s, obs, stats) {
  s = s || {};
  const condition = (s.overall_condition || 'N/A').toLowerCase();
  const condColor = condition.includes('poor') || condition.includes('critical') ? 'val-red'
                  : condition.includes('fair') || condition.includes('moderate') ? 'val-amber'
                  : condition.includes('good') ? 'val-green' : 'val-blue';

  const cards = [
    { label: 'Property',    value: s.property_name || 'N/A',    sub: s.address || '',           color: 'val-blue' },
    { label: 'Condition',   value: s.overall_condition || 'N/A', sub: s.property_type || '',    color: condColor  },
    { label: 'Issues Found',value: s.total_issues_count ?? (obs||[]).length, sub: 'observations', color: 'val-amber' },
    { label: 'Images',      value: stats?.total_images ?? 0,    sub: 'extracted',                color: 'val-blue' },
    { label: 'Insp. Date',  value: s.inspection_date || 'N/A',  sub: '',                        color: 'val-blue' },
  ];

  summaryGrid.innerHTML = cards.map(c => `
    <div class="summary-card">
      <div class="summary-card-label">${c.label}</div>
      <div class="summary-card-value ${c.color}">${c.value}</div>
      ${c.sub ? `<div class="summary-card-sub">${c.sub}</div>` : ''}
    </div>
  `).join('');
}

function sevClass(sev) {
  const s = (sev || '').toLowerCase();
  return s === 'critical' ? 'sev-critical' : s === 'high' ? 'sev-high' : s === 'medium' ? 'sev-medium' : 'sev-low';
}

function renderObservations(obs) {
  const el = document.getElementById('tabObservations');
  if (!obs.length) { el.innerHTML = emptyState('🔍', 'No observations found.'); return; }

  el.innerHTML = `<div class="obs-list">${obs.map((o, i) => {
    const images = (o.supporting_images || []).map(img =>
      `<img class="obs-img" src="${API.replace('/api','')}/api/static/${img}" alt="Supporting image" onerror="this.style.display='none'" />`
    ).join('');

    const extras = [
      o.engineering_finding ? `<p class="obs-detail"><strong>Technical Finding:</strong> ${o.engineering_finding}</p>` : '',
      o.root_cause          ? `<p class="obs-detail"><strong>Root Cause:</strong> ${o.root_cause}</p>` : '',
      o.severity_reason     ? `<p class="obs-detail"><strong>Severity Reason:</strong> ${o.severity_reason}</p>` : '',
      o.measurements        ? `<p class="obs-detail"><strong>Measurements:</strong> ${o.measurements}</p>` : '',
      o.moisture            ? `<p class="obs-detail"><strong>Moisture:</strong> ${o.moisture}</p>` : '',
      o.crack_width         ? `<p class="obs-detail"><strong>Crack Width:</strong> ${o.crack_width}</p>` : '',
      o.temperatures        ? `<p class="obs-detail"><strong>Temperatures:</strong> ${o.temperatures}</p>` : '',
      o.inspector_notes     ? `<p class="obs-detail"><strong>Inspector Notes:</strong> ${o.inspector_notes}</p>` : '',
    ].filter(Boolean).join('');

    return `
    <div class="obs-card">
      <div class="obs-top">
        <div>
          <div class="obs-id">${o.observation_id || `OBS-${i+1}`}</div>
          <div class="obs-location">📍 ${o.location || 'N/A'}</div>
        </div>
        <div class="obs-meta">
          <span class="obs-chip ${sevClass(o.severity)}">${(o.severity || 'Low').toUpperCase()}</span>
          ${(o.supporting_documents || []).map(d => `<span class="obs-chip">${d}</span>`).join('')}
        </div>
      </div>
      <div class="obs-issue">${o.issue || 'No description'}</div>
      ${extras ? `<span class="obs-expand" onclick="toggleExtra(this)">▼ Show details</span><div class="obs-extra hidden">${extras}</div>` : ''}
      ${images ? `<div class="obs-images">${images}</div>` : ''}
    </div>`;
  }).join('')}</div>`;
}

window.toggleExtra = function(el) {
  const extra = el.nextElementSibling;
  const open  = !extra.classList.contains('hidden');
  extra.classList.toggle('hidden', open);
  el.textContent = open ? '▼ Show details' : '▲ Hide details';
};

function renderRecommendations(recs) {
  const el = document.getElementById('tabRecommendations');
  if (!recs.length) { el.innerHTML = emptyState('💡', 'No recommendations generated.'); return; }

  el.innerHTML = recs.map(r => {
    const conf = (r.confidence || '').toLowerCase();
    const confClass = conf === 'high' ? 'conf-high' : conf === 'medium' ? 'conf-medium' : 'conf-low';
    return `
    <div class="rec-card">
      <div class="rec-top">
        <span class="obs-chip ${sevClass(r.severity)}">${(r.severity||'').toUpperCase()}</span>
        <span class="rec-issue">${r.issue || ''}</span>
        <span class="rec-conf ${confClass}">${r.confidence || ''} confidence</span>
      </div>
      <div class="rec-body">${r.recommendation || ''}</div>
    </div>`;
  }).join('');
}

function renderConflicts(conflicts) {
  const el = document.getElementById('tabConflicts');
  if (!conflicts.length) { el.innerHTML = emptyState('✅', 'No conflicts detected between reports.'); return; }

  el.innerHTML = conflicts.map(c => `
    <div class="conflict-card">
      <div class="conf-title">⚠ Conflict — ${(c.documents_involved || []).join(' vs ')}</div>
      <div class="conf-body">${c.reason || ''}</div>
      ${c.recommended_manual_verification ? `<div class="conf-body" style="margin-top:8px;color:var(--text)"><strong>Recommended action:</strong> ${c.recommended_manual_verification}</div>` : ''}
    </div>`).join('');
}

function renderMissing(items) {
  const el = document.getElementById('tabMissing');
  if (!items.length) { el.innerHTML = emptyState('✅', 'No missing information flagged.'); return; }

  el.innerHTML = `<div class="missing-list">${items.map(item =>
    `<div class="missing-item">${item}</div>`
  ).join('')}</div>`;
}

function emptyState(icon, msg) {
  return `<div class="empty-state"><div class="empty-state-icon">${icon}</div>${msg}</div>`;
}

// ─── Tabs ─────────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const name = tab.dataset.tab;
    ['observations','recommendations','conflicts','missing'].forEach(t => {
      const el = document.getElementById(`tab${t.charAt(0).toUpperCase() + t.slice(1)}`);
      el.classList.toggle('hidden', t !== name);
    });
  });
});

// ─── Export ───────────────────────────────────────────────────────────
btnExportPdf.addEventListener('click', async () => {
  setStatus('loading', 'Generating PDF…');
  try {
    const res = await fetch(`${API}/export/pdf`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'PDF export failed');
    }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = 'DDR_Report.pdf';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setStatus('success', 'PDF downloaded');
  } catch (err) {
    alert('PDF export error: ' + err.message);
    setStatus('error', 'Export failed');
  }
});

btnExportJson.addEventListener('click', () => {
  if (!reportData) return;
  const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'DDR_Report.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});

// ─── Auto-load existing report on page load ───────────────────────────
(async () => {
  try {
    const res = await fetch(`${API}/report`);
    if (res.ok) {
      reportData = await res.json();
      btnProcess.disabled = false;
      uploadedOk = true;
      setStatus('success', 'Report available');
      renderReport(reportData);
    }
  } catch (_) { /* no report yet */ }
})();
