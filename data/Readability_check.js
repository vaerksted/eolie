
if (typeof document !== 'undefined') {
    if (isProbablyReaderable(document, false)) {
        var previous_title = document.title;
        alert("@EOLIE_READERABLE@");
        document.title=previous_title;
    }
}
