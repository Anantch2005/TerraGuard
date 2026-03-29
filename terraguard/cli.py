import typer
from rich import print

from .parser import parse_terraform
from .diagram import show_diagram
from .tui.app import TerraGuardUI

app = typer.Typer(help="TerraGuard - Terraform visual analyzer")


@app.command()
def init():
    """Launch interactive terminal UI"""
    TerraGuardUI().run()


@app.command()
def graph():
    """Show dependency graph"""
    resources = parse_terraform()
    show_diagram(resources)


@app.command()
def version():
    print("TerraGuard v2 (TUI Edition)")


def main():
    app()


if __name__ == "__main__":
    main()