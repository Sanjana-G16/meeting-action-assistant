const transcriptField = document.querySelector("#transcript");
const characterCount = document.querySelector("#character-count");
const loadDemoButton = document.querySelector("#load-demo");
const clearButton = document.querySelector("#clear-transcript");

if (transcriptField && characterCount) {
    const updateCharacterCount = () => {
        characterCount.textContent = `${transcriptField.value.length.toLocaleString()} characters`;
    };
    transcriptField.addEventListener("input", updateCharacterCount);
    updateCharacterCount();
}

if (transcriptField && loadDemoButton) {
    loadDemoButton.addEventListener("click", () => {
        transcriptField.value = loadDemoButton.dataset.transcript || "";
        transcriptField.dispatchEvent(new Event("input"));
        transcriptField.focus();
    });
}

if (transcriptField && clearButton) {
    clearButton.addEventListener("click", () => {
        transcriptField.value = "";
        transcriptField.dispatchEvent(new Event("input"));
        transcriptField.focus();
    });
}

document.querySelectorAll(".delete-form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
        if (!window.confirm(form.dataset.confirm)) {
            event.preventDefault();
        }
    });
});
