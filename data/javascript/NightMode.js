var observer = new MutationObserver(subscriber);
var config = { childList: true, subtree: true };
var handled_css = {};
var xhr_running = 0;

function setStyle(e) {
    e.style.background =  "none";
    e.style.backgroundImage = "none";
    e.style.backgroundColor = "#353535";
}

function getRGB(color) {
    match = color.match(/rgba?\((\d{1,3}), ?(\d{1,3}), ?(\d{1,3})\)?(?:, ?(\d(?:\.\d?))\))?/);
    if (match === null) {
        return null;
    }
    else {
        return [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])];
    }
}

// color as str rgb(r, g, b) or white/black/...
function shouldTransformColor(rgb, color) {
    if (rgb === null) {
        return color == "white" || color == "black" || color == "inherit" || color.startsWith("var(");
    }
    rgb_ratio1 = (rgb[0] + 0.1) / (rgb[1] + 0.1);
    rgb_ratio2 = (rgb[1] + 0.1) / (rgb[1] + 0.1);
    greyscale = rgb_ratio1 > 0.8 && rgb_ratio1 < 1.2 && rgb_ratio2 > 0.8 && rgb_ratio2 < 1.2
    return greyscale || (rgb[0] + rgb[1] + rgb[2]) / 3 < 100;
}

function isMediaScreen(media) {
    if (media.length == 0) {
        return true;
    }
    for (let i=0; i < media.length; i++) {
        if (media[i] == "screen" || media[i] == "all") {
            return true;
        }
    }
    return false;
}

function setRules(styles) {
    let i = 0
    while (styles.length > 0) {
        style = styles.pop();
        try {
            // CSS is not valid for screen
            if (style.media !== null && !isMediaScreen(style.media)) {
                i++;
                continue
            }
            // Raise exception if rules no accessible (CORS)
            // See catch
            rules = Array.from(style.cssRules);
            // Do not read CSS if already set for this length
            if (i in handled_css) {
                if (handled_css[i] === rules.length) {
                    i++;
                    continue;
                }
            }
            handled_css[i] = rules.length;
            i++;
            // Load rules
            while (rules.length > 0) {
                rule = rules.pop();
                //console.log(rule);
                if (rule.type === CSSRule.MEDIA_RULE) {
                    rules = rules.concat(Array.from(rule.cssRules));
                    continue;
                }
                else if (rule.type === CSSRule.IMPORT_RULE) {
                    if (rule.styleSheet !== null && rule.styleSheet.disabled == false) {
                        styles.push(rule.styleSheet);
                    }
                    continue;
                }
                else if (rule.style === undefined) {
                    continue;
                }
                background_color = rule.style.getPropertyValue("background-color");
                background = rule.style.getPropertyValue("background");
                color = rule.style.getPropertyValue("color");
                background_color_rgb = getRGB(background_color);
                background_rgb = getRGB(background);
                color_rgb = getRGB(color);
                background_updated = false;
                if (background_color !== "" && shouldTransformColor(background_color_rgb, background_color)) {
                    rule.style.setProperty("background-color", "#353535", "important");
                }
                if (background !== "" && shouldTransformColor(background_rgb, background)) {
                    rule.style.setProperty("background", "#353535", "important");
                }
                if (color !== "") {
                    if (shouldTransformColor(color_rgb, color)) {
                        rule.style.setProperty("color", "#EAEAEA", "important");
                    }
                    else {
                        rule.style.setProperty("filter", "brightness(1.5)", "important");
                    }
                }
            }
        }
        catch(error) {
            console.log(error, style.href);
            style.disabled = true;
            html = document.querySelector("html");
            if (html !== null) {
                html.style.display = "none";
            }
            xhr_running++;
            alert("@EOLIE_CSS_URI@" + style.href)
        }
    }
}

function setStyleCheets() {
    styles = [];
    for(let i=0; i<document.styleSheets.length; i++) {
        style = document.styleSheets[i]
        if (style.disabled == false) {
            styles.push(style)
        }
    }
    setRules(styles);
}

function subscriber(mutations) {
    setStyleCheets()
}

head = document.querySelector("head");
observer.observe(head, config);
window.addEventListener("DOMContentLoaded", (event) => {
    setStyleCheets();
});
window.addEventListener("load", (event) => {
    setStyleCheets();
});