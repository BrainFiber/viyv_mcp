# Decorators wrapping mcp decorators

from mcp.server.fastmcp import FastMCP
import inspect


def _get_mcp_from_stack():
    for frame_info in inspect.stack():
        local = frame_info.frame.f_locals
        if 'mcp' in local and isinstance(local['mcp'], FastMCP):
            return local['mcp']
    raise RuntimeError("viyv decorator must be used inside register(mcp)")


def tool(name=None, description=None):
    """Wraps @mcp.tool: finds mcp instance in caller and registers the tool"""
    def decorator(fn):
        mcp = _get_mcp_from_stack()
        mcp.tool(name=name, description=description)(fn)
        return fn
    return decorator


def resource(uri, name=None, description=None, mime_type=None):
    """Wraps @mcp.resource: finds mcp instance in caller and registers the resource"""
    def decorator(fn):
        mcp = _get_mcp_from_stack()
        mcp.resource(uri, name=name, description=description, mime_type=mime_type)(fn)
        return fn
    return decorator


def prompt(name=None, description=None):
    """Wraps @mcp.prompt: finds mcp instance in caller and registers the prompt"""
    def decorator(fn):
        mcp = _get_mcp_from_stack()
        mcp.prompt(name=name, description=description)(fn)
        return fn
    return decorator


def agent(*args, **kwargs):
    """Decorator for registering viyv agents"""
    def decorator(obj):
        obj.__viyv_agent__ = True
        return obj
    return decorator
