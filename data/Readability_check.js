
if (typeof document !== 'undefined') {
    reader = new Readability(uri, document);
    if (reader.isProbablyReaderable(false)) {
        var previous_title = document.title;
        alert("@EOLIE_READERABLE@");
        document.title=previous_title;
    }
}
