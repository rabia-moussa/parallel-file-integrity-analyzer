// Quand la page est servie par Flask (port 5000), on reste en relatif.
// Quand elle est servie par Live Server (5500), on appelle Flask en absolu.
const API_BASE = window.location.port === "5000" ? "" : "http://127.0.0.1:5000";

async function requestJSON(path, options) {
    const response = await fetch(`${API_BASE}${path}`, options);
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        const error = new Error(data.error || `HTTP ${response.status}`);
        error.status = response.status;
        error.data = data;
        throw error;
    }
    return data;
}

async function runCheck(path, mode = 'sequential', workers = 3) {
    return requestJSON('/scan', {
        method: 'POST',
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ directory: path, scanMode: mode, workers: workers }),
    });
}

async function Firstrun(path, mode = 'sequential', workers = 3) {
    return requestJSON('/baseline', {
        method: 'POST',
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ directory: path, scanMode: mode, workers: workers }),
    });
}


function plural(count, singular, pluralForm) {
    return count === 1 ? singular : pluralForm;
}

// Renders one flat result section (an array of file paths).
// countId is the badge next to the static <h2>; listId is the <ul>.
function renderFileList(countId, listId, items) {
    const count = document.getElementById(countId);
    const list = document.getElementById(listId);
    items = Array.isArray(items) ? items : [];

    if (count) {
        count.textContent = items.length === 0
            ? "none"
            : `${items.length} ${plural(items.length, "file", "files")}`;
    }
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


// Renders the duplicates section, which is a { hash: [paths] } dictionary
// and therefore needs a nested group -> files structure.
function renderDuplicates(countId, listId, duplicates) {
    const count = document.getElementById(countId);
    const list = document.getElementById(listId);
    const groups = duplicates && typeof duplicates === "object"
        ? Object.entries(duplicates)
        : [];

    if (count) {
        count.textContent = groups.length === 0
            ? "none"
            : `${groups.length} ${plural(groups.length, "group", "groups")}`;
    }
    list.innerHTML = "";

    if (groups.length === 0) {
        const empty = document.createElement("li");
        empty.className = "empty";
        empty.textContent = "None";
        list.appendChild(empty);
        return;
    }

    for (const [hash, files] of groups) {
        const group = document.createElement("li");

        const header = document.createElement("strong");
        header.textContent = `Hash: ${hash.slice(0, 16)}…`;
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


// Principal renderer. Takes the source of information as an argument and
// awaits it inside, so the same function is used for a normal scan and a
// periodic scan (pass the promise / value produced by either one).
async function renderResults(source) {
    const result = await source;
    const data = result || {};

    renderFileList(
        "permission-denied-title",
        "permission-denied-list",
        data.permission_denied
    );
    renderFileList(
        "modified-files-title",
        "modified-files-list",
        data.modified
    );
    renderFileList(
        "new-files-title",
        "new-files-list",
        data.new
    );
    renderFileList(
        "deleted-files-title",
        "deleted-files-list",
        data.deleted
    );
    renderDuplicates(
        "duplicate-files-title",
        "duplicate-files-list",
        data.duplicates
    );
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

const form = document.querySelector('form');
const firstRunButton = document.getElementById('first-run');
const submitButton = form.querySelector('button[type="submit"]');
const stopButton = document.getElementById('stop-scan');
const statusMessage = document.getElementById('status-message');

const resultError = document.getElementById('result-error');

function setStatus(message, type = '') {
    if (!statusMessage) return;
    statusMessage.textContent = message;
    statusMessage.className = type;
}

function showResultError(message) {
    if (!resultError) return;
    resultError.textContent = message;
    resultError.hidden = false;
}

function clearResultError() {
    if (!resultError) return;
    resultError.textContent = '';
    resultError.hidden = true;
}

form.addEventListener('submit', async (event) => {
    event.preventDefault();

    const directoryPath = document.getElementById('directory').value.trim();
    const mode = document.getElementById('mode').value;
    const workers = readWorkers();

    if (!directoryPath) {
        setStatus('Please enter a directory path first.', 'error');
        return;
    }

    submitButton.disabled = true;
    setStatus('Scanning... this can take several minutes.');

    try {
        clearResultError();
        const result = await runCheck(directoryPath, mode, workers);
        await renderResults(result);

        if (result.complete === false) {
            const pending = Array.isArray(result.unprocessed) ? result.unprocessed.length : 0;
            setStatus(`Scan incomplete: ${pending} file(s) not processed.`, 'error');
            showResultError(`Scan incomplete: ${pending} file(s) not processed.`);
        } else {
            setStatus(`Scan complete (${result.mode}).`, 'success');
        }
    } catch (error) {
        // Meme en cas d'erreur, on remplit les sections avec ce que le serveur
        // a renvoye (ou avec des listes vides) pour ne jamais laisser la zone
        // de resultats completement blanche.
        await renderResults(error.data || {});
        setStatus(error.message, 'error');
        showResultError(error.message);
    } finally {
        submitButton.disabled = false;
    }
});

firstRunButton.addEventListener('click', async () => {
    const directoryPath = document.getElementById('directory').value.trim();
    const mode = document.getElementById('mode').value;
    const workers = readWorkers();

    if (!directoryPath) {
        setStatus('Please enter a directory path first.', 'error');
        return;
    }

    firstRunButton.disabled = true;
    setStatus('Creating the baseline...');

    try {
        clearResultError();
        const result = await Firstrun(directoryPath, mode, workers);
        setStatus(
            `Baseline created for ${result.directory || directoryPath} (${result.mode || mode}, ${result.entries} entries).`,
            'success'
        );
    } catch (error) {
        setStatus(error.message, 'error');
        showResultError(error.message);
    } finally {
        firstRunButton.disabled = false;
    }
});

if (stopButton) {
    stopButton.addEventListener('click', async () => {
        try {
            const data = await requestJSON('/stop', { method: 'POST' });
            setStatus(data.status === 'stopping' ? 'Stopping the current scan...' : 'No scan is running.');
        } catch (error) {
            setStatus(error.message, 'error');
            showResultError(error.message);
        }
    });
}

updateWorkersVisibility();
document.getElementById('mode').addEventListener('change', updateWorkersVisibility);

// Etat initial : les cinq sections affichent "None" des le chargement.
const uiState = document.getElementById('ui-state');
if (uiState) uiState.textContent = 'JavaScript actif — résultats prêts';
renderResults({});
