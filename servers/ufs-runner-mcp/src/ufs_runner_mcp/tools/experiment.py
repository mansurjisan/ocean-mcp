"""Tools for creating, validating, and submitting UFS experiments."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..runner import RunnerError, UfsRunner
from ..server import mcp


def _get_runner(ctx: Context) -> UfsRunner:
    return ctx.request_context.lifespan_context["ufs_runner"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )
)
async def ufs_create_experiment(
    ctx: Context,
    model_type: str,
    run_dir: str,
    template: str | None = None,
    overrides: str | None = None,
    input_data_dir: str | None = None,
) -> str:
    """Create a UFS-Coastal experiment directory from a template.

    Sets up the run directory with namelists, configs, and input file stubs
    copied from an approved template. Only operates in whitelisted scratch paths.

    Args:
        model_type: Model configuration — 'schism', 'adcirc', or 'fvcom'.
        run_dir: Absolute path for the experiment directory (must be under /scratch*).
        template: Template name (default: auto-detected). Use ufs_list_templates to see options.
        overrides: JSON string of parameter overrides. Flat keys set template variables
            (e.g. '{"start_year": 2024, "nhours_fcst": 12, "nodes": 8}').
            Nested dicts set namelist group values
            (e.g. '{"CORE": {"dt": 5.0, "rnday": 0.5}}').
            Common variables: start_year, start_month, start_day, start_hour,
            nhours_fcst, dt_ocean, dt_atmos, coupling_interval, atm_tasks,
            ocn_tasks, nodes, tasks_per_node, wall_minutes, job_name.
        input_data_dir: Path to an existing UFS run directory to copy input data
            from (mesh files, forcing data, executables). Files are symlinked
            when possible. Template files are not overwritten.
    """
    try:
        import json as _json

        override_dict = _json.loads(overrides) if overrides else None

        runner = _get_runner(ctx)
        result = runner.create_experiment(
            model_type=model_type,
            run_dir=run_dir,
            template=template,
            overrides=override_dict,
            input_data_dir=input_data_dir,
        )

        lines = [
            "## Experiment Created",
            f"- **Model**: {result['model_type']}",
            f"- **Template**: {result['template']}",
            f"- **Directory**: {result['run_dir']}",
            f"- **Files**: {len(result['files'])}",
        ]
        if result.get("staged_files"):
            lines.append(
                f"- **Staged from input**: {len(result['staged_files'])} files"
            )

        lines += ["", "### Files"]
        for f in result["files"]:
            lines.append(f"- {f}")

        if result.get("staged_files"):
            lines += ["", "### Staged Input Files"]
            for f in result["staged_files"]:
                lines.append(f"- {f}")

        lines.append(
            "\nNext: call `ufs_validate_experiment` to check the setup, "
            "then `ufs_submit_experiment` to submit."
        )
        return "\n".join(lines)

    except RunnerError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def ufs_validate_experiment(
    ctx: Context,
    run_dir: str,
) -> str:
    """Validate a UFS experiment directory is ready for submission.

    Checks for required files, valid namelists, and Slurm submission scripts.

    Args:
        run_dir: Path to the experiment directory.
    """
    try:
        runner = _get_runner(ctx)
        result = runner.validate_experiment(run_dir)

        lines = [
            "## Experiment Validation",
            f"- **Directory**: {result['run_dir']}",
            f"- **Model**: {result['model_type']}",
            f"- **Ready**: {'YES' if result['ready'] else 'NO'}",
        ]

        if result["errors"]:
            lines.append(f"\n### Errors ({len(result['errors'])})")
            for err in result["errors"]:
                lines.append(f"- {err['message']}")

        if result["warnings"]:
            lines.append(f"\n### Warnings ({len(result['warnings'])})")
            for w in result["warnings"]:
                lines.append(f"- {w}")

        lines.append(f"\n### Files ({len(result['files_found'])})")
        for f in result["files_found"]:
            lines.append(f"- {f}")

        return "\n".join(lines)

    except RunnerError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )
)
async def ufs_submit_experiment(
    ctx: Context,
    run_dir: str,
    account: str,
    partition: str,
    nodes: int = 1,
    wall_hours: int = 1,
    qos: str | None = None,
    dry_run: bool = True,
) -> str:
    """Submit a UFS experiment to Slurm.

    IMPORTANT: Defaults to dry_run=true — shows the sbatch command without
    executing. Set dry_run=false only after reviewing the dry-run output.

    Args:
        run_dir: Path to the experiment directory.
        account: Slurm account/allocation name.
        partition: Slurm partition.
        nodes: Number of compute nodes (default 1, max 50).
        wall_hours: Wall clock limit in hours (default 1, max 12).
        qos: Optional QOS (e.g. 'batch', 'debug', 'gpu').
        dry_run: If true (default), show command without submitting.
    """
    try:
        runner = _get_runner(ctx)
        result = runner.submit_experiment(
            run_dir=run_dir,
            account=account,
            partition=partition,
            nodes=nodes,
            wall_hours=wall_hours,
            qos=qos,
            dry_run=dry_run,
        )

        if result["mode"] == "dry_run":
            return (
                f"## Dry Run (not submitted)\n\n"
                f"**Command:**\n```\n{result['command']}\n```\n\n"
                f"- **Script**: {result['script']}\n"
                f"- **Directory**: {result['run_dir']}\n\n"
                f"Review the command above. To actually submit, call "
                f"`ufs_submit_experiment` again with `dry_run=false`."
            )

        return (
            f"## Job Submitted\n\n"
            f"- **Job ID**: {result['job_id']}\n"
            f"- **Command**: `{result['command']}`\n"
            f"- **Directory**: {result['run_dir']}\n\n"
            f"Use `ufs_get_run_status` to monitor progress."
        )

    except RunnerError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def ufs_list_templates(
    ctx: Context,
) -> str:
    """List available UFS experiment templates.

    Shows all pre-configured model templates that can be used
    with ufs_create_experiment.
    """
    runner = _get_runner(ctx)
    templates_dir = runner._templates_dir

    if not templates_dir.exists():
        return "No templates directory found. Templates need to be installed."

    templates = [
        d.name
        for d in templates_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ]

    if not templates:
        return (
            "No templates available. Add template directories to the templates/ folder."
        )

    lines = ["## Available Templates"]
    for t in sorted(templates):
        files = list((templates_dir / t).rglob("*"))
        file_count = len([f for f in files if f.is_file()])
        lines.append(f"- **{t}** ({file_count} files)")

    return "\n".join(lines)
