let elementsArray = document.querySelectorAll("input[type='password']");

elementsArray.forEach(function(elem) {
    elem.addEventListener("focus", function() {
        alert("@EOLIE_FOCUS_MESSAGE@");
    });
});
