const API_BASE = window.location.port === "5000" ? "" : "http://127.0.0.1:5000";

async function requestJSON(path, options) {
    const response = await fetch(API_BASE + path, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        const error = new Error(data.error || ("HTTP " + response.status));
        error.status = response.status;
        error.data = data;
        throw error;
    }
    return data;
}

function plural(count, singular, pluralForm) {
    return count === 1 ? singular : pluralForm;
}

function renderFileList(countId, listId, items) {
    const count = document.getElementById(countId);
    const list = document.getElementById(listId);
    items = Array.isArray(items) ? items : [];

    if (count) {
        count.textContent = items.length === 0
            ? "none"
            : (items.length + " " + plural(items.length, "file", "files"));
    }
    if (!list) return;
    list.innerHTML = "";

    if (items.length === 0) {
        const empty = document.createElement("li");
        empty.className = "empty";
        empty.textContent = "None";
        list.appendChild(empty);
        return;
    }
    for (const file of items) {
        const li = document.createElement("li");
        li.textContent = file;
        list.appendChild(li);
    }
}

function renderDuplicates(countId, listId, duplicates) {
    const count = document.getElementById(countId);
    const list = document.getElementById(listId);
    const groups = duplicates && typeof duplicates === "object"
        ? Object.entries(duplicates)
        : [];

    if (count) {
        count.textContent = groups.length === 0
            ? "none"
            : (groups.length + " " + plural(groups.length, "group", "groups"));
    }
    if (!list) return;
    list.innerHTML = "";

    if (groups.length === 0) {
        const empty = document.createElement("li");
        empty.className = "empty";
        empty.textContent = "None";
        list.appendChild(empty);
        return;
    }
    for (const entry of groups) {
        const hash = entry[0];
        const files = entry[1];
        const group = document.createElement("li");
        const header = document.createElement("strong");
        header.textContent = "Hash: " + hash.slice(0, 16) + "…";
        header.title = hash;
        group.appendChild(header);

        const fileList = document.createElement("ul");
        (Array.isArray(files) ? files : []).forEach((file) => {
            const item = document.createElement("li");
            item.textContent = file;
            fileList.appendChild(item);
        });
        group.appendChild(fileList);
        list.appendChild(group);
    }
}

function renderResults(source) {
    const result = source || {};
    renderFileList("permission-denied-title", "permission-denied-list", result.permission_denied);
    renderFileList("modified-files-title", "modified-files-list", result.modified);
    renderFileList("new-files-title", "new-files-list", result.new);
    renderFileList("deleted-files-title", "deleted-files-list", result.deleted);
    renderDuplicates("duplicate-files-title", "duplicate-files-list", result.duplicates);
}

function readWorkers() {
    const input = document.getElementById('workers');
    if (!input) return 3;
    const value = Number(input.value);
    return Number.isFinite(value) && value >= 1 ? Math.floor(value) : 3;
}

function updateWorkersVisibility() {
    const control = document.getElementById('workers-control');
    const select = document.getElementById('mode');
    if (!control || !select) return;
    control.hidden = select.value === 'sequential';
}

const form = document.getElementById('watch-form');
const startButton = document.getElementById('start-watch');
const stopButton = document.getElementById('stop-watch');
const timestampInput = document.getElementById('timestamp');
const statusMessage = document.getElementById('status-message');

const fields = {
    state: document.getElementById('watch-state'),
    run: document.getElementById('watch-run'),
    directory: document.getElementById('watch-directory'),
    mode: document.getElementById('watch-mode'),
    workers: document.getElementById('watch-workers'),
    timestamp: document.getElementById('watch-timestamp'),
    started: document.getElementById('watch-started'),
    ended: document.getElementById('watch-ended'),
    rc: document.getElementById('watch-rc'),
    cycles: document.getElementById('watch-cycles'),
};

let pollTimer = null;

function setStatus(message, type) {
    statusMessage.textContent = message;
    statusMessage.className = type || '';
}

function showState(data) {
    const running = Boolean(data.running);
    fields.state.textContent = running
        ? (data.stop_requested ? 'Stopping…' : 'Running')
        : 'Idle';
    fields.state.className = running ? 'running' : 'stopped';
    fields.run.textContent = data.run_id || data.last_run_id || '—';
    fields.directory.textContent = data.directory || '—';
    fields.mode.textContent = data.mode || '—';
    fields.workers.textContent = data.workers == null ? '—' : String(data.workers);
    fields.timestamp.textContent = data.timestamp == null ? '—' : (data.timestamp + ' s');
    fields.started.textContent = data.started_at || '—';
    fields.ended.textContent = data.ended_at || '—';
    fields.rc.textContent = data.last_rc == null ? '—' : String(data.last_rc);
    fields.cycles.textContent = data.cycles == null ? '—' : String(data.cycles);
    renderResults(data.last_result || {});

    startButton.disabled = running;
    stopButton.disabled = !running;
    if (!running && pollTimer !== null) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

async function pollStatus() {
    try {
        showState(await requestJSON('/verification_temp/status'));
    } catch (error) {
        setStatus(error.message, 'error');
    }
}

form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const directory = document.getElementById('directory').value.trim();
    const mode = document.getElementById('mode').value;
    const seconds = Number(timestampInput.value);
    const workers = readWorkers();
    if (!directory) {
        setStatus('Please enter a directory path first.', 'error');
        return;
    }
    if (!Number.isFinite(seconds) || seconds <= 0) {
        setStatus('Timestamp must be a positive number of seconds.', 'error');
        return;
    }

    startButton.disabled = true;
    setStatus('Starting the periodic check…');
    try {
        const result = await requestJSON('/verification_temp/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ directory: directory, scanMode: mode, timestamp: seconds, workers: workers }),
        });
        setStatus('Watcher started (run ' + result.run_id + ', every ' + result.timestamp + ' s).', 'success');
        await pollStatus();
        if (pollTimer === null) pollTimer = setInterval(pollStatus, 2000);
    } catch (error) {
        setStatus(error.message, 'error');
        await pollStatus();
    } finally {
        if (!pollTimer) startButton.disabled = false;
    }
});

stopButton.addEventListener('click', async () => {
    stopButton.disabled = true;
    setStatus('Stopping the watcher…');
    try {
        await requestJSON('/verification_temp/stop', { method: 'POST' });
        setStatus('Stop requested. The cycle will finish before exiting.', 'success');
        await pollStatus();
    } catch (error) {
        setStatus(error.message, 'error');
    } finally {
        if (pollTimer) stopButton.disabled = false;
    }
});

const uiState = document.getElementById('ui-state');
if (uiState) uiState.textContent = 'JavaScript actif — résultats prêts';
updateWorkersVisibility();
document.getElementById('mode').addEventListener('change', updateWorkersVisibility);
pollStatus();


// Hamburger sidebar (present on both pages).
function setupSidebar() {
    const toggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (!toggle || !sidebar || !backdrop) return;

    function setOpen(open) {
        sidebar.classList.toggle('open', open);
        backdrop.hidden = !open;
        toggle.setAttribute('aria-expanded', String(open));
        toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    }
    toggle.addEventListener('click', () => setOpen(!sidebar.classList.contains('open')));
    backdrop.addEventListener('click', () => setOpen(false));

    const current = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach((link) => {
        const target = new URL(link.href, window.location.origin).pathname;
        if (target === current) link.classList.add('active');
    });
}
setupSidebar();

    
