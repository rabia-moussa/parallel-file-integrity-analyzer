async function runCheck(path) {
    try {
        const response = await fetch('http://127.0.0.1:5000/scan' 
            
            , {method:'POST' , headers: { "Content-Type": "application/json" },body : JSON.stringify({directory: path}) } );
        return response.json();

        }
    catch (error) {
        console.error('Error running check:', error);
    }

}
   

const form = document.querySelector('form');

form.addEventListener('submit', async (event) => {
    event.preventDefault()
    const directoryInput = document.getElementById('directory');
    const directoryPath = directoryInput.value
    result = await runCheck(directoryPath)
    // Display the permission denied files and their count in the HTML
    document.getElementById('permission-denied-title').textContent = 'Permission Denied Files are around '
    + result.counts.permission_denied;
    const permissionDeniedList = document.getElementById('permission-denied-list');
    permissionDeniedList.innerHTML = ''; 
    result.permission_denied.forEach(file => {
        const item = document.createElement('li');
        item.textContent = file;
        permissionDeniedList.appendChild(item); })

    // Display the modified files and their count in the HTML
    document.getElementById('modified-files-title').textContent = 'Permission Denied Files are around '
    + result.counts.modified;
    const modified = document.getElementById('modified-files-list');
    modified.innerHTML = ''; 
    result.modified.forEach(file => {
        const item = document.createElement('li');
        item.textContent = file;
        modified.appendChild(item); })       
    
        // Display the  new files and their count in the HTML
    document.getElementById('new-files-title').textContent = 'new Files are around '
    + result.counts.new;
    const new_files = document.getElementById('new-files-list');
    new_files.innerHTML = ''; 
    result.new.forEach(file => {
        const item = document.createElement('li');
        item.textContent = file;
        new_files.appendChild(item); })
    
      // Display the  deleted files and their count in the HTML
    document.getElementById('deleted-files-title').textContent = 'deleted Files are around '
    + result.counts.deleted;
    const deleted = document.getElementById('deleted-files-list');
    deleted.innerHTML = ''; 
    result.deleted.forEach(file => {
        const item = document.createElement('li');
        item.textContent = file;
        deleted.appendChild(item); })



    // display the duplicate files and their count in the HTML 
    document.getElementById('duplicate-files-title').textContent =
      'Duplicate Files are around ' + result.counts.duplicate_groups ;

      const duplicateFilesList = document.getElementById('duplicate-files-list');
      duplicateFilesList.innerHTML = '';

      for (const [hash, files] of Object.entries(result.duplicates)) {
        const item=document.createElement('ul');
        item.textContent = `group : Hash: ${hash}`;
        let count = 0 ;
        files.forEach(file =>{
            count ++;
            const fileItem=document.createElement('li');
            fileItem.textContent=`file ${count} :${file}`;
            item.appendChild(fileItem);
      })
        duplicateFilesList.appendChild(item);

      }
      })  
   
    
    
    
    

