let elementsArraySubmit = document.querySelectorAll("form");

elementsArraySubmit.forEach(function(elem) {
    elem.addEventListener("submit", function() {
        const types = ["text", "email", "search"];
        const names = ["login", "user", "email"];
        let form_uri = elem.action
        let username_input_name;
        let username_input_value;
        let password_input_name;
        let password_input_value;
        let inputsArray = elem.querySelectorAll("input");
        for (let i = 0; i < inputsArray.length; i++) {
            let input = inputsArray[i];
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
                    username_input_name = input.name;
                    username_input_value = input.value;
                }
                if (type == "password") {
                    password_input_name = input.name;
                    password_input_value = input.value;
                }
                if (password_input_name !== undefined && username_input_name !== undefined) {
                    break;
                }
            }
        }
        if (password_input_name !== undefined && username_input_name !== undefined) {
            let message = "@EOLIE_SUBMIT@\n";
            message += username_input_name;
            message += "\n";
            message += username_input_value;
            message += "\n";
            message += password_input_name;
            message += "\n";
            message += password_input_value;
            message += "\n";
            message += form_uri;
            alert(message);
        }
    });
});
