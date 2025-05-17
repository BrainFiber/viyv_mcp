import importlib.util
import os
import sys
import types

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Create a minimal viyv_mcp package to satisfy relative import in cli
package = types.ModuleType("viyv_mcp")
package.__path__ = [os.path.join(ROOT_DIR, "viyv_mcp")]
package.__version__ = "0"
sys.modules['viyv_mcp'] = package

spec = importlib.util.spec_from_file_location(
    'viyv_mcp.cli',
    os.path.join(ROOT_DIR, 'viyv_mcp', 'cli.py'),
)
cli = importlib.util.module_from_spec(spec)
sys.modules['viyv_mcp.cli'] = cli
spec.loader.exec_module(cli)


def test_create_new_project(tmp_path):
    project_dir = tmp_path / "sample_project"
    cli.create_new_project(str(project_dir))
    assert project_dir.exists()
    assert (project_dir / "main.py").exists()

