'use strict';
const $ = s => document.querySelector(s);

let lastPhase = '';

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  return r.json();
}

function showError(msg) { const e = $('#error'); e.hidden = !msg; e.textContent = msg || ''; }

function fmtT(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function renderHighlights(hl) {
  const L = $('#highlight-list'); L.innerHTML = '';
  if (!hl.length) { L.innerHTML = '<p class="dim">No highlights detected for this focus.</p>'; return; }
  hl.forEach((h, i) => {
    const row = document.createElement('div');
    row.className = 'hl';
    row.innerHTML = `<input type="checkbox" checked data-i="${i}">
      <span class="type ${h.type}">${h.type}</span>
      <span class="label">${h.label}</span>
      <span class="when">lap ${h.lap ?? '?'} · ${fmtT(Math.max(0, h.t_start))}–${fmtT(h.t_end)} · ${(h.t_end - h.t_start).toFixed(0)}s</span>`;
    L.appendChild(row);
  });
}

async function poll() {
  try {
    const st = await api('/api/status');
    const pill = $('#sim-status');
    pill.textContent = st.connected ? 'iRacing connected' : 'iRacing not running';
    pill.className = 'pill ' + (st.connected ? 'ok' : 'bad');

    const focus = $('#focus');
    if (st.drivers.length && focus.options.length <= 1) {
      for (const d of st.drivers) {
        const o = document.createElement('option');
        o.value = d.idx; o.textContent = `#${d.number} ${d.name}`;
        focus.appendChild(o);
      }
    }

    const job = st.job;
    showError(job.error);
    const scanning = job.phase === 'scanning';
    const busy = ['scanning', 'recording', 'cutting'].includes(job.phase);
    $('#btn-scan').disabled = busy;
    $('#btn-stop').hidden = !busy;
    $('#scan-progress').hidden = !scanning;
    if (scanning) {
      $('#scan-progress .bar').style.width = `${(job.progress * 100).toFixed(0)}%`;
      $('#scan-progress .ptext').textContent = job.message;
    }
    const recProg = $('#rec-progress');
    recProg.hidden = !(job.phase === 'recording' || job.phase === 'cutting');
    if (!recProg.hidden) {
      recProg.querySelector('.bar').style.width = `${(job.progress * 100).toFixed(0)}%`;
      recProg.querySelector('.ptext').textContent = job.message;
    }
    const log = $('#rec-log');
    log.hidden = !(job.log && job.log.length);
    if (!log.hidden) log.textContent = job.log.join('\n');
    $('#btn-record').disabled = busy;

    if (job.phase !== lastPhase) {
      if (job.phase === 'scanned' || job.phase === 'done') {
        $('#step3').hidden = false;
        renderHighlights(job.highlights);
      }
      if (job.phase === 'done' && job.reel) {
        $('#step4').hidden = false;
        $('#reel-path').textContent = job.reel;
      }
      lastPhase = job.phase;
    }
  } catch { /* server briefly busy — keep polling */ }
  setTimeout(poll, 1000);
}

$('#btn-scan').onclick = async () => {
  showError(null);
  $('#step3').hidden = true; $('#step4').hidden = true;
  const r = await api('/api/scan', { speed: parseInt($('#scan-speed').value, 10) });
  if (r.error) showError(r.error);
};

$('#btn-stop').onclick = () => api('/api/stop', {});

$('#focus').onchange = async () => {
  const r = await api('/api/detect', { focus: $('#focus').value });
  if (r.error) return showError(r.error);
  renderHighlights(r.highlights);
};

$('#capture').onchange = () => {
  $('#obs-pass-wrap').style.display = $('#capture').value === 'obs' ? '' : 'none';
};

$('#btn-record').onclick = async () => {
  showError(null);
  const selected = [...document.querySelectorAll('#highlight-list input:checked')]
    .map(x => parseInt(x.dataset.i, 10));
  const r = await api('/api/record', {
    selected,
    capture: $('#capture').value,
    obs_password: $('#obs-password').value,
  });
  if (r.error) showError(r.error);
};

$('#btn-folder').onclick = () => api('/api/open-folder', {});

$('#btn-test-capture').onclick = async () => {
  const out = $('#capture-test-result');
  out.hidden = false;
  out.textContent = 'Recording a 4-second test…';
  const r = await api('/api/capture-test', {
    capture: $('#capture').value,
    obs_password: $('#obs-password').value,
  });
  out.textContent = (r.ok ? '✔ ' : '✘ ') + r.detail;
  out.style.color = r.ok ? '#3fb950' : '#e5484d';
};

poll();
