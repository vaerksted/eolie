if (document.activeElement.tagName.toLowerCase() == 'textarea') {
    value = fwd_history[document.activeElement].pop(-1);
    if (value != undefined) {
        back_history[document.activeElement].push(document.activeElement.value);
        document.activeElement.value = value;
    }
}
