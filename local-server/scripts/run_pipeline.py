#!/usr/bin/env python3
"""
Command-line harness for invoking pipelines.

Usage:
    python -m local_server.scripts.run_pipeline \\
        --type individual_extraction \\
        --config extraction-default \\
        --input /path/to/input.json \\
        --output /path/to/output.json \\
        [--implementation default] \\
        [--dry-run] \\
        [--log-iteration]

Examples:
    # Run individual extraction
    python -m local_server.scripts.run_pipeline \\
        --type individual_extraction \\
        --config extraction-default \\
        --input examples/input.json \\
        --output /tmp/output.json \\
        --log-iteration

    # Dry-run to validate configuration
    python -m local_server.scripts.run_pipeline \\
        --type individual_extraction \\
        --config extraction-default \\
        --input examples/input.json \\
        --dry-run

    # Use a specific implementation
    python -m local_server.scripts.run_pipeline \\
        --type schema_extraction \\
        --implementation custom-impl \\
        --config schema-v2 \\
        --input examples/schema-input.json \\
        --output /tmp/schema-output.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add local-server to path so we can import domain modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.pipelines.entities import PipelineType
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
    PipelineTypeRegistry,
)
from utils.logger import get_logger

_logger = get_logger(__name__)


def main() -> int:
    """Execute pipeline from command line."""
    parser = argparse.ArgumentParser(
        description="Run a pipeline from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--type",
        required=True,
        help="Pipeline type (individual_extraction, schema_extraction, etc.)",
    )
    parser.add_argument(
        "--implementation",
        default="default",
        help="Implementation identifier (default: 'default')",
    )
    parser.add_argument(
        "--config",
        default="default",
        help="Configuration reference (default: 'default')",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input JSON file path",
    )
    parser.add_argument(
        "--output",
        help="Output JSON file path (omit to print to stdout)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without executing",
    )
    parser.add_argument(
        "--log-iteration",
        action="store_true",
        help="Append execution record to pipeline-iteration-log.md",
    )

    args = parser.parse_args()

    try:
        # Validate pipeline type
        try:
            ptype = PipelineType(args.type)
        except ValueError:
            _logger.error(f"Unknown pipeline type: {args.type}")
            return 1

        _logger.info(f"Pipeline type: {ptype.value}")
        _logger.info(f"Implementation: {args.implementation}")
        _logger.info(f"Configuration: {args.config}")

        # Load input
        input_path = Path(args.input)
        if not input_path.exists():
            _logger.error(f"Input file not found: {input_path}")
            return 1

        with open(input_path) as f:
            input_data = json.load(f)
        _logger.info(f"Loaded input from {input_path}")

        # Initialize registries
        type_registry = PipelineTypeRegistry()
        impl_registry = PipelineImplementationRegistry()
        config_registry = PipelineConfigurationRegistry()

        # Verify pipeline type is registered
        type_def = type_registry.get_type(ptype)
        if type_def is None:
            _logger.error(f"Pipeline type not registered: {ptype.value}")
            return 1

        # Verify implementation is registered
        impl_class = impl_registry.get(ptype, args.implementation)
        if impl_class is None:
            _logger.error(
                f"Implementation not found: {ptype.value}:{args.implementation}"
            )
            return 1
        _logger.info(f"Implementation class: {impl_class.__name__}")

        # Verify configuration is registered
        config_version = config_registry.get_latest(ptype, args.implementation, args.config)
        if config_version is None:
            _logger.error(
                f"Configuration not found: {ptype.value}:{args.implementation}:{args.config}"
            )
            return 1
        _logger.info(f"Configuration version: {config_version.version}")

        # Dry-run: stop here
        if args.dry_run:
            _logger.info("[DRY-RUN] Configuration validated successfully")
            return 0

        # Instantiate and execute implementation
        _logger.info("Instantiating implementation...")
        impl = impl_class(config=config_version.config)

        _logger.info("Executing pipeline...")
        result = impl.execute(input_data)

        # Write output
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            _logger.info(f"Wrote output to {output_path}")
        else:
            # Print to stdout
            print(json.dumps(result, indent=2))

        # Log iteration if requested
        if args.log_iteration:
            _append_iteration_log(
                ptype=ptype,
                impl_id=args.implementation,
                config_ref=args.config,
                input_data=input_data,
                result=result,
                error=None,
            )

        return 0

    except Exception as exc:
        _logger.error(f"Pipeline execution failed: {exc}", exc_info=exc)

        # Log the error if iteration logging is enabled
        if args.log_iteration:
            try:
                _append_iteration_log(
                    ptype=ptype,
                    impl_id=args.implementation,
                    config_ref=args.config,
                    input_data=input_data,
                    result=None,
                    error=str(exc),
                )
            except Exception as log_exc:
                _logger.error(f"Failed to log iteration: {log_exc}")

        return 1


def _append_iteration_log(
    ptype: PipelineType,
    impl_id: str,
    config_ref: str,
    input_data: dict,
    result: dict | None,
    error: str | None,
) -> None:
    """
    Append execution record to pipeline-iteration-log.md.

    Args:
        ptype: Pipeline type
        impl_id: Implementation ID
        config_ref: Configuration reference
        input_data: Input payload
        result: Output payload (None if error occurred)
        error: Error message (None if successful)
    """
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / "pipeline-iteration-log.md"

    # Create header if file doesn't exist
    if not log_path.exists():
        with open(log_path, "w") as f:
            f.write("# Pipeline Iteration Log\n\n")
            f.write("Append-only execution log for pipeline iterations during development.\n")
            f.write("Organized by pipeline type.\n\n")

    # Build entry
    timestamp = datetime.now().isoformat()
    status = "ERROR" if error else "SUCCESS"
    section_header = f"## {ptype.value}"

    entry_parts = [
        f"\n{section_header}\n",
        f"\n**Timestamp:** {timestamp}",
        f"\n**Implementation:** {impl_id}",
        f"\n**Configuration:** {config_ref}",
        f"\n**Status:** {status}\n",
        f"\n### Input\n\n```json\n{json.dumps(input_data, indent=2)}\n```\n",
    ]

    if error:
        entry_parts.append(f"\n### Error\n\n```\n{error}\n```\n")
    elif result:
        entry_parts.append(f"\n### Output\n\n```json\n{json.dumps(result, indent=2)}\n```\n")

    entry_parts.append("\n---\n")

    # Append to log
    with open(log_path, "a") as f:
        f.writelines(entry_parts)

    _logger.info(f"Appended iteration log to {log_path}")


if __name__ == "__main__":
    sys.exit(main())
