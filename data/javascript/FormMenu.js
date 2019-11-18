
formsArrayMenu = document.querySelectorAll("form");
user_form_names = "";
formsArrayMenu.forEach(function(form) {
    inputsArrayMenu = form.querySelectorAll("input");
    inputsArrayMenu.forEach(function(input) {
        const types = ["text", "email", "search"];
        const names = ["login", "user", "email"];
        let name = input.getAttribute("name");
        let type = input.getAttribute("type");
        let valid_type = types.includes(type);
        let valid_name = false;
        if (name !== null) {
            for (let i = 0; i < names.length; i++) {
                if (name.search(names[i]) != -1) {
                    valid_name = true;
                }
            }
            if (type != "password" && (valid_type || valid_name)) {
                user_form_names = user_form_names.concat(input.name, "\n");
                input.addEventListener("click", function() {
                    message = "@EOLIE_FORM_MENU_MESSAGE@\n";
                    message += input.name;
                    alert(message);
                });
            }
        }
    });
});
user_form_names;
