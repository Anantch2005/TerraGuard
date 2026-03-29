from textual.app import App, ComposeResult
from textual.widgets import Tree, Input
from textual.binding import Binding
from rich.text import Text

from terraguard.parser import parse_terraform
from terraguard.cost_engine import get_resource_cost
from terraguard.aws_resource_map import RESOURCE_MAP
from terraguard.formatter import clean_value, format_cost
from terraguard.ai_explainer import explain_resource, explain_infrastructure


class TerraGuardUI(App):

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("c", "copy", "Copy Selected"),
        Binding("C", "copy_all", "Copy All"),
        Binding("/", "search", "Search"),
        Binding("e", "explain", "Explain Resource"),        # ✅
        Binding("E", "explain_all", "Explain Infra"),       # 🔥
    ]

    def compose(self) -> ComposeResult:
        yield Tree("Detected Resources")
        yield Input(placeholder="Search...", id="search", classes="hidden")

    def on_mount(self):
        self.resources = parse_terraform()
        tree = self.query_one(Tree)

        self.node_map = {}
        self.all_nodes = []
        self.original_labels = {}

        for r in self.resources:
            label = self.get_label(r)

            node = tree.root.add(label)

            self.node_map[node] = r
            self._track(node)

            self._add_config(node, r.get("config", {}))

            cost = get_resource_cost(r)
            cost_text = format_cost(cost)
            leaf = node.add_leaf(Text(f"cost: {cost_text}", style="green"))

            self._track(leaf)

        tree.root.expand()
        self.set_focus(tree)

    # -----------------------
    def get_label(self, resource):
        name = RESOURCE_MAP.get(resource["type"], resource["type"])
        return f"{name} ({resource['name']})"

    # -----------------------
    def _track(self, node):
        self.all_nodes.append(node)

        if isinstance(node.label, Text):
            self.original_labels[node] = node.label.plain
        else:
            self.original_labels[node] = str(node.label)

    # -----------------------
    def _add_config(self, parent, config):
        for k, v in config.items():

            if k == "cidr_blocks" and "0.0.0.0/0" in str(v):
                node = parent.add_leaf(Text(f"{k}: {v}", style="red"))
                self._track(node)
                continue

            if isinstance(v, list):
                node = parent.add(f"{k}:")
                self._track(node)

                for item in v:
                    if isinstance(item, dict):
                        sub = node.add("")
                        self._track(sub)
                        self._add_config(sub, item)
                    else:
                        leaf = node.add_leaf(str(clean_value(item)))
                        self._track(leaf)

            elif isinstance(v, dict):
                node = parent.add(f"{k}:")
                self._track(node)
                self._add_config(node, v)

            else:
                leaf = parent.add_leaf(f"{k}: {clean_value(v)}")
                self._track(leaf)

    # -----------------------
    # 🔥 SINGLE RESOURCE AI
    def action_explain(self):
        tree = self.query_one(Tree)
        node = tree.cursor_node

        if node not in self.node_map:
            self.notify("Select a resource node")
            return

        resource = self.node_map[node]

        self.notify("Generating explanation...")
        explanation = explain_resource(resource)

        self.notify(explanation, timeout=8)

    # -----------------------
    # 🔥 FULL INFRA AI
    def action_explain_all(self):
        self.notify("Analyzing infrastructure...")

        explanation = explain_infrastructure(self.resources)

        self.notify(explanation, timeout=10)

    # -----------------------
    def action_search(self):
        search_input = self.query_one("#search")
        search_input.remove_class("hidden")
        self.set_focus(search_input)

    def on_input_submitted(self, event):
        tree = self.query_one(Tree)
        search_input = self.query_one("#search")

        query = event.value.lower()

        for node, label in self.original_labels.items():
            node.set_label(label)

        matches = []

        for node in self.all_nodes:
            label = self.original_labels[node].lower()

            if query in label:
                matches.append(node)

                node.set_label(Text(self.original_labels[node], style="blue"))

                node.expand()
                parent = node.parent
                while parent:
                    parent.expand()
                    parent = parent.parent

        if not matches:
            self.notify("No match found")
        else:
            self.notify(f"{len(matches)} matches found")

        search_input.add_class("hidden")
        self.set_focus(tree)

    # -----------------------
    def action_copy(self):
        tree = self.query_one(Tree)
        node = tree.cursor_node

        if node not in self.node_map:
            return

        resource = self.node_map[node]
        cost = get_resource_cost(resource)

        output = f"{resource['type']} ({resource['name']})\n"

        for k, v in resource.get("config", {}).items():
            output += f"  {k}: {clean_value(v)}\n"

        output += f"  cost: {format_cost(cost)}\n"

        self._copy(output)

    # -----------------------
    def action_copy_all(self):
        output = ""

        for r in self.resources:
            output += f"{r['type']} ({r['name']})\n"

            for k, v in r.get("config", {}).items():
                output += f"  {k}: {clean_value(v)}\n"

            cost = get_resource_cost(r)
            output += f"  cost: {format_cost(cost)}\n"

            output += "\n"

        self._copy(output)

    # -----------------------
    def _copy(self, text):
        try:
            import pyperclip
            pyperclip.copy(text)
            self.notify("Copied")
        except:
            self.notify("Copy failed")

    # -----------------------
    def action_quit(self):
        self.exit()


if __name__ == "__main__":
    TerraGuardUI().run()