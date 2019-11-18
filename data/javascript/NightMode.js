var observer = new MutationObserver(subscriber);
var config = { attributeFilter: ["style"], attributes: true, childList: true, subtree: true };

function setStyle(e) {
    e.style.color = "#EAEAEA";
    background_image = e.style.backgroundImage != "undefined" && e.style.backgroundImage.search("url") != -1
    background = e.style.background != "undefined" && e.style.background.search("url") != -1
    if (!background && !background_image) {
        e.style.backgroundImage = "none";
        e.style.backgroundColor = "#353535";
        e.style.background =  "#353535";
    }
}

function subscriber(mutations) {
    mutations.forEach((mutation) => {
        elements = mutation.target.querySelectorAll("*")
        elements.forEach((e) => {
            observer.disconnect();
            observer.takeRecords();
            setStyle(e);
            observer.observe(document.querySelector("body"), config);
        });
    });
}

if(document.readyState === "complete") {
    elements = document.querySelectorAll("*");
    elements.forEach((e) => {
        setStyle(e);
    });
    observer.observe(document.querySelector("body"), config);
}
else if(document.readyState === "interactive") {
    elements = document.querySelectorAll("*");
    elements.forEach((e) => {
        setStyle(e);
    });
    observer.observe(document.querySelector("body"), config);
}
else {
    elements = document.querySelectorAll("*");
        elements.forEach((e) => {
            setStyle(e);
        });
    window.addEventListener("DOMContentLoaded", (event) => {
        elements = document.querySelectorAll("*");
        elements.forEach((e) => {
            setStyle(e);
        });
        observer.observe(document.querySelector("body"), config);
    });
}
