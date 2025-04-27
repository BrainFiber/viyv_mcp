# File: viyv_mcp/cli.py

import sys
import shutil
import argparse
from pathlib import Path
from . import __version__

TEMPLATES_DIR = Path(__file__).parent / "templates"

def main():
    parser = argparse.ArgumentParser(prog="create-viyv-mcp")
    parser.add_argument("command", choices=["new"], help="Subcommand (only 'new' supported)")
    parser.add_argument("project_name", help="Name of the new project directory")
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    args = parser.parse_args()

    if args.command == "new":
        create_new_project(args.project_name)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)

def create_new_project(project_name: str):
    target_dir = Path(project_name).resolve()
    if target_dir.exists():
        print(f"Error: directory '{target_dir}' already exists.", file=sys.stderr)
        sys.exit(1)

    # Python 3.8+ なら dirs_exist_ok=True を使える
    # これにより TEMPLATES_DIR にある Dockerfile / pyproject.toml 等も全てコピーされる
    shutil.copytree(TEMPLATES_DIR, target_dir, dirs_exist_ok=True)

    print(f"Successfully created project in {target_dir}")
    print("Next steps:")
    print(f"  cd {project_name}")
    print("  uv sync")
    print("  uv run python main.py")