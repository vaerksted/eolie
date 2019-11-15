var selection = "";
if (window.getSelection) {
    selection = window.getSelection().toString();
} else if (document.selection && document.selection.type != "Control") {
    selection = document.selection.createRange().text;
}
selection;
