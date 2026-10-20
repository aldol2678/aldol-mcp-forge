"""Run: python -m enterprise_mcps seum|bonsae|majung"""
import argparse
from .server import create_app

def main():
    parser = argparse.ArgumentParser(description="ALDOL specialized MCP servers")
    parser.add_argument("company", choices=("seum", "bonsae", "majung"))
    args = parser.parse_args()
    create_app(args.company).run()

if __name__ == "__main__":
    main()
