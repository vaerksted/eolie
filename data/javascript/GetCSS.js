var observer = new MutationObserver(subscriber);
var config = {  attributes : true, attributeFilter : ['style'] };

function getCSS() {
    if (document.styleSheets.length == 0) {
        alert("@EOLIE_CSS_TEXT@");
        return;
    }
    for(let i=0; i<document.styleSheets.length; i++) {
        let css_text = "";
        style = document.styleSheets[i]
        if (style.disabled == false) {
            if (style.href === null) {
                for(var item in style.cssRules) {    
                    rules = style.cssRules[item]
                    if(rules.cssText != undefined)
                        css_text = css_text + rules.cssText;
                    }
                alert("@EOLIE_CSS_TEXT@" + css_text)
            }
            else {
                alert("@EOLIE_CSS_URI@" + style.href)
            }
        }
    }
}

function subscriber(mutations) {
    getCSS()
}

getCSS();
window.addEventListener("DOMContentLoaded", (event) => {
    getCSS();
    head = document.querySelector("head");
    observer.observe(head, config);
});
