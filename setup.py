from setuptools import setup, find_packages

setup(
    name="terraguard",
    version="1.0.0",
    description="AI-powered Terraform cost analyzer and infrastructure explainer",
    author="Anant",
    packages=find_packages(),
    install_requires=[
        "rich",
        "typer",
        "python-hcl2",
        "requests",
        "boto3",
        "groq",
        "python-dotenv",
        "textual",
        "pyperclip"
    ],
    entry_points={
        "console_scripts": [
            "terraguard=terraguard.cli:main"
        ]
    },
    python_requires=">=3.8",
)