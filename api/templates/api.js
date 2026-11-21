async function runCheck(path, mode = 'sequential') {
    try {
        const response = await fetch('http://127.0.0.1:5000/scan' 
            
            , {method:'POST' , headers: { "Content-Type": "application/json" },body : JSON.stringify({directory: path , scanMode : mode}) } );
        return response.json();

        }
    catch (error) {
        console.error('Error running check:', error);
    }

}

async function Firstrun(path , mode='sequentiel') {
    try {
        const response = await fetch('http://127.0.0.1:5000/First_run'
        , {method: 'POST' ,header : { "Content-Type": "application/json" } 
        , body : JSON.stringify({directory:path , scanMode : mode})
     }
        )
    }
    catch (error) {
        console.error('Error running check:', error);
    }
    
}


// Renders one flat result section (an array of file paths).
// titleId / listId are the ids of the <h2> and <ul> already present in home.html.
function renderFileList(titleId, listId, label, items) {
    const title = document.getElementById(titleId);
    const list = document.getElementById(listId);
    items = Array.isArray(items) ? items : [];

    title.textContent = `${label} (${items.length})`;
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
function renderDuplicates(titleId, listId, label, duplicates) {
    const title = document.getElementById(titleId);
    const list = document.getElementById(listId);
    const groups = duplicates && typeof duplicates === "object"
        ? Object.entries(duplicates)
        : [];

    title.textContent = `${label} (${groups.length} groups)`;
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
        header.textContent = `Hash: ${hash}`;
        group.appendChild(header);

        const fileList = document.createElement("ul");
        (Array.isArray(files) ? files : []).forEach((file, index) => {
            const item = document.createElement("li");
            item.textContent = `File ${index + 1}: ${file}`;
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

    renderFileList(
        "permission-denied-title",
        "permission-denied-list",
        "Permission Denied Files",
        result?.permission_denied
    );
    renderFileList(
        "modified-files-title",
        "modified-files-list",
        "Modified Files",
        result?.modified
    );
    renderFileList(
        "new-files-title",
        "new-files-list",
        "New Files",
        result?.new
    );
    renderFileList(
        "deleted-files-title",
        "deleted-files-list",
        "Deleted Files",
        result?.deleted
    );
    renderDuplicates(
        "duplicate-files-title",
        "duplicate-files-list",
        "Duplicate Files",
        result?.duplicates
    );
}


const form = document.querySelector('form');

form.addEventListener('submit', async (event) => {
    event.preventDefault()
    const directoryInput = document.getElementById('directory');
    const directoryPath = directoryInput.value
    const mode = document.getElementById('mode').value;
    await renderResults(runCheck(directoryPath, mode))
})
