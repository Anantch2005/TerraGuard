from rich import print
from rich.tree import Tree
import re
from collections import defaultdict


# ─────────────────────────────────────────────────────────────────────────────
# Classification tables
# ─────────────────────────────────────────────────────────────────────────────

# The ONLY config keys that make a resource a direct child of another in
# the placement tree.  Every other reference becomes a "depends on" annotation.
#
# Rule: a resource is placed under EXACTLY ONE parent.
# Priority: explicit vpc_id/route_table_id/subnet_id > inferred VPC root
#
# Special cases handled separately:
#   aws_route                → child of its route_table  (route_table_id key)
#   aws_route_table_association → child of its subnet    (subnet_id key)
#
# Everything else with vpc_id → direct VPC child (flat, not nested in subnet).

TREE_PARENT_KEYS = {
    "vpc_id",          # → placed under that VPC
    "route_table_id",  # aws_route → placed under its route table
                       # aws_route_table_association also uses this but
                       # subnet_id takes priority (handled in Pass 1)
}

# subnet_id is NOT a tree-parent key for most resources.
# aws_route_table_association is the exception (handled explicitly).
# For all other resources subnet_id → "depends on subnet" annotation only.

# Config keys whose references become "depends on" child annotations.
DEPENDS_ON_KEYS = {
    "subnet_id",
    "subnet_ids",
    "db_subnet_group_name",
    "vpc_security_group_ids",
    "security_groups",
    "security_group_ids",
    "db_security_groups",
    "iam_instance_profile",
    "iam_role_arn",
    "role_arn",
    "execution_role_arn",
    "task_role_arn",
    "load_balancer_arn",
    "target_group_arn",
    "target_group_arns",
    "gateway_id",
    "nat_gateway_id",
    "cluster_id",
    "launch_template",
}

# Global services — always top-level roots, never inside a VPC tree.
GLOBAL_TYPES = {
    "aws_s3_bucket",
    "aws_dynamodb_table",
    "aws_cloudfront_distribution",
    "aws_iam_role",
    "aws_iam_policy",
    "aws_iam_role_policy_attachment",
    "aws_sns_topic",
    "aws_sqs_queue",
    "aws_route53_zone",
    "aws_route53_record",
    "aws_acm_certificate",
    "aws_wafv2_web_acl",
}

# Types that, if they have a vpc_id, are VPC-level children.
# (Any type with vpc_id not in this set is also treated as VPC-level by default.)
# Listed explicitly so inferred placement also works when vpc_id is absent.
VPC_LEVEL_TYPES = {
    "aws_subnet",
    "aws_internet_gateway",
    "aws_nat_gateway",
    "aws_security_group",
    "aws_route_table",
    "aws_network_acl",
    "aws_vpc_peering_connection",
    "aws_lb",
    "aws_alb",
    "aws_instance",
    "aws_db_instance",
    "aws_db_cluster",
    "aws_db_subnet_group",
    "aws_elasticache_subnet_group",
    "aws_elasticache_cluster",
    "aws_elasticache_replication_group",
    "aws_lambda_function",
    "aws_ecs_cluster",
    "aws_ecs_service",
    "aws_eks_cluster",
    "aws_eks_node_group",
    "aws_network_interface",
}


# ─────────────────────────────────────────────────────────────────────────────
# Reference extraction
# ─────────────────────────────────────────────────────────────────────────────

_PAT = re.compile(r"(aws_[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+)")


def _extract_refs(config):
    """
    Return two dicts keyed by config key:
        tree_refs    – references that drive TREE PLACEMENT
        depends_refs – references that become "depends on" annotations
    Values are sets of node-key strings.
    """
    tree_refs    = defaultdict(set)
    depends_refs = defaultdict(set)

    def scan(value, hint=None):
        if isinstance(value, str):
            for ref in _PAT.findall(value):
                if hint in TREE_PARENT_KEYS:
                    tree_refs[hint].add(ref)
                elif hint in DEPENDS_ON_KEYS:
                    depends_refs[hint].add(ref)
                # else: ignored (e.g. AMI IDs, CIDR strings that happen to match)
        elif isinstance(value, list):
            for v in value:
                scan(v, hint)
        elif isinstance(value, dict):
            for k, v in value.items():
                scan(v, hint=k)

    scan(config)
    return tree_refs, depends_refs


# ─────────────────────────────────────────────────────────────────────────────
# Build graph
# ─────────────────────────────────────────────────────────────────────────────

def build_graph(resources):
    """
    Returns:
        nodes       : dict[node_key → resource_dict]
        edges       : dict[parent_key → set(child_keys)]   placement tree
        dep_annots  : dict[node_key  → list[str]]          "depends on …" lines
    """
    nodes      = {}
    edges      = defaultdict(set)
    dep_annots = defaultdict(list)   # ordered annotation lines per node

    for r in resources:
        nodes[f"{r['type']}.{r['name']}"] = r

    by_type = defaultdict(list)
    for r in resources:
        by_type[r["type"]].append(r)

    def key(r):
        return f"{r['type']}.{r['name']}"

    def sname(node_key):
        return node_key.split(".", 1)[-1]

    has_placement = set()   # nodes that already have a tree parent

    def place(parent_key, child_key):
        if parent_key not in nodes or child_key not in nodes:
            return
        if child_key in has_placement:
            return
        edges[parent_key].add(child_key)
        has_placement.add(child_key)

    # ── Pass 1: explicit references ──────────────────────────────────────────
    for r in resources:
        rk = key(r)
        tree_refs, depends_refs = _extract_refs(r.get("config", {}))

        # ── Tree placement from explicit keys ─────────────────────────────────

        # Special case 1: aws_route_table_association → child of its subnet
        if r["type"] == "aws_route_table_association":
            for ref in tree_refs.get("subnet_id", depends_refs.get("subnet_id", set())):
                # subnet_id is in DEPENDS_ON_KEYS normally; override for rta
                if ref in nodes:
                    place(ref, rk)
            # Also capture the route_table ref as a depends-on annotation
            for ref in tree_refs.get("route_table_id", set()):
                if ref in nodes:
                    dep_annots[rk].append(f"binds  {sname(ref)}")

        # Special case 2: aws_route → child of its route table
        elif r["type"] == "aws_route":
            for ref in tree_refs.get("route_table_id", set()):
                if ref in nodes:
                    place(ref, rk)

        # General case: vpc_id → child of that VPC
        else:
            for ref in tree_refs.get("vpc_id", set()):
                if ref in nodes:
                    place(ref, rk)

        # ── Depends-on annotations (all types) ───────────────────────────────
        LABEL = {
            "subnet_id":            "subnet",
            "subnet_ids":           "subnet",
            "db_subnet_group_name": "subnet-group",
            "vpc_security_group_ids": "sg",
            "security_groups":      "sg",
            "security_group_ids":   "sg",
            "db_security_groups":   "sg",
            "iam_instance_profile": "iam",
            "iam_role_arn":         "iam",
            "role_arn":             "iam",
            "execution_role_arn":   "iam",
            "task_role_arn":        "iam",
            "load_balancer_arn":    "lb",
            "target_group_arn":     "target-group",
            "target_group_arns":    "target-group",
            "gateway_id":           "via",
            "nat_gateway_id":       "via",
            "cluster_id":           "cluster",
        }
        for dep_key, refs in depends_refs.items():
            label = LABEL.get(dep_key, dep_key)
            valid = sorted(sname(ref) for ref in refs if ref in nodes)
            if valid:
                dep_annots[rk].append(f"{label}  {', '.join(valid)}")

        # Also capture security_group refs that ended up in tree_refs
        # (shouldn't happen with current tables, but be safe)

    # ── Pass 2: inferred placement for unplaced VPC-level resources ──────────
    vpcs = by_type.get("aws_vpc", [])
    if vpcs:
        vpc_key = key(vpcs[0])   # use first VPC if multiple
        for r in resources:
            rk = key(r)
            t  = r["type"]
            if t in GLOBAL_TYPES or t == "aws_vpc":
                continue
            if rk in has_placement:
                continue
            if t in VPC_LEVEL_TYPES:
                place(vpc_key, rk)
            # Unknown types with no placement → orphan (shown at end)

    # ── Pass 3: inferred depends-on annotations ───────────────────────────────
    # For resources that reference another resource via a depends-on key but
    # the reference wasn't in the config (e.g. parser didn't provide it),
    # we skip — we only annotate what we can prove from explicit config.

    # ── Pass 4: Lambda → DynamoDB (single table, no explicit ref) ────────────
    for r in by_type.get("aws_lambda_function", []):
        rk = key(r)
        tables = by_type.get("aws_dynamodb_table", [])
        existing = dep_annots.get(rk, [])
        already  = any("dynamodb" in a for a in existing)
        if len(tables) == 1 and not already:
            dep_annots[rk].append(f"table  {sname(key(tables[0]))}")

    return nodes, edges, dep_annots


# ─────────────────────────────────────────────────────────────────────────────
# Reachability
# ─────────────────────────────────────────────────────────────────────────────

def reachable(root, edges):
    visited, stack = set(), [root]
    while stack:
        n = stack.pop()
        if n in visited:
            continue
        visited.add(n)
        stack.extend(edges.get(n, []))
    return visited


# ─────────────────────────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────────────────────────

def show_diagram(resources):
    print("\n[bold green]Infrastructure Dependency Graph[/bold green]\n")

    nodes, edges, dep_annots = build_graph(resources)

    all_children = {c for cs in edges.values() for c in cs}
    vpc_roots    = [n for n in nodes if n.startswith("aws_vpc")]
    other_roots  = [n for n in nodes if n not in all_children and n not in vpc_roots]

    rendered = set()

    for root in vpc_roots + other_roots:
        r     = nodes[root]
        label = _label(root, r, dep_annots, bold=True)
        tree  = Tree(label)

        visited = {root}
        _build_tree(root, tree, nodes, edges, dep_annots, visited, depth=0)

        print(tree)
        print()
        rendered.update(reachable(root, edges))
        rendered.add(root)

    orphans = [n for n in nodes if n not in rendered]
    if orphans:
        print("[bold yellow]Unattached Resources[/bold yellow]")
        for o in sorted(orphans):
            r = nodes[o]
            print(f"  [dim]○[/dim]  [yellow]{r['type']}[/yellow] → {r['name']}")
        print()


def _label(node_key, r, dep_annots, bold=False):
    t = f"[bold cyan]{r['type']}[/bold cyan]" if bold else f"[green]{r['type']}[/green]"
    n = f"[bold]{r['name']}[/bold]"           if bold else r["name"]
    return f"{t}  [dim]→[/dim]  {n}"


def _build_tree(node, branch, nodes, edges, dep_annots, visited, depth):
    if depth > 50:
        branch.add("[red]… depth limit[/red]")
        return

    # ── Depends-on annotations as virtual child lines ─────────────────────────
    for ann in dep_annots.get(node, []):
        branch.add(f"[dim]depends on  {ann}[/dim]")

    # ── Actual tree children ──────────────────────────────────────────────────
    for child in sorted(edges.get(node, [])):
        r = nodes.get(child)
        if not r:
            continue
        if child in visited:
            branch.add(f"[dim]⤷ {r['type']} → {r['name']} (see above)[/dim]")
            continue
        visited.add(child)
        sub = branch.add(_label(child, r, dep_annots))
        _build_tree(child, sub, nodes, edges, dep_annots, visited, depth + 1)