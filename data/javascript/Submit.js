let elementsArray = document.querySelectorAll("form");

elementsArray.forEach(function(elem) {
    elem.addEventListener("submit", function() {
        const types = ["text", "email", "search"];
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
            if (types.includes(type) && name !== null) {
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
    });
});
