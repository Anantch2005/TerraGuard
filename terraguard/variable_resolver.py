import os
import hcl2


def load_variable_defaults(directory="."):
    defaults = {}

    for file in os.listdir(directory):

        if file.endswith(".tf"):

            with open(os.path.join(directory, file), "r") as f:

                data = hcl2.load(f)

                if "variable" in data:

                    for var in data["variable"]:

                        for name, config in var.items():

                            if isinstance(config, dict) and "default" in config:
                                defaults[name] = config["default"]

    return defaults


def resolve_variable(value, defaults):

    if isinstance(value, str):

        # Handles: var.instance_type
        if value.startswith("var."):

            var_name = value.replace("var.", "")

            if var_name in defaults:
                return defaults[var_name]

        # Handles: ${var.instance_type}
        if "${var." in value:

            var_name = value.split("var.")[1].split("}")[0]

            if var_name in defaults:
                return defaults[var_name]

    return value