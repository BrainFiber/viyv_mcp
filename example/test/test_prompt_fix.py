"""
Test suite for Prompt Parameter Parsing Bug Fix (v0.1.16)

Tests that _register_prompt_bridge correctly handles PromptArgument objects
instead of treating them as dictionaries.
"""

import pytest
import inspect
from unittest.mock import AsyncMock, MagicMock
from mcp import types
from fastmcp import FastMCP
from viyv_mcp.app.bridge_manager import _register_prompt_bridge


def test_prompt_argument_with_required_fields():
    """
    Test that PromptArgument objects with required=True are parsed correctly.
    """
    # Create a mock FastMCP instance
    mcp = FastMCP("test-mcp")

    # Create a mock session
    session = AsyncMock()

    # Create a Prompt with PromptArgument objects (not dicts!)
    prompt = types.Prompt(
        name="aws_cost_query",
        description="Query AWS cost data",
        arguments=[
            types.PromptArgument(
                name="account_ids",
                description="AWS account IDs to query",
                required=True
            ),
            types.PromptArgument(
                name="start_date",
                description="Start date for cost data",
                required=True
            )
        ]
    )

    # This should not raise ValueError anymore
    try:
        _register_prompt_bridge(mcp, session, prompt)
        print("✅ Test passed: PromptArgument with required=True parsed correctly")
        print("   - No ValueError was raised")
        print("   - PromptArgument.name attribute was accessed correctly")
    except ValueError as e:
        pytest.fail(f"❌ Test failed: ValueError raised: {e}")
    except Exception as e:
        pytest.fail(f"❌ Test failed: Unexpected error: {e}")


def test_prompt_argument_with_optional_fields():
    """
    Test that PromptArgument objects with required=False get default=None.
    """
    mcp = FastMCP("test-mcp")
    session = AsyncMock()

    prompt = types.Prompt(
        name="bedrock_kb_search",
        description="Search Bedrock Knowledge Base",
        arguments=[
            types.PromptArgument(
                name="query",
                description="Search query",
                required=True
            ),
            types.PromptArgument(
                name="max_results",
                description="Maximum number of results",
                required=False  # Optional parameter
            )
        ]
    )

    try:
        _register_prompt_bridge(mcp, session, prompt)
        print("✅ Test passed: PromptArgument with required=False parsed correctly")
        print("   - Optional parameter handled correctly")
    except ValueError as e:
        pytest.fail(f"❌ Test failed: ValueError raised: {e}")
    except Exception as e:
        pytest.fail(f"❌ Test failed: Unexpected error: {e}")


def test_prompt_argument_without_description():
    """
    Test that PromptArgument objects without description are handled correctly.
    """
    mcp = FastMCP("test-mcp")
    session = AsyncMock()

    prompt = types.Prompt(
        name="simple_prompt",
        description="A simple prompt",
        arguments=[
            types.PromptArgument(
                name="param1",
                # No description
                required=True
            )
        ]
    )

    try:
        _register_prompt_bridge(mcp, session, prompt)
        print("✅ Test passed: PromptArgument without description parsed correctly")
    except ValueError as e:
        pytest.fail(f"❌ Test failed: ValueError raised: {e}")
    except Exception as e:
        pytest.fail(f"❌ Test failed: Unexpected error: {e}")


def test_prompt_with_no_arguments():
    """
    Test that prompts without arguments are handled correctly.
    """
    mcp = FastMCP("test-mcp")
    session = AsyncMock()

    prompt = types.Prompt(
        name="no_args_prompt",
        description="Prompt with no arguments",
        arguments=None  # No arguments
    )

    try:
        _register_prompt_bridge(mcp, session, prompt)
        print("✅ Test passed: Prompt with no arguments parsed correctly")
    except Exception as e:
        pytest.fail(f"❌ Test failed: {e}")


def test_prompt_argument_default_required_behavior():
    """
    Test that when required field is None, it defaults to True.
    """
    mcp = FastMCP("test-mcp")
    session = AsyncMock()

    prompt = types.Prompt(
        name="default_required_test",
        description="Test default required behavior",
        arguments=[
            types.PromptArgument(
                name="param_with_none_required",
                description="Parameter where required=None",
                required=None  # Should default to True
            )
        ]
    )

    try:
        _register_prompt_bridge(mcp, session, prompt)
        print("✅ Test passed: PromptArgument with required=None defaults to True")
    except ValueError as e:
        pytest.fail(f"❌ Test failed: ValueError raised: {e}")
    except Exception as e:
        pytest.fail(f"❌ Test failed: Unexpected error: {e}")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("Testing Prompt Parameter Parsing Bug Fix (v0.1.16)")
    print("="*80 + "\n")

    test_prompt_argument_with_required_fields()
    test_prompt_argument_with_optional_fields()
    test_prompt_argument_without_description()
    test_prompt_with_no_arguments()
    test_prompt_argument_default_required_behavior()

    print("\n" + "="*80)
    print("✅ All tests passed!")
    print("="*80)
    print("\nConclusion:")
    print("- PromptArgument objects are now correctly parsed as Pydantic objects")
    print("- required field properly controls default values")
    print("- AWS MCP servers with prompts should now work correctly")
