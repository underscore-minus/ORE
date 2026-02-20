"""
ORE v0.9 application entry point.
Loads environment and delegates to the CLI.
"""

from dotenv import load_dotenv

from ore import cli

if __name__ == "__main__":
    load_dotenv()
    cli.run()
