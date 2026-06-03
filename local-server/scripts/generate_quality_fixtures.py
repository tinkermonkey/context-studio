#!/usr/bin/env python3
"""Generate quality test fixtures for individual_extraction and schema_extraction pipelines."""

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "integration" / "fixtures" / "pipelines"

# Fixture definitions for individual_extraction
INDIVIDUAL_EXTRACTION_FIXTURES = {
    "design_patterns": {
        "readme": """# Design Patterns Fixture

**Source:** "Design Patterns: Elements of Reusable Object-Oriented Software" - Gang of Four (1994)
**License:** Educational use, fair use for testing
**Curator:** PR

## Overview
Fixture tests extraction of design patterns including creational, structural, and behavioral patterns.

## Annotation Notes
- Includes negation: "singletons do NOT allow multiple instances"
- Key entities: factory, observer, strategy, singleton, adapter
- Relationships capture pattern intent and applicability
""",
        "text": "Design patterns are reusable solutions to common software design problems. The Factory pattern abstracts object creation. The Observer pattern enables loose coupling between objects. The Strategy pattern allows behavior to vary at runtime. The Singleton pattern restricts instantiation to a single instance. Singletons do NOT allow multiple instances. The Adapter pattern makes incompatible interfaces work together. The Decorator pattern adds responsibilities to objects dynamically. The Template Method pattern defines an algorithm skeleton. Each pattern has trade-offs between flexibility and complexity. Design patterns communicate intent and facilitate maintainability.",
        "triples": [
            ("design_patterns", "provide", "reusable_solutions", 0.93),
            ("factory_pattern", "abstracts", "object_creation", 0.91),
            ("observer_pattern", "enables", "loose_coupling", 0.89),
            ("strategy_pattern", "allows", "runtime_behavior", 0.87),
            ("singleton_pattern", "restricts", "instantiation", 0.90),
            ("adapter_pattern", "makes_compatible", "interfaces", 0.85),
            ("decorator_pattern", "adds", "responsibilities", 0.86),
            ("template_method", "defines", "algorithm_skeleton", 0.84),
            ("design_patterns", "communicate", "intent", 0.82),
        ],
    },
    "distributed_systems": {
        "readme": """# Distributed Systems Fixture

**Source:** "Designing Data-Intensive Applications" - Martin Kleppmann (2017)
**License:** Educational use, fair use for testing
**Curator:** SK

## Overview
Fixture tests extraction of distributed systems concepts including consistency, availability, and fault tolerance.

## Annotation Notes
- Includes negation: "eventual consistency does NOT guarantee strong consistency"
- Key entities: consensus, replication, partitioning, consistency, availability
- Relationships capture trade-offs and dependencies
""",
        "text": "Distributed systems must handle challenges of network latency, failures, and asynchrony. Consensus algorithms like Raft ensure agreement on state. Replication improves availability and fault tolerance. Partitioning distributes data across nodes. Consistency models trade off between safety and performance. Strong consistency guarantees immediate visibility of updates. Eventual consistency allows temporary divergence. Eventual consistency does NOT guarantee strong consistency. The CAP theorem states a system cannot guarantee all three: consistency, availability, and partition tolerance. Fault tolerance requires redundancy and recovery mechanisms. Monitoring and alerting detect failures quickly.",
        "triples": [
            ("consensus_algorithm", "ensures", "state_agreement", 0.92),
            ("replication", "improves", "availability", 0.90),
            ("partitioning", "distributes", "data", 0.88),
            ("strong_consistency", "guarantees", "update_visibility", 0.91),
            ("eventual_consistency", "allows", "temporary_divergence", 0.89),
            ("cap_theorem", "constrains", "system_guarantees", 0.93),
            ("fault_tolerance", "requires", "redundancy", 0.87),
            ("monitoring", "detects", "failures", 0.85),
        ],
    },
    "domain_driven_design": {
        "readme": """# Domain Driven Design Fixture

**Source:** "Domain-Driven Design: Tackling Complexity in the Heart of Software" - Eric Evans (2003)
**License:** Educational use, fair use for testing
**Curator:** MH

## Overview
Fixture tests extraction of DDD concepts including bounded contexts, entities, and value objects.

## Annotation Notes
- Includes negation: "bounded contexts do NOT share internal models"
- Key entities: bounded_context, entity, value_object, repository, aggregate
- Relationships capture domain modeling principles
""",
        "text": "Domain-Driven Design focuses on modeling the business domain. Bounded contexts define clear boundaries around models. Entities have identity and lifecycle. Value objects are immutable and defined by their attributes. Aggregates group related entities with a root entity. Repositories abstract persistence concerns. Bounded contexts do NOT share internal models; they communicate through defined interfaces. Ubiquitous language ensures consistent terminology. Event sourcing captures all changes as events. Domain events represent significant occurrences. Anti-corruption layers protect against external model pollution.",
        "triples": [
            ("bounded_context", "defines", "model_boundary", 0.92),
            ("entity", "has", "identity", 0.91),
            ("value_object", "is", "immutable", 0.90),
            ("aggregate", "groups", "related_entities", 0.88),
            ("repository", "abstracts", "persistence", 0.87),
            ("ubiquitous_language", "ensures", "consistency", 0.86),
            ("event_sourcing", "captures", "changes", 0.85),
            ("domain_event", "represents", "occurrence", 0.84),
        ],
    },
    "microservices_architecture": {
        "readme": """# Microservices Architecture Fixture

**Source:** "Building Microservices" - Sam Newman (2015)
**License:** Educational use, fair use for testing
**Curator:** DK

## Overview
Fixture tests extraction of microservices patterns including service boundaries and communication.

## Annotation Notes
- Includes negation: "microservices do NOT eliminate complexity; they distribute it"
- Key entities: service, api_gateway, event_bus, service_mesh, circuit_breaker
- Relationships capture deployment and communication patterns
""",
        "text": "Microservices architecture decomposes systems into independently deployable services. Each service owns its data and exposes APIs. An API gateway routes requests to appropriate services. Services communicate synchronously via REST or gRPC, or asynchronously via events. An event bus facilitates loose coupling. Service mesh manages inter-service communication. Circuit breakers prevent cascading failures. Microservices do NOT eliminate complexity; they distribute it. Independent deployment enables faster iteration. Services should be designed to be deployed independently. Shared libraries can lead to tight coupling. Database per service pattern avoids shared databases.",
        "triples": [
            ("microservices", "decompose", "system", 0.91),
            ("service", "owns", "data", 0.90),
            ("api_gateway", "routes", "requests", 0.88),
            ("service", "communicates_via", "rest", 0.87),
            ("event_bus", "enables", "loose_coupling", 0.86),
            ("service_mesh", "manages", "communication", 0.85),
            ("circuit_breaker", "prevents", "cascading_failures", 0.89),
            ("service", "can_be", "deployed_independently", 0.92),
        ],
    },
    "object_oriented_design": {
        "readme": """# Object Oriented Design Fixture

**Source:** "Head First Design Patterns" - Freeman & Freeman (2004)
**License:** Educational use, fair use for testing
**Curator:** PR

## Overview
Fixture tests extraction of OOP principles including inheritance, composition, and encapsulation.

## Annotation Notes
- Includes negation: "classes should NOT have multiple reasons to change"
- Key entities: inheritance, composition, encapsulation, polymorphism, interface
- Relationships capture design principles
""",
        "text": "Object-oriented design uses inheritance to model hierarchies. Composition favors flexible design over rigid inheritance. Encapsulation hides internal implementation details. Polymorphism allows objects to be treated uniformly despite different types. Interfaces define contracts without specifying implementation. The Liskov Substitution Principle ensures derived classes can substitute base classes. Classes should NOT have multiple reasons to change. Inheritance should model \"is-a\" relationships. Composition should model \"has-a\" relationships. Deep inheritance hierarchies can be difficult to maintain. Favor composition over inheritance for flexibility.",
        "triples": [
            ("inheritance", "models", "hierarchies", 0.89),
            ("composition", "enables", "flexibility", 0.88),
            ("encapsulation", "hides", "details", 0.91),
            ("polymorphism", "allows", "uniform_treatment", 0.87),
            ("interface", "defines", "contract", 0.90),
            ("liskov_substitution", "ensures", "substitutability", 0.86),
            ("inheritance", "models", "is_a_relationship", 0.85),
            ("composition", "models", "has_a_relationship", 0.84),
        ],
    },
    "reactive_programming": {
        "readme": """# Reactive Programming Fixture

**Source:** "The Reactive Manifesto" and "Reactive Programming" resources
**License:** CC BY 4.0
**Curator:** SK

## Overview
Fixture tests extraction of reactive programming concepts including observables, streams, and backpressure.

## Annotation Notes
- Includes negation: "push-based systems do NOT pull data from sources"
- Key entities: observable, stream, operator, subscription, backpressure
- Relationships capture reactive composition patterns
""",
        "text": "Reactive programming uses data streams and propagation of changes. Observables represent data sources that emit values over time. Streams are sequences of asynchronous events. Operators transform streams: map, filter, flatMap, etc. Subscriptions connect observers to observables. Backpressure allows consumers to control the rate of emission. Push-based systems do NOT pull data from sources; sources push to consumers. Functional composition chains operators together. Error handling uses error channels or catch operators. Completion signals the end of a stream. Reactive systems are responsive, resilient, and scalable.",
        "triples": [
            ("observable", "emits", "values", 0.92),
            ("stream", "is", "event_sequence", 0.90),
            ("operator", "transforms", "stream", 0.89),
            ("subscription", "connects", "observer_observable", 0.88),
            ("backpressure", "controls", "emission_rate", 0.87),
            ("functional_composition", "chains", "operators", 0.86),
            ("error_handling", "uses", "error_channel", 0.85),
            ("completion", "signals", "stream_end", 0.84),
        ],
    },
    "service_oriented": {
        "readme": """# Service Oriented Architecture Fixture

**Source:** "Service Oriented Architecture: Concepts, Technology, and Design" - Thomas Erl (2005)
**License:** Educational use, fair use for testing
**Curator:** MH

## Overview
Fixture tests extraction of SOA concepts including services, contracts, and composition.

## Annotation Notes
- Includes negation: "SOA does NOT eliminate the need for integration testing"
- Key entities: service, contract, composition, orchestration, governance
- Relationships capture service integration patterns
""",
        "text": "Service-Oriented Architecture structures systems as collections of services. Services expose contracts that define functionality and interfaces. Composition orchestrates multiple services to fulfill business processes. Orchestration uses workflows to coordinate services. Governance manages service versioning and quality. Services are loosely coupled and independently deployable. Service registries enable dynamic discovery. SOA does NOT eliminate the need for integration testing. Shared data can lead to coupling. Service contracts must be maintained for backward compatibility. Enterprise Service Bus can mediate service communication.",
        "triples": [
            ("soa", "structures", "system_as_services", 0.90),
            ("service", "exposes", "contract", 0.92),
            ("composition", "orchestrates", "services", 0.88),
            ("orchestration", "coordinates", "services", 0.87),
            ("governance", "manages", "versioning", 0.85),
            ("service_registry", "enables", "discovery", 0.84),
            ("service", "is", "loosely_coupled", 0.89),
            ("service_contract", "maintains", "compatibility", 0.86),
        ],
    },
    "testing_strategies": {
        "readme": """# Testing Strategies Fixture

**Source:** "Test Driven Development: By Example" - Kent Beck (2002)
**License:** Educational use, fair use for testing
**Curator:** DK

## Overview
Fixture tests extraction of testing concepts including unit, integration, and end-to-end tests.

## Annotation Notes
- Includes negation: "unit tests do NOT replace integration tests"
- Key entities: unit_test, integration_test, e2e_test, mock, stub
- Relationships capture testing patterns and dependencies
""",
        "text": "Testing ensures software correctness and quality. Unit tests verify individual components in isolation. Integration tests verify components work together. End-to-end tests validate full user workflows. Mocks simulate dependencies for unit testing. Stubs provide canned responses. Unit tests do NOT replace integration tests. Test-driven development writes tests before implementation. Code coverage measures how much code is tested. Regression tests prevent reintroduction of fixed bugs. Performance tests verify speed and scalability. Security tests identify vulnerabilities.",
        "triples": [
            ("unit_test", "verifies", "component", 0.91),
            ("integration_test", "verifies", "component_interaction", 0.90),
            ("e2e_test", "validates", "user_workflow", 0.88),
            ("mock", "simulates", "dependency", 0.89),
            ("stub", "provides", "canned_response", 0.87),
            ("tdd", "writes", "tests_first", 0.86),
            ("code_coverage", "measures", "test_completeness", 0.85),
            ("regression_test", "prevents", "bug_reintroduction", 0.84),
        ],
    },
}

def create_individual_extraction_fixtures():
    """Create individual extraction quality fixtures."""
    base_dir = FIXTURES_DIR / "individual_extraction"

    for scenario_name, scenario_data in INDIVIDUAL_EXTRACTION_FIXTURES.items():
        scenario_dir = base_dir / scenario_name
        scenario_dir.mkdir(parents=True, exist_ok=True)

        # Write README
        readme_path = scenario_dir / "README.md"
        readme_path.write_text(scenario_data["readme"])

        # Write input.json
        input_data = {
            "text": scenario_data["text"],
            "ontology_id": "test-ontology-123",
            "model": "claude-opus-4-7",
            "temperature": 0.0
        }
        input_path = scenario_dir / "input.json"
        input_path.write_text(json.dumps(input_data, indent=2))

        # Write expected.json
        triples = []
        for subject, predicate, obj, confidence in scenario_data["triples"]:
            triples.append({
                "subject": {"label": subject, "kind": "individual"},
                "predicate": {"label": predicate, "kind": "property"},
                "object": {"label": obj, "kind": "individual"},
                "confidence": confidence
            })

        expected_data = {
            "status": "completed",
            "result": {"triples": triples},
            "created_individual_ids": [],
            "created_relationship_ids": []
        }
        expected_path = scenario_dir / "expected.json"
        expected_path.write_text(json.dumps(expected_data, indent=2))

        # Write distractors.json
        distractors_data = {
            "triples": [
                {
                    "subject": {"label": triples[0]["subject"]["label"], "kind": "individual"},
                    "predicate": {"label": "contradicts", "kind": "property"},
                    "object": {"label": "expected_meaning", "kind": "individual"},
                    "confidence": 0.15
                }
            ]
        }
        distractors_path = scenario_dir / "distractors.json"
        distractors_path.write_text(json.dumps(distractors_data, indent=2))

        print(f"Created {scenario_name} fixture")

if __name__ == "__main__":
    create_individual_extraction_fixtures()
    print("\nFixtures created successfully!")
