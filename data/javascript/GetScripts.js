var uris="";
scripts = document.getElementsByTagName("script");
for(let i=0; i<scripts.length; i++) {
    let src = scripts[i].src;
    if (!src) continue;
    uris += "@@@" + src
}
uris;
