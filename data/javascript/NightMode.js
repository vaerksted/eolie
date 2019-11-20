var observer = new MutationObserver(subscriber);
var config = { childList: true, subtree: true };
var handled_css_uri = {}
var handled_css_content = []
var xhr_running = 0

function getURL(url) {
    try {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", url, true);
        xhr.onreadystatechange = function () {
            if(xhr.readyState === 4 && xhr.status === 200) {
                injectStyleSheet(xhr.responseText);
            }
        };
        xhr.send();
    }
    catch(error) {
        console.log(error);
    }
}

function setStyle(e) {
    e.style.background =  "none";
    e.style.backgroundImage = "none";
    e.style.backgroundColor = "#353535";
}

// color as str rgb(r, g, b) or white/black/...
function shouldTransformColor(color) {
    match = color.match(/rgba?\((\d{1,3}), ?(\d{1,3}), ?(\d{1,3})\)?(?:, ?(\d(?:\.\d?))\))?/);
    if (match === null) {
        return color == "white" || color == "black" || color.startsWith("var(");
    }
    rgb = [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])];
    rgb_ratio1 = (rgb[0] + 0.1) / (rgb[1] + 0.1);
    rgb_ratio2 = (rgb[1] + 0.1) / (rgb[1] + 0.1);
    greyscale = rgb_ratio1 > 0.8 && rgb_ratio1 < 1.2 && rgb_ratio2 > 0.8 && rgb_ratio2 < 1.2
    //console.log(greyscale + " / " + rgb);
    return greyscale || (rgb[0] + rgb[1] + rgb[2]) / 3 < 100;
}

function injectStyleSheet(css) {
    let s = document.createElement("style");
    s.setAttribute('type', 'text/css');
    s.appendChild(document.createTextNode(css));
    document.head.appendChild(s)
    xhr_running --;
    if (xhr_running == 0 ) {
        body = document.querySelector("body");
        body.style.display = "block";
    }
}

function setRules(style) {
    try {
        rules = Array.from(style.cssRules);

        // Style already handled and same rules length
        if (style.href === null) {
            if (handled_css_content.includes(style.ownerNode.innerText)) {
                return;
            }
            handled_css_content.push(style.ownerNode.innerText);
        }
        else {
            if (style.href in handled_css_uri) {
                if (handled_css_uri[style.href] === rules.length) {
                    return;
                }
            }
            handled_css_uri[style.href] = rules.length;
        }

        while (rules.length > 0) {
            rule = rules.pop();
            //console.log(rule);
            if (rule.type === CSSRule.MEDIA_RULE) {
                rules = rules.concat(Array.from(rule.cssRules));
                continue;
            }
            else if (rule.style === undefined) {
                continue;
            }
            background_color = rule.style.getPropertyValue("background-color");
            background = rule.style.getPropertyValue("background");
            color = rule.style.getPropertyValue("color");
            background_updated = false;
            if (background_color !== "" && shouldTransformColor(background_color)) {
                rule.style.setProperty("background-color", "#353535", "important");
            }
            if (background !== "" && shouldTransformColor(background)) {
                rule.style.setProperty("background", "#353535", "important");
            }
            if (color !== "") {
                if (shouldTransformColor(color)) {
                    rule.style.setProperty("color", "#EAEAEA", "important");
                }
                else {
                    rule.style.setProperty("filter", "brightness(1.25)", "important");
                }
            }
        }
    }
    catch(error) {
        console.log(error);
        // CORS disallowed, get by hand
        getURL(style.href);
        style.disabled = true;
        body = document.querySelector("body");
        body.style.display = "none";
        xhr_running++;
    }
}

function setStyleCheets() {
    for(let i=0; i<document.styleSheets.length; i++) {
        style = document.styleSheets[i]
        if (style.disabled === false) {
            setRules(style);
        }
    }  
}

function subscriber(mutations) {
    setStyleCheets()
}

function addStyleString(str) {
    var node = document.createElement('style');
    node.innerHTML = str;
    document.body.appendChild(node);
}

if (document.body !== null) {
    addStyleString("*[style] {color: #EAEAEA !important; background-color: #353535 !important; background: none !important}");
}
head = document.querySelector("head");
observer.observe(head, config);
setStyleCheets();
window.addEventListener("DOMContentLoaded", (event) => {
    addStyleString("*[style] {color: #EAEAEA !important; background-color: #353535 !important; background: none !important}");
    setStyleCheets();
});
