var observer = new MutationObserver(subscriber);
var config = { childList: true, subtree: true };
var handled_css = {};

function string2RGB(color) {
    colors = {
      "aliceblue": [240, 248, 255],
      "antiquewhite": [250, 235, 215],
      "aqua": [0, 255, 255],
      "aquamarine": [127, 255, 212],
      "azure": [240, 255, 255],
      "beige": [245, 245, 220],
      "bisque": [255, 228, 196],
      "black": [0, 0, 0],
      "blanchedalmond": [255, 235, 205],
      "blue": [0, 0, 255],
      "blueviolet": [138, 43, 226],
      "brown": [165, 42, 42],
      "burlywood": [222, 184, 135],
      "cadetblue": [95, 158, 160],
      "chartreuse": [127, 255, 0],
      "chocolate": [210, 105, 30],
      "coral": [255, 127, 80],
      "cornflowerblue": [100, 149, 237],
      "cornsilk": [255, 248, 220],
      "crimson": [220, 20, 60],
      "cyan": [0, 255, 255],
      "darkblue": [0, 0, 139],
      "darkcyan": [0, 139, 139],
      "darkgoldenrod": [184, 134, 11],
      "darkgray": [169, 169, 169],
      "darkgreen": [0, 100, 0],
      "darkgrey": [169, 169, 169],
      "darkkhaki": [189, 183, 107],
      "darkmagenta": [139, 0, 139],
      "darkolivegreen": [85, 107, 47],
      "darkorange": [255, 140, 0],
      "darkorchid": [153, 50, 204],
      "darkred": [139, 0, 0],
      "darksalmon": [233, 150, 122],
      "darkseagreen": [143, 188, 143],
      "darkslateblue": [72, 61, 139],
      "darkslategray": [47, 79, 79],
      "darkslategrey": [47, 79, 79],
      "darkturquoise": [0, 206, 209],
      "darkviolet": [148, 0, 211],
      "deeppink": [255, 20, 147],
      "deepskyblue": [0, 191, 255],
      "dimgray": [105, 105, 105],
      "dimgrey": [105, 105, 105],
      "dodgerblue": [30, 144, 255],
      "firebrick": [178, 34, 34],
      "floralwhite": [255, 250, 240],
      "forestgreen": [34, 139, 34],
      "fuchsia": [255, 0, 255],
      "gainsboro": [220, 220, 220],
      "ghostwhite": [248, 248, 255],
      "gold": [255, 215, 0],
      "goldenrod": [218, 165, 32],
      "gray": [128, 128, 128],
      "green": [0, 128, 0],
      "greenyellow": [173, 255, 47],
      "grey": [128, 128, 128],
      "honeydew": [240, 255, 240],
      "hotpink": [255, 105, 180],
      "indianred": [205, 92, 92],
      "indigo": [75, 0, 130],
      "ivory": [255, 255, 240],
      "khaki": [240, 230, 140],
      "lavender": [230, 230, 250],
      "lavenderblush": [255, 240, 245],
      "lawngreen": [124, 252, 0],
      "lemonchiffon": [255, 250, 205],
      "lightblue": [173, 216, 230],
      "lightcoral": [240, 128, 128],
      "lightcyan": [224, 255, 255],
      "lightgoldenrodyellow": [250, 250, 210],
      "lightgray": [211, 211, 211],
      "lightgreen": [144, 238, 144],
      "lightgrey": [211, 211, 211],
      "lightpink": [255, 182, 193],
      "lightsalmon": [255, 160, 122],
      "lightseagreen": [32, 178, 170],
      "lightskyblue": [135, 206, 250],
      "lightslategray": [119, 136, 153],
      "lightslategrey": [119, 136, 153],
      "lightsteelblue": [176, 196, 222],
      "lightyellow": [255, 255, 224],
      "lime": [0, 255, 0],
      "limegreen": [50, 205, 50],
      "linen": [250, 240, 230],
      "magenta": [255, 0, 255],
      "maroon": [128, 0, 0],
      "mediumaquamarine": [102, 205, 170],
      "mediumblue": [0, 0, 205],
      "mediumorchid": [186, 85, 211],
      "mediumpurple": [147, 112, 216],
      "mediumseagreen": [60, 179, 113],
      "mediumslateblue": [123, 104, 238],
      "mediumspringgreen": [0, 250, 154],
      "mediumturquoise": [72, 209, 204],
      "mediumvioletred": [199, 21, 133],
      "midnightblue": [25, 25, 112],
      "mintcream": [245, 255, 250],
      "mistyrose": [255, 228, 225],
      "moccasin": [255, 228, 181],
      "navajowhite": [255, 222, 173],
      "navy": [0, 0, 128],
      "oldlace": [253, 245, 230],
      "olive": [128, 128, 0],
      "olivedrab": [107, 142, 35],
      "orange": [255, 165, 0],
      "orangered": [255, 69, 0],
      "orchid": [218, 112, 214],
      "palegoldenrod": [238, 232, 170],
      "palegreen": [152, 251, 152],
      "paleturquoise": [175, 238, 238],
      "palevioletred": [216, 112, 147],
      "papayawhip": [255, 239, 213],
      "peachpuff": [255, 218, 185],
      "peru": [205, 133, 63],
      "pink": [255, 192, 203],
      "plum": [221, 160, 221],
      "powderblue": [176, 224, 230],
      "purple": [128, 0, 128],
      "red": [255, 0, 0],
      "rosybrown": [188, 143, 143],
      "royalblue": [65, 105, 225],
      "saddlebrown": [139, 69, 19],
      "salmon": [250, 128, 114],
      "sandybrown": [244, 164, 96],
      "seagreen": [46, 139, 87],
      "seashell": [255, 245, 238],
      "sienna": [160, 82, 45],
      "silver": [192, 192, 192],
      "skyblue": [135, 206, 235],
      "slateblue": [106, 90, 205],
      "slategray": [112, 128, 144],
      "slategrey": [112, 128, 144],
      "snow": [255, 250, 250],
      "springgreen": [0, 255, 127],
      "steelblue": [70, 130, 180],
      "tan": [210, 180, 140],
      "teal": [0, 128, 128],
      "thistle": [216, 191, 216],
      "tomato": [255, 99, 71],
      "turquoise": [64, 224, 208],
      "violet": [238, 130, 238],
      "wheat": [245, 222, 179],
      "white": [255, 255, 255],
      "whitesmoke": [245, 245, 245],
      "yellow": [255, 255, 0],
      "yellowgreen": [154, 205, 50]
    }
    return colors[color];
}

function getRGB(color) {
    match = color.match(/rgba?\((\d{1,3}), ?(\d{1,3}), ?(\d{1,3})\)?(?:, ?(\d(?:\.\d?))\))?/);
    if (match === null) {
        rgb = string2RGB(color);
        if (rgb === undefined) {
        }
        else {
            return [rgb[0], rgb[1], rgb[2], 1];
        }
        
    }
    else {
        return [parseInt(match[1]), parseInt(match[2]), parseInt(match[3]), 1];
    }
}

function shoulIgnoreColor(color) {
    values = ["inherit", "transparent", "none"];
    for (let i in values) {
        if (color.startsWith(values[i])) {
            return true
        }
    }
    return false;
}

function shouldOverrideColor(color) {
    values = ["initial", "var(", "url(", "linear-", "radial-"];
    for (let i in values) {
        if (color.startsWith(values[i])) {
            return true
        }
    }
    return false;
}

function isGrayscaleColor(rgb) {
    rgb_ratio1 = (rgb[0] + 0.1) / (rgb[1] + 0.1);
    rgb_ratio2 = (rgb[1] + 0.1) / (rgb[1] + 0.1);
    greyscale = rgb_ratio1 > 0.8 && rgb_ratio1 < 1.2 && rgb_ratio2 > 0.8 && rgb_ratio2 < 1.2
    return greyscale
}

function isDarkColor(rgb) {
    return (rgb[0] + rgb[1] + rgb[2]) / 3 < 100;
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

function colorBrightness(rgb, diff) {
    r = Math.min(255, Math.max(0, rgb[0] + diff));
    g = Math.min(255, Math.max(0, rgb[1] + diff));
    b  = Math.min(255, Math.max(0, rgb[2] + diff));
    a = rgb[3]
    return "rgba("  + r + "," + g + "," + b + "," + a +")"
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
                if (background_color !== "" && !shoulIgnoreColor(background_color)) {
                    set_color = shouldOverrideColor(background_color)
                    let rgb = null;
                    if (set_color == false) {
                        rgb = getRGB(background_color);
                        set_color = isGrayscaleColor(rgb) || isDarkColor(rgb);
                    }
                    if (set_color == true) {
                        rule.style.setProperty("background-color", "#353535", "important");
                    }
                    else {
                        if (rgb == null) {
                            rgb = getRGB(background_color);
                        }
                        rgb_str = colorBrightness(rgb, -50);
                        rule.style.setProperty("background-color", rgb_str, "important");
                    }
                }
                if (background !== "" && !shoulIgnoreColor(background)) {
                    set_color = shouldOverrideColor(background)
                    let rgb = null;
                    if (set_color == false) {
                        rgb = getRGB(background);
                        set_color = isGrayscaleColor(rgb) || isDarkColor(rgb);
                    }
                    if (set_color == true) {
                        rule.style.setProperty("background", "#353535", "important");
                    }
                    else {
                        if (rgb == null) {
                            rgb = getRGB(background);
                        }
                        rgb_str = colorBrightness(rgb, -50);
                        rule.style.setProperty("background", rgb_str, "important");
                    }
                }
                if (color !== "" && !shoulIgnoreColor(color)) {
                    if (shouldOverrideColor(color)) {
                        rule.style.setProperty("color", "#EAEAEA", "important");
                        continue;
                    }
                    rgb = getRGB(color);
                    if (isGrayscaleColor(rgb)) {
                        rule.style.setProperty("color", "#EAEAEA", "important");
                    }
                    else if (isDarkColor(rgb)) {
                        rgb_str = colorBrightness(rgb, -100);
                        rule.style.setProperty("color", rgb_str, "important");
                    }
                    else {
                        rgb_str = colorBrightness(rgb, 100);
                        rule.style.setProperty("color", rgb_str, "important");
                    }
                }
            }
        }
        catch(error) {
            if (style.href !== null) {
                style.disabled = true;
                alert("@EOLIE_CSS_URI@" + style.href)
            }
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
html = document.querySelector("html");
if (html !== null) {
    html.style.display = "none";
}
observer.observe(head, config);
window.addEventListener("DOMContentLoaded", (event) => {
    setStyleCheets();
});
window.addEventListener("load", (event) => {
    setStyleCheets();
    html.style.display = "block";
});
