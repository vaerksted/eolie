
if (typeof document !== 'undefined') {
    var documentClone = document.cloneNode(true);
    reader = new Readability(uri, documentClone);
    article = reader.parse();
    var previous_title = document.title;
    alert("@EOLIE_READER@".concat(article.content));
    document.title=previous_title;
}
