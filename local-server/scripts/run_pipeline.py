#!/usr/bin/env python3
"""
Command-line harness for invoking pipelines.

A run is selected as everywhere else (domain/pipelines/selection.py): by
pipeline type, implementation and configuration. An implementation left out is
the type's default; a configuration left out is the implementation's default.
The run's model, temperature and output-token limit are the configuration's
unless the input file names its own.

Usage (from local-server/, venv active):
    python scripts/run_pipeline.py \\
        --type individual_extraction \\
        --input /path/to/input.json \\
        [--implementation find_then_type] \\
        [--configuration extraction-find-then-type] \\
        [--output /path/to/output.json] \\
        [--dry-run] \\
        [--log-iteration <log_path>]

Examples:
    # Run individual extraction with its default implementation and configuration
    python scripts/run_pipeline.py \\
        --type individual_extraction \\
        --input examples/input.json \\
        --output /tmp/output.json \\
        --log-iteration logs/my-iteration-log.md

    # Dry-run: say what would run, and stop
    python scripts/run_pipeline.py \\
        --type individual_extraction \\
        --input examples/input.json \\
        --dry-run

    # Name the implementation and one of its configurations
    python scripts/run_pipeline.py \\
        --type individual_extraction \\
        --implementation default \\
        --configuration extraction-openrouter-default \\
        --input examples/input.json \\
        --output /tmp/output.json
"""

import argparse
import atexit
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

# Add local-server to path so we can import domain modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.embedding.sentence_transformer import SentenceTransformerEmbedding
from adapters.events.in_process import InProcessEventPublisher
from adapters.factories.orchestrator_factory import create_selected_run
from adapters.llm.provider_router import LLMProviderRouter
from adapters.nlp.spacy_processor import SpacyNLPProcessor
from adapters.persistence.sqlite.connection import DatabaseManager
from adapters.persistence.sqlite.extraction_repo import SQLiteExtractionRepository
from adapters.persistence.sqlite.extraction_run_repo import (
    SQLiteExtractionRunRepository,
)
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.reference.conceptnet import ConceptNetSource
from adapters.reference.dbpedia import DBpediaSource
from adapters.reference.grounding import GroundingAdapter
from adapters.reference.proxy import ReferenceProxy
from adapters.reference.schema_org import SchemaOrgSource
from adapters.reference.wikidata import WikidataSource
from config import get_settings
from domain.extraction.ports import ReferenceSource
from domain.extraction.services import ExtractionService
from domain.ontology.ports import OntologyRepository
from domain.pipelines.bootstrap import register_pipelines
from domain.pipelines.entities import PipelineType
from domain.pipelines.exceptions import PipelineSelectionError
from domain.pipelines.registry import (
    PipelineConfigurationRegistry,
    PipelineImplementationRegistry,
    PipelineTypeRegistry,
)
from domain.pipelines.schema_node_grounding.scoring import GroundingScorer
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
        help="Implementation identifier (default: the pipeline type's default implementation)",
    )
    parser.add_argument(
        "--configuration",
        "--config",
        dest="configuration",
        help="Configuration reference (default: the implementation's default configuration)",
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
        type=str,
        default=None,
        help="Append execution record to log file (default: logs/pipeline-iteration-log.md)",
    )

    args = parser.parse_args()

    # Initialize variables with defaults to avoid NameError in exception handler
    ptype = None
    input_data = None
    # What was selected to run, for the iteration log (as named until it is resolved)
    selected = {"implementation": args.implementation, "configuration": args.configuration}

    try:
        # Validate pipeline type
        try:
            ptype = PipelineType(args.type)
        except ValueError:
            _logger.error(f"Unknown pipeline type: {args.type}")
            return 1

        _logger.info(f"Pipeline type: {ptype.value}")

        # Load input
        input_path = Path(args.input)
        if not input_path.exists():
            _logger.error(f"Input file not found: {input_path}")
            return 1

        with open(input_path) as f:
            input_data = json.load(f)
        _logger.info(f"Loaded input from {input_path}")

        # Register the pipelines as the app does, and select what runs: the
        # implementation and configuration named, or the registered defaults
        if PipelineTypeRegistry().get_type(ptype) is None:
            _logger.error(f"Pipeline type not registered: {ptype.value}")
            return 1
        resolver = register_pipelines(
            PipelineImplementationRegistry(), PipelineConfigurationRegistry()
        )
        try:
            selection = resolver.resolve(ptype, args.implementation, args.configuration)
        except PipelineSelectionError as exc:
            _logger.error(str(exc))
            return 1
        selected["implementation"] = selection.implementation_id
        selected["configuration"] = selection.configuration_ref
        config = selection.config
        _logger.info(
            f"Implementation: {selection.implementation_id} ({selection.implementation.__name__})"
        )
        _logger.info(
            f"Configuration: {selection.configuration_ref} v{selection.configuration.version}"
            f" (model {config.get('model')})"
        )

        # Dry-run: stop here
        if args.dry_run:
            _logger.info("[DRY-RUN] Configuration validated successfully")
            return 0

        # Initialize database and services for execution
        _logger.info("Initializing services...")
        db_manager = DatabaseManager()
        db_manager.initialize(
            local_db_url="sqlite:///./local.db",
            operations_db_url="sqlite:///./operations.db",
        )

        # Initialize LLM provider router with configured API keys
        settings = get_settings()
        try:
            llm_provider = LLMProviderRouter(
                openrouter_api_key=settings.llm.openrouter_api_key,
                anthropic_api_key=settings.llm.anthropic_api_key,
                openai_api_key=settings.llm.openai_api_key,
            )
        except ValueError as e:
            _logger.error(
                f"No LLM provider could be initialized: {e}. "
                "Please configure at least one LLM provider API key in config.json "
                "(openrouter_api_key, anthropic_api_key, or openai_api_key)"
            )
            return 1

        # Initialize repositories
        local_session_factory = db_manager.get_local_session_factory()
        ontology_repo = SQLiteOntologyRepository(local_session_factory)
        extraction_repo = SQLiteExtractionRepository(local_session_factory)
        extraction_run_repo = SQLiteExtractionRunRepository(local_session_factory)

        # Create services
        embedding_service = SentenceTransformerEmbedding(model_name="all-MiniLM-L12-v2")
        nlp_processor = SpacyNLPProcessor()
        # Reference calls go through the caching, rate-limiting reference proxy
        reference_proxy = ReferenceProxy(settings.reference.proxy)
        reference_proxy.start()
        atexit.register(reference_proxy.stop)
        conceptnet_source = ConceptNetSource(
            base_url=reference_proxy.base_url("conceptnet"),
            upstream_url=reference_proxy.upstream_url("conceptnet"),
            timeout=settings.reference.conceptnet_timeout,
        )
        dbpedia_source = DBpediaSource(
            base_url=reference_proxy.base_url("dbpedia"),
            upstream_url=reference_proxy.upstream_url("dbpedia"),
        )
        wikidata_source = WikidataSource(
            base_url=reference_proxy.base_url("wikidata"),
            upstream_url=reference_proxy.upstream_url("wikidata"),
        )
        schema_org_source = SchemaOrgSource()
        reference_sources: list[ReferenceSource] = [
            conceptnet_source,
            dbpedia_source,
            wikidata_source,
            schema_org_source,
        ]

        extraction_service = ExtractionService(
            ontology_repo=cast(OntologyRepository, ontology_repo),
            embedding_service=embedding_service,
            llm=llm_provider,
            nlp=nlp_processor,
            reference_sources=reference_sources,
            event_publisher=InProcessEventPublisher(),
            extraction_repo=extraction_repo,
            extraction_run_repo=extraction_run_repo,
        )

        # Prepare services dict for orchestrator factory
        services: dict[str, Any] = {
            "config": config,
            "extraction_service": extraction_service,
            "ontology_repo": ontology_repo,
            "extraction_repo": extraction_repo,
            "grounding_adapter": GroundingAdapter(
                dbpedia=dbpedia_source,
                conceptnet=conceptnet_source,
                wikidata=wikidata_source,
                schema_org=schema_org_source,
            ),
            "scorer": GroundingScorer(embedding_service=embedding_service),
            "grounding_config": {
                "top_n": config.get("top_n", 10),
                "weights": config.get(
                    "weights",
                    {
                        "source_score": 0.3,
                        "label_match": 0.3,
                        "semantic_similarity": 0.4,
                    },
                ),
            },
            "refinement_config": config,
        }

        # Instantiate the implementation and its state: the configuration's
        # model, temperature and output limit, unless the input names its own
        _logger.info("Instantiating implementation...")
        orchestrator, state = create_selected_run(
            selection, llm_provider, services, "script-run", input_data
        )

        _logger.info("Executing pipeline...")
        result_state = asyncio.run(orchestrator.execute(state))

        result = result_state.result or {}

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
        if args.log_iteration is not None:
            _append_iteration_log(
                ptype=ptype,
                impl_id=str(selected["implementation"]),
                config_ref=str(selected["configuration"]),
                input_data=input_data,
                result=result,
                error=None,
                log_path=args.log_iteration,
            )

        return 0

    except Exception as exc:
        _logger.error(f"Pipeline execution failed: {exc}", exc_info=exc)

        # Log the error if iteration logging is enabled and required variables are available
        if args.log_iteration is not None and ptype is not None and input_data is not None:
            try:
                _append_iteration_log(
                    ptype=ptype,
                    impl_id=str(selected["implementation"]),
                    config_ref=str(selected["configuration"]),
                    input_data=input_data,
                    result=None,
                    error=str(exc),
                    log_path=args.log_iteration,
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
    log_path: str | None = None,
) -> None:
    """
    Append execution record to the iteration log.

    Args:
        ptype: Pipeline type
        impl_id: Implementation ID
        config_ref: Configuration reference
        input_data: Input payload
        result: Output payload (None if error occurred)
        error: Error message (None if successful)
        log_path: Path to log file (default: logs/pipeline-iteration-log.md)
    """
    if log_path is None:
        log_path = str(Path(__file__).parent.parent / "logs" / "pipeline-iteration-log.md")

    log_path_obj = Path(log_path)
    log_path_obj.parent.mkdir(parents=True, exist_ok=True)

    # Create header if file doesn't exist
    if not log_path_obj.exists():
        with open(log_path_obj, "w") as f:
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
    with open(log_path_obj, "a") as f:
        f.writelines(entry_parts)

    _logger.info(f"Appended iteration log to {log_path_obj}")


if __name__ == "__main__":
    sys.exit(main())
