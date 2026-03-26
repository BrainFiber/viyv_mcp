# File: viyv_mcp/__init__.py

# バージョンや他の要素があればそのまま
__version__ = "1.0.0"

# ここで core.py のクラスを読み込み
from .core import ViyvMCP
from .decorators import tool, resource, prompt, agent, entry