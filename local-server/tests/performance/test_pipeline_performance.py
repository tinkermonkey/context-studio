"""Performance tests for LLM pipeline management operations at various scales.

Tests measure pipeline configuration CRUD throughput, execution tracking,
and list operations at multiple configuration counts (10, 50, 100).
"""

import sys
import os
import time
import pytest

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from domain.pipeline.services import PipelineService
from tests.fakes.fake_pipeline_repository import FakePipelineRepository
from tests.fakes.fake_llm_provider import FakeLLMProvider
from tests.fakes.fake_event_publisher import FakeEventPublisher


def _setup_pipeline_context() -> tuple[PipelineService, FakePipelineRepository]:
    """Set up pipeline service with fake dependencies.

    Returns:
        Tuple of (service, repository) for testing
    """
    repository = FakePipelineRepository()
    llm_provider = FakeLLMProvider()
    event_publisher = FakeEventPublisher()
    service = PipelineService(
        pipeline_repo=repository,
        flavor_repo=repository,
        llm=llm_provider,
        event_publisher=event_publisher,
    )
    return service, repository


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_configs,max_time",
    [
        (10, 0.01),
        (50, 0.05),
        (100, 0.1),
    ],
)
def test_bulk_create_pipeline_configs(num_configs: int, max_time: float) -> None:
    """Measure throughput of creating pipeline configurations."""
    service, _ = _setup_pipeline_context()

    start = time.perf_counter()
    for i in range(num_configs):
        service.create_config(
            pipeline=f"pipeline_{i}",
            title=f"Pipeline Config {i}",
            provider="openai",
            model="gpt-4",
            config={"temperature": 0.7},
            system_prompt=f"System prompt {i}",
            user_prompt=f"User template {i}",
        )
    elapsed = time.perf_counter() - start

    print(
        f"\nBulk create pipeline configs ({num_configs} configs): {elapsed:.4f}s ({num_configs / elapsed:.1f} configs/sec)"
    )
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_configs,max_time",
    [
        (10, 0.01),
        (50, 0.05),
        (100, 0.1),
    ],
)
def test_list_pipeline_configs(num_configs: int, max_time: float) -> None:
    """Measure time to list pipeline configurations."""
    service, _ = _setup_pipeline_context()

    # Create configurations
    for i in range(num_configs):
        service.create_config(
            pipeline=f"pipeline_{i}",
            title=f"Pipeline Config {i}",
            provider="openai",
            model="gpt-4",
            config={"temperature": 0.7},
            system_prompt=f"System prompt {i}",
            user_prompt=f"User template {i}",
        )

    start = time.perf_counter()
    configs = service.list_configs()
    elapsed = time.perf_counter() - start

    print(f"\nList pipeline configs ({num_configs} configs): {elapsed:.4f}s")
    assert len(configs) == num_configs
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_configs,max_time",
    [
        (10, 0.01),
        (50, 0.05),
        (100, 0.1),
    ],
)
def test_update_pipeline_configs(num_configs: int, max_time: float) -> None:
    """Measure throughput of updating pipeline configurations."""
    service, _ = _setup_pipeline_context()

    # Create configurations
    config_ids = []
    for i in range(num_configs):
        config = service.create_config(
            pipeline=f"pipeline_{i}",
            title=f"Pipeline Config {i}",
            provider="openai",
            model="gpt-4",
            config={"temperature": 0.7},
            system_prompt=f"System prompt {i}",
            user_prompt=f"User template {i}",
        )
        config_ids.append(config.id)

    start = time.perf_counter()
    for i, config_id in enumerate(config_ids):
        service.update_config(
            config_id,
            title=f"Updated_Pipeline_Config_{i:03d}",
            system_prompt=f"Updated system prompt {i}",
        )
    elapsed = time.perf_counter() - start

    print(
        f"\nUpdate pipeline configs ({num_configs} configs): {elapsed:.4f}s ({num_configs / elapsed:.1f} updates/sec)"
    )
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_configs,num_executions,max_time",
    [
        (5, 20, 0.02),
        (10, 50, 0.1),
    ],
)
def test_execute_pipelines(
    num_configs: int, num_executions: int, max_time: float
) -> None:
    """Measure throughput of executing pipelines."""
    service, _ = _setup_pipeline_context()

    # Create and enable pipeline configurations
    config_ids = []
    for i in range(num_configs):
        config = service.create_config(
            pipeline=f"pipeline_{i}",
            title=f"Pipeline Config {i}",
            provider="openai",
            model="gpt-4",
            config={"temperature": 0.7},
            system_prompt=f"System prompt {i}",
            user_prompt=f"User template {i}",
        )
        config_ids.append(config.id)

    start = time.perf_counter()
    for i in range(num_executions):
        config_id = config_ids[i % num_configs]
        service.execute_pipeline(config_id, f"Input text {i}")
    elapsed = time.perf_counter() - start

    print(
        f"\nExecute pipelines ({num_executions} executions across {num_configs} configs): {elapsed:.4f}s ({num_executions / elapsed:.1f} executions/sec)"
    )
    assert elapsed < max_time


@pytest.mark.performance
@pytest.mark.parametrize(
    "num_configs,max_time",
    [
        (10, 0.02),
        (50, 0.1),
        (100, 0.2),
    ],
)
def test_delete_pipeline_configs(num_configs: int, max_time: float) -> None:
    """Measure throughput of deleting pipeline configurations."""
    service, _ = _setup_pipeline_context()

    # Create configurations
    config_ids = []
    for i in range(num_configs):
        config = service.create_config(
            pipeline=f"pipeline_{i}",
            title=f"Pipeline Config {i}",
            provider="openai",
            model="gpt-4",
            config={"temperature": 0.7},
            system_prompt=f"System prompt {i}",
            user_prompt=f"User template {i}",
        )
        config_ids.append(config.id)

    start = time.perf_counter()
    for config_id in config_ids:
        service.delete_config(config_id)
    elapsed = time.perf_counter() - start

    print(
        f"\nDelete pipeline configs ({num_configs} configs): {elapsed:.4f}s ({num_configs / elapsed:.1f} deletes/sec)"
    )
    assert elapsed < max_time
