var observer = new MutationObserver(subscriber);
var config = { childList: true, subtree: true };

function getCSS() {
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
head = document.querySelector("head");
observer.observe(head, config);
window.addEventListener("DOMContentLoaded", (event) => {
    getCSS();
});
