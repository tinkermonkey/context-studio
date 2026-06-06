#!/usr/bin/env python3
"""Generate quality test fixtures for schema_extraction pipeline."""

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "integration" / "fixtures" / "pipelines"

# Fixture definitions for schema_extraction
SCHEMA_EXTRACTION_FIXTURES = {
    "async_patterns": {
        "readme": (
            """# Async Patterns Schema Fixture

**Source:** "Asynchronous Programming in Python" - Real Python article series (2023)
**License:** CC BY-NC-SA 3.0
**Curator:** MH

## Overview
Fixture tests extraction of async programming schema including concepts, types, and relationships.

## Annotation Notes
- Includes off-topic paragraph testing noise resistance
- Key classes: Coroutine, EventLoop, Task, Future, Callback
- Expected properties: manages, awaits, enables, handles
- Connection relationships: Task-EventLoop, Future-Task, Coroutine-EventLoop
"""
        ),
        "text": (
            "Asynchronous programming allows a program to perform tasks without"
            + "blocking execution. The async/await syntax in Python provides a"
            + "clean way to write coroutines. An event loop manages the execution"
            + "of tasks and futures. When a coroutine awaits another coroutine,"
            + "control returns to the event loop. Multiple tasks can be gathered"
            + "together using asyncio.gather. Callbacks are registered with tasks"
            + "to handle completion. A future represents a value that may not be"
            + "available yet but will be eventually. To prepare for dessert after"
            + "dinner, ensure the kitchen is clean and ready. Event loops do NOT"
            + "run tasks in parallel threads. The event loop continuously polls"
            + "tasks for readiness."
        ),
        "expected_classes": [
            "Coroutine",
            "EventLoop",
            "Task",
            "Future",
            "Callback",
            "Gather",
        ],
        "expected_properties": [
            "manages",
            "awaits",
            "enables",
            "handles",
            "polls",
            "awaits",
        ],
        "expected_connections": [
            ("EventLoop", "manages", "Task"),
            ("Task", "awaits", "Coroutine"),
            ("Future", "represents", "Value"),
            ("Callback", "handles", "Completion"),
        ],
    },
    "clean_code": {
        "readme": (
            """# Clean Code Schema Fixture

**Source:** "Clean Code: A Handbook of Agile Software Craftsmanship" - Robert C. Martin (2008)
**License:** Educational use, fair use for testing
**Curator:** DK

## Overview
Fixture tests extraction of code design schema.

## Annotation Notes
- Key classes: Function, Class, Comment, Method, Variable
- Expected properties: defines, implements, extends, encapsulates
- Connection relationships capture design hierarchies
"""
        ),
        "text": (
            "Clean code is readable and maintainable code. Functions should be"
            + "small and focused on a single responsibility. Classes should follow"
            + "the Single Responsibility Principle. Meaningful names are crucial"
            + "for code comprehension. Comments should explain why, not what."
            + "Methods implement class behavior. Variables store state. Meaningful"
            + "names do NOT consist of random characters or abbreviations."
        ),
        "expected_classes": [
            "Function",
            "Class",
            "Comment",
            "Variable",
            "Method",
            "Responsibility",
        ],
        "expected_properties": [
            "defines",
            "implements",
            "extends",
            "encapsulates",
            "documents",
        ],
        "expected_connections": [
            ("Class", "contains", "Method"),
            ("Function", "defines", "Behavior"),
            ("Comment", "explains", "Intent"),
        ],
    },
    "design_patterns": {
        "readme": (
            """# Design Patterns Schema Fixture

**Source:** "Design Patterns: Elements of Reusable Object-Oriented Software" - Gang of Four (1994)
**License:** Educational use, fair use for testing
**Curator:** PR

## Overview
Fixture tests extraction of design pattern taxonomy and relationships.

## Annotation Notes
- Key classes: Pattern, CreationalPattern, StructuralPattern, BehavioralPattern
- Expected properties: categorizes, solves, implements
"""
        ),
        "text": (
            "Design patterns are reusable solutions to common software design"
            + "problems. The Factory pattern abstracts object creation. The"
            + "Observer pattern enables loose coupling between objects. The"
            + "Strategy pattern allows behavior to vary at runtime. The Singleton"
            + "pattern restricts instantiation to a single instance. Creational"
            + "patterns deal with object creation. Structural patterns deal with"
            + "object composition. Behavioral patterns focus on communication"
            + "between objects."
        ),
        "expected_classes": [
            "DesignPattern",
            "CreationalPattern",
            "StructuralPattern",
            "BehavioralPattern",
            "Factory",
            "Observer",
            "Strategy",
        ],
        "expected_properties": ["categorizes", "solves", "abstracts", "enables"],
        "expected_connections": [
            ("Factory", "is_a", "CreationalPattern"),
            ("Observer", "is_a", "BehavioralPattern"),
            ("Strategy", "is_a", "BehavioralPattern"),
        ],
    },
    "distributed_systems": {
        "readme": (
            """# Distributed Systems Schema Fixture

**Source:** "Designing Data-Intensive Applications" - Martin Kleppmann (2017)
**License:** Educational use, fair use for testing
**Curator:** SK

## Overview
Fixture tests extraction of distributed systems concepts and trade-offs.

## Annotation Notes
- Key classes: ConsensusAlgorithm, ReplicationStrategy, ConsistencyModel, Availability
- Expected properties: ensures, improves, constrains
"""
        ),
        "text": (
            "Distributed systems must handle challenges of network latency,"
            + "failures, and asynchrony. Consensus algorithms like Raft ensure"
            + "agreement on state. Replication improves availability and fault"
            + "tolerance. Partitioning distributes data across nodes. Consistency"
            + "models trade off between safety and performance. Strong consistency"
            + "guarantees immediate visibility of updates. Eventual consistency"
            + "allows temporary divergence."
        ),
        "expected_classes": [
            "ConsensusAlgorithm",
            "Replication",
            "ConsistencyModel",
            "StrongConsistency",
            "EventualConsistency",
            "Partition",
        ],
        "expected_properties": ["ensures", "improves", "allows", "guarantees"],
        "expected_connections": [
            ("StrongConsistency", "is_a", "ConsistencyModel"),
            ("EventualConsistency", "is_a", "ConsistencyModel"),
            ("Consensus", "achieves", "Agreement"),
        ],
    },
    "domain_driven_design": {
        "readme": (
            """# Domain Driven Design Schema Fixture

**Source:** "Domain-Driven Design: Tackling Complexity in the Heart of Software" - Eric Evans (2003)
**License:** Educational use, fair use for testing
**Curator:** MH

## Overview
Fixture tests extraction of DDD building blocks and relationships.

## Annotation Notes
- Key classes: BoundedContext, Entity, ValueObject, Aggregate, Repository
- Expected properties: defines, contains, protects
"""
        ),
        "text": (
            "Domain-Driven Design focuses on modeling the business domain. Bounded"
            + "contexts define clear boundaries around models. Entities have"
            + "identity and lifecycle. Value objects are immutable and defined by"
            + "their attributes. Aggregates group related entities with a root"
            + "entity. Repositories abstract persistence concerns. Ubiquitous"
            + "language ensures consistent terminology."
        ),
        "expected_classes": [
            "BoundedContext",
            "Entity",
            "ValueObject",
            "Aggregate",
            "Repository",
            "UbiquitousLanguage",
        ],
        "expected_properties": [
            "defines",
            "contains",
            "protects",
            "abstracts",
            "groups",
        ],
        "expected_connections": [
            ("Aggregate", "contains", "Entity"),
            ("Repository", "manages", "Aggregate"),
            ("BoundedContext", "uses", "UbiquitousLanguage"),
        ],
    },
    "microservices_architecture": {
        "readme": (
            """# Microservices Architecture Schema Fixture

**Source:** "Building Microservices" - Sam Newman (2015)
**License:** Educational use, fair use for testing
**Curator:** DK

## Overview
Fixture tests extraction of microservices architecture patterns.

## Annotation Notes
- Key classes: Microservice, APIGateway, EventBus, ServiceMesh, CircuitBreaker
- Expected properties: routes, facilitates, manages, prevents
"""
        ),
        "text": (
            "Microservices architecture decomposes systems into independently"
            + "deployable services. Each service owns its data and exposes APIs. An"
            + "API gateway routes requests to appropriate services. Services"
            + "communicate synchronously via REST or gRPC, or asynchronously via"
            + "events. An event bus facilitates loose coupling. Service mesh"
            + "manages inter-service communication. Circuit breakers prevent"
            + "cascading failures."
        ),
        "expected_classes": [
            "Microservice",
            "APIGateway",
            "EventBus",
            "ServiceMesh",
            "CircuitBreaker",
            "RESTInterface",
        ],
        "expected_properties": ["routes", "facilitates", "manages", "prevents", "owns"],
        "expected_connections": [
            ("APIGateway", "routes_to", "Microservice"),
            ("Microservice", "communicates_via", "EventBus"),
            ("CircuitBreaker", "protects", "Microservice"),
        ],
    },
    "object_oriented_design": {
        "readme": (
            """# Object Oriented Design Schema Fixture

**Source:** "Head First Design Patterns" - Freeman & Freeman (2004)
**License:** Educational use, fair use for testing
**Curator:** PR

## Overview
Fixture tests extraction of OOP principles and relationships.

## Annotation Notes
- Key classes: Inheritance, Composition, Encapsulation, Polymorphism, Interface
- Expected properties: models, enables, hides, allows
"""
        ),
        "text": (
            "Object-oriented design uses inheritance to model hierarchies."
            + "Composition favors flexible design over rigid inheritance."
            + "Encapsulation hides internal implementation details. Polymorphism"
            + "allows objects to be treated uniformly despite different types."
            + "Interfaces define contracts without specifying implementation. The"
            + "Liskov Substitution Principle ensures derived classes can substitute"
            + "base classes."
        ),
        "expected_classes": [
            "Inheritance",
            "Composition",
            "Encapsulation",
            "Polymorphism",
            "Interface",
            "LiskovSubstitution",
        ],
        "expected_properties": ["models", "enables", "hides", "allows", "defines"],
        "expected_connections": [
            ("Inheritance", "models", "Hierarchy"),
            ("Composition", "enables", "Flexibility"),
            ("Interface", "defines", "Contract"),
        ],
    },
    "reactive_programming": {
        "readme": (
            """# Reactive Programming Schema Fixture

**Source:** "The Reactive Manifesto" and "Reactive Programming" resources
**License:** CC BY 4.0
**Curator:** SK

## Overview
Fixture tests extraction of reactive programming concepts.

## Annotation Notes
- Key classes: Observable, Stream, Operator, Subscription, Backpressure
- Expected properties: emits, transforms, controls
"""
        ),
        "text": (
            "Reactive programming uses data streams and propagation of changes."
            + "Observables represent data sources that emit values over time."
            + "Streams are sequences of asynchronous events. Operators transform"
            + "streams: map, filter, flatMap, etc. Subscriptions connect observers"
            + "to observables. Backpressure allows consumers to control the rate of"
            + "emission."
        ),
        "expected_classes": [
            "Observable",
            "Stream",
            "Operator",
            "Subscription",
            "Backpressure",
            "Observer",
        ],
        "expected_properties": [
            "emits",
            "transforms",
            "connects",
            "controls",
            "propagates",
        ],
        "expected_connections": [
            ("Observable", "emits", "Stream"),
            ("Operator", "transforms", "Stream"),
            ("Subscription", "connects", "Observer"),
        ],
    },
    "service_oriented": {
        "readme": (
            """# Service Oriented Architecture Schema Fixture

**Source:** "Service Oriented Architecture: Concepts, Technology, and Design" - Thomas Erl (2005)
**License:** Educational use, fair use for testing
**Curator:** MH

## Overview
Fixture tests extraction of SOA concepts and relationships.

## Annotation Notes
- Key classes: Service, Contract, Composition, Orchestration, Governance
- Expected properties: exposes, orchestrates, manages
"""
        ),
        "text": (
            "Service-Oriented Architecture structures systems as collections of"
            + "services. Services expose contracts that define functionality and"
            + "interfaces. Composition orchestrates multiple services to fulfill"
            + "business processes. Orchestration uses workflows to coordinate"
            + "services. Governance manages service versioning and quality."
            + "Services are loosely coupled and independently deployable."
        ),
        "expected_classes": [
            "Service",
            "Contract",
            "Composition",
            "Orchestration",
            "Governance",
            "ServiceRegistry",
        ],
        "expected_properties": ["exposes", "orchestrates", "manages", "coordinates"],
        "expected_connections": [
            ("Service", "exposes", "Contract"),
            ("Composition", "orchestrates", "Service"),
            ("ServiceRegistry", "enables", "Discovery"),
        ],
    },
    "testing_strategies": {
        "readme": (
            """# Testing Strategies Schema Fixture

**Source:** "Test Driven Development: By Example" - Kent Beck (2002)
**License:** Educational use, fair use for testing
**Curator:** DK

## Overview
Fixture tests extraction of testing concepts and taxonomy.

## Annotation Notes
- Key classes: UnitTest, IntegrationTest, E2ETest, Mock, Stub
- Expected properties: verifies, validates, simulates
"""
        ),
        "text": (
            "Testing ensures software correctness and quality. Unit tests verify"
            + "individual components in isolation. Integration tests verify"
            + "components work together. End-to-end tests validate full user"
            + "workflows. Mocks simulate dependencies for unit testing. Stubs"
            + "provide canned responses. Test-driven development writes tests"
            + "before implementation. Code coverage measures how much code is"
            + "tested."
        ),
        "expected_classes": [
            "UnitTest",
            "IntegrationTest",
            "E2ETest",
            "Mock",
            "Stub",
            "CodeCoverage",
        ],
        "expected_properties": [
            "verifies",
            "validates",
            "simulates",
            "provides",
            "measures",
        ],
        "expected_connections": [
            ("UnitTest", "verifies", "Component"),
            ("IntegrationTest", "verifies", "Interaction"),
            ("Mock", "simulates", "Dependency"),
        ],
    },
}


def create_schema_extraction_fixtures():
    """Create schema extraction quality fixtures."""
    base_dir = FIXTURES_DIR / "schema_extraction"

    for scenario_name, scenario_data in SCHEMA_EXTRACTION_FIXTURES.items():
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
            "temperature": 0.0,
        }
        input_path = scenario_dir / "input.json"
        input_path.write_text(json.dumps(input_data, indent=2))

        # Write expected.json
        classes = [{"label": c, "confidence": 0.85} for c in scenario_data["expected_classes"]]
        properties = [
            {"label": p, "confidence": 0.80} for p in scenario_data["expected_properties"]
        ]
        connections = [
            {
                "subject_class": subj,
                "predicate": pred,
                "object_class": obj,
                "confidence": 0.82,
            }
            for subj, pred, obj in scenario_data["expected_connections"]
        ]

        expected_data = {
            "status": "completed",
            "result": {
                "extracted_classes": classes,
                "extracted_properties": properties,
                "extracted_relationships": connections,
            },
            "created_class_ids": [],
            "created_property_ids": [],
            "created_relationship_ids": [],
        }
        expected_path = scenario_dir / "expected.json"
        expected_path.write_text(json.dumps(expected_data, indent=2))

        # Write distractors.json (for schema extraction, these could be noise-derived classes)
        distractors_data = {
            "classes": [
                {
                    "label": "UnnecessaryClass",
                    "source": "off-topic_paragraph",
                    "confidence": 0.10,
                }
            ],
            "properties": [{"label": "spurious_property", "confidence": 0.12}],
        }
        distractors_path = scenario_dir / "distractors.json"
        distractors_path.write_text(json.dumps(distractors_data, indent=2))

        print(f"Created {scenario_name} schema fixture")


if __name__ == "__main__":
    create_schema_extraction_fixtures()
    print("\nSchema fixtures created successfully!")
