# File: viyv_mcp/__init__.py

# バージョンや他の要素があればそのまま
__version__ = "2.0.0"

# ここで core.py のクラスを読み込み
from .core import ViyvMCP
from .decorators import tool, resource, prompt, entry