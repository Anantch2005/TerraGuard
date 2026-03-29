import re


# -----------------------------
# Clean Terraform references
# -----------------------------
def clean_value(value):
    if isinstance(value, str):

        # ${aws_vpc.myvpc.id} → aws_vpc.myvpc
        if value.startswith("${") and value.endswith("}"):
            value = value[2:-1]

        # Remove .id
        value = re.sub(r"\.id$", "", value)

        # file("...") → file(...)
        value = value.replace('"', "")

        return value

    return value


# -----------------------------
# Format dict nicely
# -----------------------------
def format_dict(d, indent=2):
    lines = []

    for k, v in d.items():

        if isinstance(v, list):
            lines.append(f"{' ' * indent}{k}:")
            for item in v:
                if isinstance(item, dict):
                    lines.append(format_dict(item, indent + 4))
                else:
                    lines.append(f"{' ' * (indent + 2)}- {clean_value(item)}")

        elif isinstance(v, dict):
            lines.append(f"{' ' * indent}{k}:")
            lines.append(format_dict(v, indent + 2))

        else:
            lines.append(f"{' ' * indent}{k}: {clean_value(v)}")

    return "\n".join(lines)


# -----------------------------
# Format full resource
# -----------------------------
def format_resource(resource, cost=None):
    output = f"{resource['type']} ({resource['name']})\n"

    config = resource.get("config", {})

    if config:
        output += format_dict(config) + "\n"

    if cost:
        output += f"  cost: ${cost:.4f}/hr\n"

    return output


def format_cost(cost):
    if cost is None:
        return "not available"

    if cost == 0:
        return "$0.0000/hr (Free)" 
        
    return f"${cost:.4f}/hr"
