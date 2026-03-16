"""Tools for Lmod module system queries."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..executor import CommandExecutor, ExecutorError
from ..server import mcp


def _get_executor(ctx: Context) -> CommandExecutor:
    return ctx.request_context.lifespan_context["executor"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def hpc_module_list(
    ctx: Context,
) -> str:
    """List currently loaded modules.

    Shows all modules in the current environment, including
    compilers, MPI stacks, and application modules.
    """
    executor = _get_executor(ctx)

    try:
        output = await executor.run_shell("module list 2>&1")
    except ExecutorError as e:
        return f"Error: {e}"

    if not output.strip() or "No modules loaded" in output:
        return "No modules currently loaded."

    return f"## Loaded Modules\n```\n{output}\n```"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def hpc_module_avail(
    ctx: Context,
    search: str | None = None,
) -> str:
    """Search for available modules.

    Uses 'module avail' to list loadable modules, or 'module spider'
    to search all modules including those with unmet dependencies.

    Args:
        search: Module name or pattern to search for (e.g. 'netcdf',
            'intel', 'hdf5'). If not provided, lists all available.
    """
    import re

    executor = _get_executor(ctx)

    # Validate search term
    if search and re.search(r"[;&|`$(){}]", search):
        return f"Error: Unsafe characters in search: '{search}'"

    # Use spider for search (finds all modules regardless of hierarchy)
    if search:
        try:
            output = await executor.run_shell(f"module spider {search} 2>&1")
        except ExecutorError as e:
            return f"Error: {e}"

        if not output.strip():
            return f"No modules found matching '{search}'."

        return f"## Module Search: {search}\n```\n{output}\n```"

    # No search term — list all available
    try:
        output = await executor.run_shell("module avail 2>&1")
    except ExecutorError as e:
        return f"Error: {e}"

    if not output.strip():
        return "No modules available."

    return f"## Available Modules\n```\n{output}\n```"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def hpc_module_info(
    ctx: Context,
    module_name: str,
) -> str:
    """Show detailed information about a specific module.

    Displays the module file contents including paths, environment
    variables, and dependencies.

    Args:
        module_name: Full module name (e.g. 'netcdf-c/4.9.2', 'intel/2023.2.0').
    """
    import re

    executor = _get_executor(ctx)

    if re.search(r"[;&|`$(){}]", module_name):
        return f"Error: Unsafe characters in module name: '{module_name}'"

    try:
        output = await executor.run_shell(f"module show {module_name} 2>&1")
    except ExecutorError as e:
        return f"Error: {e}"

    if not output.strip():
        return f"Module '{module_name}' not found."

    return f"## Module: {module_name}\n```\n{output}\n```"
