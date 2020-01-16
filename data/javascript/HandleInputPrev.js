if (document.activeElement.tagName.toLowerCase() == 'textarea' && document.activeElement.value !== '') {
    fwd_history[document.activeElement].push(document.activeElement.value);
    value = back_history[document.activeElement].pop(-1);
    if (value == undefined) {
        document.activeElement.value = '';
    }
    else {
        document.activeElement.value = value;
    }
}
