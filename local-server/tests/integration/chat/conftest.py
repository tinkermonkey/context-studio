"""
Shared fixtures for chat integration tests: a small workspace shaped like the
Documentation Robotics (DR) model, stored in real SQLite databases.

Shape: taxonomy "Documentation Robotics" -> layer schemes (API Layer, Business
Layer) -> classes (Operation, Business Service) -> individuals (Admin Health,
Health Monitoring) connected by a DR-style relationship type
("api.operation realizes business.service").
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from adapters.graph.networkx_engine import NetworkXGraphEngine
from adapters.graph.rdflib_engine import RDFLibQueryEngine
from adapters.persistence.sqlite.change_repo import SQLiteChangeRepository
from adapters.persistence.sqlite.chat_repo import SqliteConversationRepository
from adapters.persistence.sqlite.connection import (
    create_local_db_engine,
    create_operations_db_engine,
    create_session_factory,
)
from adapters.persistence.sqlite.models import Base
from adapters.persistence.sqlite.ontology_repo import SQLiteOntologyRepository
from adapters.persistence.sqlite.operations.models import OperationsBase
from adapters.persistence.sqlite.proposal_repo import SQLiteChangeProposalRepository
from domain.graph.services import GraphAnalysisService
from domain.ontology.entities import (
    Class,
    ConceptScheme,
    Individual,
    PropertyDefinition,
    Relationship,
    Taxonomy,
)
from domain.ontology.services import OntologyService
from domain.versioning.proposal_service import ProposalService
from domain.versioning.revert_service import RevertService
from tests.fakes.fake_approval_policy_repository import FakeApprovalPolicyRepository
from tests.fakes.fake_embedding_service import FakeEmbeddingService
from tests.fakes.fake_event_publisher import FakeEventPublisher

TAXONOMY_ID = "a0000000-0000-4000-8000-000000000001"
API_SCHEME_ID = "a0000000-0000-4000-8000-000000000002"
BUSINESS_SCHEME_ID = "a0000000-0000-4000-8000-000000000003"
OPERATION_ID = "a0000000-0000-4000-8000-000000000004"
SERVICE_CLASS_ID = "a0000000-0000-4000-8000-000000000005"
ADMIN_HEALTH_ID = "a0000000-0000-4000-8000-000000000006"
HEALTH_MONITORING_ID = "a0000000-0000-4000-8000-000000000007"
REALIZES_ID = "a0000000-0000-4000-8000-000000000008"
RELATIONSHIP_ID = "a0000000-0000-4000-8000-000000000009"
LIST_CLASSES_ID = "a0000000-0000-4000-8000-00000000000a"
DR_VISION = (
    "# Design charter\n\nAn element is a named architectural fact a maintainer would point to."
)


@dataclass
class DrWorkspace:
    session_factory: sessionmaker
    repository: SQLiteOntologyRepository
    ontology: OntologyService
    graph: GraphAnalysisService
    conversations: SqliteConversationRepository


@pytest.fixture
def dr_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        local_engine = create_local_db_engine(f"sqlite:///{Path(tmpdir) / 'local.db'}")
        ops_engine = create_operations_db_engine(f"sqlite:///{Path(tmpdir) / 'operations.db'}")
        Base.metadata.create_all(local_engine)
        OperationsBase.metadata.create_all(ops_engine)
        session_factory = create_session_factory(local_engine)
        repository = SQLiteOntologyRepository(session_factory)

        repository.save_taxonomy(
            Taxonomy(
                id=TAXONOMY_ID,
                title="Documentation Robotics",
                identifier="dr_spec",
                description="Architecture model layers",
                vision=DR_VISION,
            )
        )
        for scheme_id, title, identifier in (
            (API_SCHEME_ID, "API Layer", "api"),
            (BUSINESS_SCHEME_ID, "Business Layer", "business"),
        ):
            repository.save_concept_scheme(
                ConceptScheme(
                    id=scheme_id, taxonomy_id=TAXONOMY_ID, title=title, identifier=identifier
                )
            )
        repository.save_class(
            Class(
                id=OPERATION_ID,
                concept_scheme_id=API_SCHEME_ID,
                taxonomy_id=TAXONOMY_ID,
                title="Operation",
                identifier="operation",
                description="An API operation (endpoint + method)",
            )
        )
        repository.save_class(
            Class(
                id=SERVICE_CLASS_ID,
                concept_scheme_id=BUSINESS_SCHEME_ID,
                taxonomy_id=TAXONOMY_ID,
                title="Business Service",
                identifier="business_service",
            )
        )
        repository.save_property_definition(
            PropertyDefinition(
                id=REALIZES_ID,
                identifier="operation_realizes_service",
                title="api.operation realizes business.service",
                domain_class_id=OPERATION_ID,
                range_class_id=SERVICE_CLASS_ID,
            )
        )
        for individual_id, title, class_id in (
            (ADMIN_HEALTH_ID, "Admin Health", OPERATION_ID),
            (LIST_CLASSES_ID, "List Classes", OPERATION_ID),
            (HEALTH_MONITORING_ID, "Health Monitoring", SERVICE_CLASS_ID),
        ):
            repository.save_individual(
                Individual(id=individual_id, class_ids=[class_id], title=title)
            )
        repository.save_relationship(
            Relationship(
                id=RELATIONSHIP_ID,
                source_id=ADMIN_HEALTH_ID,
                target_id=HEALTH_MONITORING_ID,
                property_definition_id=REALIZES_ID,
            )
        )

        ontology = OntologyService(
            repository=repository,
            embedding_service=FakeEmbeddingService(),
            event_publisher=FakeEventPublisher(),
        )
        graph = GraphAnalysisService(
            repository=repository,
            graph_engine=NetworkXGraphEngine(),
            query_engine=RDFLibQueryEngine(),
        )
        yield DrWorkspace(
            session_factory=session_factory,
            repository=repository,
            ontology=ontology,
            graph=graph,
            conversations=SqliteConversationRepository(create_session_factory(ops_engine)),
        )
        local_engine.dispose()
        ops_engine.dispose()


@dataclass
class Proposals:
    service: ProposalService
    policies: FakeApprovalPolicyRepository


@pytest.fixture
def proposals(dr_workspace):
    """A ProposalService over the DR workspace; set a policy in `policies` to auto-apply."""
    policies = FakeApprovalPolicyRepository()
    service = ProposalService(
        SQLiteChangeProposalRepository(dr_workspace.session_factory),
        dr_workspace.ontology,
        dr_workspace.repository,
        RevertService(
            SQLiteChangeRepository(dr_workspace.session_factory), dr_workspace.repository
        ),
        approval_policies=policies,
    )
    return Proposals(service=service, policies=policies)
