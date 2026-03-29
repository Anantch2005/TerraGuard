import os
import hcl2
from .variable_resolver import load_variable_defaults, resolve_variable


def detect_count(values):

    if "count" in values:
        try:
            return int(values["count"])
        except:
            return 1

    if "for_each" in values:
        # cannot fully evaluate terraform expressions
        # but we assume 3 resources as approximation
        return 3

    return 1


def parse_terraform(directory="."):

    resources = []

    defaults = load_variable_defaults(directory)

    for file in os.listdir(directory):

        if file.endswith(".tf"):

            with open(os.path.join(directory, file), "r") as f:

                data = hcl2.load(f)

                if "resource" not in data:
                    continue

                for resource in data["resource"]:

                    for rtype, configs in resource.items():

                        for name, values in configs.items():

                            resolved_config = {}

                            for key, val in values.items():
                                resolved_config[key] = resolve_variable(val, defaults)

                            count = detect_count(values)

                            resources.append({
                                "type": rtype,
                                "name": name,
                                "config": resolved_config,
                                "count": count
                            })

    return resources