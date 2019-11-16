
let formsArrayMenu = document.querySelectorAll("form");
var user_form_names = "";
formsArrayMenu.forEach(function(form) {
    inputsArrayMenu = form.querySelectorAll("input");
    inputsArrayMenu.forEach(function(input) {
        const types = ["text", "email", "search"];
        let name = input.getAttribute("name");
        let type = input.getAttribute("type");
        if (types.includes(type) && name !== null) {
            user_form_names = user_form_names.concat(input.name, "\n");
            input.addEventListener("click", function() {
                message = "@EOLIE_FORM_MENU_MESSAGE@\n";
                message += input.name;
                alert(message);
            });
        }
    });
});
user_form_names;
