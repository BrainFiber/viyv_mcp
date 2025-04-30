from typing import Callable, List, Tuple, Union, Awaitable
from starlette.types import ASGIApp

# (path, app_or_factory) のタプルを貯める
_ENTRIES: List[Tuple[str, Union[ASGIApp, Callable[[], ASGIApp]]]] = []

def add_entry(path: str, app: Union[ASGIApp, Callable[[], ASGIApp]]) -> None:
    _ENTRIES.append((path, app))

def list_entries() -> List[Tuple[str, Union[ASGIApp, Callable[[], ASGIApp]]]]:
    # `/` を最後にマウントしたいので長いパス順に並べ替え
    return sorted(_ENTRIES, key=lambda t: len(t[0]), reverse=True)