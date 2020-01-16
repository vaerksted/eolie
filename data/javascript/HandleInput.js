var observer = new MutationObserver(subscriber);
var config = { childList: true, subtree: true };
var back_history = {};
var fwd_history = {};

function handleTextareas(textareas) {
    for(let i=0; i<textareas.length; i++) {
        let textarea = textareas[i];
        back_history[textarea] = [];
        fwd_history[textarea] = [];
        textarea.addEventListener('input', function() {handleInput(textarea);}, true);
    }
}

function handleInput(textarea) {
    let value = textarea.value
    let is_space = value[value.length -1] == " ";
    if (is_space) {
        back_history[textarea].push(value);
    }
}

function subscriber(mutations) {
    let addedNodesLength = mutationRecord.addedNodes.length;
    let textareas = [];
    for (let i = 0; i < addedNodesLength; i++) {
        element = mutationRecord.addedNodes[i];
        if (element.tagName.toLowerCase() == 'textarea') {
            textareas.push(element);
        }
    }
    handleTextareas(textareas);
}

html = document.querySelector("html");
textareas = document.getElementsByTagName('textarea')
handleTextareas(textareas);
observer.observe(html, config);
