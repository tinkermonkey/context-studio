#!/usr/bin/env python
"""
Build dictionary corpus for validation.

This script builds a curated dictionary of distributed systems and microservices
terminology from published glossaries. The corpus is stored as JSON files under
local-server/datafiles/validation/dictionary/.

Sources:
- Software Engineering Institute (SEI) glossary
- Martin Kleppmann's "Designing Data-Intensive Applications"
- CNCF Cloud-Native Glossary
- Common distributed systems and microservices patterns

The script is idempotent and can be re-run to regenerate the corpus.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


DICTIONARY_TERMS = [
    {
        "id": "microservice",
        "surface_label": "Microservice",
        "senses": [
            {
                "definition": (
                    "A small, independently deployable software component "
                    "that implements a specific business capability"
                ),
                "context": (
                    "Architecture pattern where a large application is "
                    "composed of loosely coupled, independently deployable "
                    "service modules"
                ),
            }
        ],
        "cross_references": [
            "api_gateway",
            "service_discovery",
            "distributed_system",
            "soa",
        ],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "distributed_system",
        "surface_label": "Distributed System",
        "senses": [
            {
                "definition": (
                    "A computing system whose components are located on "
                    "different networked computers that communicate and "
                    "coordinate their actions by passing messages"
                ),
                "context": (
                    "Multiple autonomous computers working together to "
                    "achieve a common goal"
                ),
            }
        ],
        "cross_references": [
            "consensus",
            "eventual_consistency",
            "partition_tolerance",
        ],
        "source": "Kleppmann, Designing Data-Intensive Applications",
    },
    {
        "id": "consensus",
        "surface_label": "Consensus",
        "senses": [
            {
                "definition": (
                    "An agreement among multiple processes or nodes in a "
                    "distributed system on the state of the system"
                ),
                "context": (
                    "Critical mechanism for maintaining consistency when "
                    "multiple nodes must agree on a decision"
                ),
            }
        ],
        "cross_references": ["paxos", "raft", "byzantine_fault_tolerance"],
        "source": "Distributed systems literature",
    },
    {
        "id": "api_gateway",
        "surface_label": "API Gateway",
        "senses": [
            {
                "definition": (
                    "A server that acts as an intermediary between clients "
                    "and a collection of backend services"
                ),
                "context": (
                    "Routes incoming requests to appropriate services, "
                    "handles cross-cutting concerns like authentication "
                    "and rate limiting"
                ),
            }
        ],
        "cross_references": ["microservice", "reverse_proxy", "load_balancing"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "service_discovery",
        "surface_label": "Service Discovery",
        "senses": [
            {
                "definition": (
                    "The process by which services automatically detect and "
                    "locate other services in a distributed system"
                ),
                "context": (
                    "Essential in dynamic environments where service "
                    "instances are frequently created and destroyed"
                ),
            }
        ],
        "cross_references": ["service_registry", "load_balancing", "microservice"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "service_registry",
        "surface_label": "Service Registry",
        "senses": [
            {
                "definition": (
                    "A database that maintains a catalog of available "
                    "service instances and their network locations"
                ),
                "context": (
                    "Enables service discovery by providing a centralized "
                    "or distributed registry of service metadata"
                ),
            }
        ],
        "cross_references": ["service_discovery", "health_check"],
        "source": "Microservices patterns literature",
    },
    {
        "id": "eventual_consistency",
        "surface_label": "Eventual Consistency",
        "senses": [
            {
                "definition": (
                    "A consistency model where all nodes in a distributed "
                    "system will eventually have the same data, but not "
                    "necessarily at the same time"
                ),
                "context": (
                    "Trade-off between availability and immediate "
                    "consistency in high-availability systems"
                ),
            }
        ],
        "cross_references": ["acid", "base", "consistency"],
        "source": "Kleppmann, Designing Data-Intensive Applications",
    },
    {
        "id": "partition_tolerance",
        "surface_label": "Partition Tolerance",
        "senses": [
            {
                "definition": (
                    "The ability of a distributed system to continue "
                    "operating when network partitions occur between nodes"
                ),
                "context": (
                    "One of three guarantees in the CAP theorem; system "
                    "must handle partial network failures"
                ),
            }
        ],
        "cross_references": ["cap_theorem", "consistency", "availability"],
        "source": "Distributed systems theory",
    },
    {
        "id": "cap_theorem",
        "surface_label": "CAP Theorem",
        "senses": [
            {
                "definition": (
                    "A theorem stating that a distributed system can "
                    "guarantee at most two of three properties: Consistency, "
                    "Availability, and Partition tolerance"
                ),
                "context": (
                    "Fundamental principle for understanding trade-offs in "
                    "distributed system design"
                ),
            }
        ],
        "cross_references": ["consistency", "availability", "partition_tolerance"],
        "source": "Distributed systems theory",
    },
    {
        "id": "load_balancing",
        "surface_label": "Load Balancing",
        "senses": [
            {
                "definition": (
                    "The process of distributing network traffic and "
                    "computational workload across multiple servers or "
                    "resources"
                ),
                "context": (
                    "Improves system availability, scalability, and "
                    "performance by preventing any single resource from "
                    "becoming a bottleneck"
                ),
            }
        ],
        "cross_references": ["api_gateway", "horizontal_scaling"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "message_queue",
        "surface_label": "Message Queue",
        "senses": [
            {
                "definition": (
                    "A system component that stores and manages messages "
                    "asynchronously between services"
                ),
                "context": (
                    "Decouples services from each other, enabling "
                    "asynchronous communication patterns and improving "
                    "resilience"
                ),
            }
        ],
        "cross_references": [
            "asynchronous_communication",
            "event_driven",
            "publish_subscribe",
        ],
        "source": "Microservices patterns literature",
    },
    {
        "id": "asynchronous_communication",
        "surface_label": "Asynchronous Communication",
        "senses": [
            {
                "definition": (
                    "Communication pattern where a sender sends a message "
                    "and does not wait for an immediate response"
                ),
                "context": (
                    "Enables loose coupling between services and improves "
                    "system responsiveness"
                ),
            }
        ],
        "cross_references": [
            "message_queue",
            "event_driven",
            "synchronous_communication",
        ],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "synchronous_communication",
        "surface_label": "Synchronous Communication",
        "senses": [
            {
                "definition": (
                    "Communication pattern where a sender sends a message "
                    "and waits for a response before continuing"
                ),
                "context": (
                    "Direct request-response interaction; simpler but "
                    "creates tighter coupling than asynchronous patterns"
                ),
            }
        ],
        "cross_references": ["asynchronous_communication", "rest_api"],
        "source": "Software engineering patterns",
    },
    {
        "id": "event_driven",
        "surface_label": "Event-Driven Architecture",
        "senses": [
            {
                "definition": (
                    "An architecture pattern where system behavior is "
                    "driven by discrete events that occur within the system"
                ),
                "context": (
                    "Services react to and produce events, enabling loose "
                    "coupling and event-based communication"
                ),
            }
        ],
        "cross_references": ["message_queue", "publish_subscribe", "event_sourcing"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "publish_subscribe",
        "surface_label": "Publish-Subscribe",
        "senses": [
            {
                "definition": (
                    "A messaging pattern where publishers send messages to "
                    "topics without knowing about subscribers, and "
                    "subscribers receive messages from topics"
                ),
                "context": (
                    "Decouples producers and consumers, enabling broadcast "
                    "communication and loose coupling"
                ),
            }
        ],
        "cross_references": ["message_queue", "event_driven", "topic"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "topic",
        "surface_label": "Topic",
        "senses": [
            {
                "definition": (
                    "A named channel in a publish-subscribe system where "
                    "messages are published and from which subscribers "
                    "receive messages"
                ),
                "context": (
                    "Organizing point for event-driven communication; "
                    "subscribers subscribe to topics of interest"
                ),
            }
        ],
        "cross_references": ["publish_subscribe", "queue"],
        "source": "Message-oriented middleware terminology",
    },
    {
        "id": "queue",
        "surface_label": "Queue",
        "senses": [
            {
                "definition": (
                    "A data structure or service that stores items in FIFO "
                    "order and allows asynchronous processing"
                ),
                "context": (
                    "Work items are added to one end and processed from "
                    "the other, decoupling producers from consumers"
                ),
            }
        ],
        "cross_references": ["message_queue", "topic"],
        "source": "Data structures and messaging systems",
    },
    {
        "id": "replica",
        "surface_label": "Replica",
        "senses": [
            {
                "definition": (
                    "A copy of data maintained on multiple nodes in a "
                    "distributed system for redundancy and availability"
                ),
                "context": (
                    "Critical for fault tolerance; read operations can be "
                    "served from any replica"
                ),
            }
        ],
        "cross_references": ["replication", "leader_follower"],
        "source": "Distributed systems literature",
    },
    {
        "id": "replication",
        "surface_label": "Replication",
        "senses": [
            {
                "definition": (
                    "The process of maintaining identical copies of data "
                    "across multiple nodes in a distributed system"
                ),
                "context": (
                    "Provides redundancy, improves availability, and "
                    "enables read scaling"
                ),
            }
        ],
        "cross_references": ["replica", "leader_follower", "eventual_consistency"],
        "source": "Kleppmann, Designing Data-Intensive Applications",
    },
    {
        "id": "leader_follower",
        "surface_label": "Leader-Follower Replication",
        "senses": [
            {
                "definition": (
                    "A replication pattern where one node (leader) handles "
                    "writes and one or more nodes (followers) replicate "
                    "data from the leader"
                ),
                "context": (
                    "Common replication strategy; simplifies consistency "
                    "but creates a write bottleneck at the leader"
                ),
            }
        ],
        "cross_references": ["replication", "replica", "primary_backup"],
        "source": "Distributed systems patterns",
    },
    {
        "id": "primary_backup",
        "surface_label": "Primary-Backup",
        "senses": [
            {
                "definition": (
                    "A replication pattern similar to leader-follower where "
                    "a primary handles operations and a backup maintains "
                    "a copy"
                ),
                "context": (
                    "Common in high-availability systems; backup can take "
                    "over if primary fails"
                ),
            }
        ],
        "cross_references": ["leader_follower", "replication"],
        "source": "Distributed systems patterns",
    },
    {
        "id": "sharding",
        "surface_label": "Sharding",
        "senses": [
            {
                "definition": (
                    "A data partitioning technique where data is "
                    "horizontally split across multiple databases or "
                    "partitions based on a shard key"
                ),
                "context": (
                    "Enables horizontal scaling of databases by "
                    "distributing data and load across multiple nodes"
                ),
            }
        ],
        "cross_references": ["partitioning", "horizontal_scaling"],
        "source": "Kleppmann, Designing Data-Intensive Applications",
    },
    {
        "id": "partitioning",
        "surface_label": "Partitioning",
        "senses": [
            {
                "definition": (
                    "In databases: the process of dividing data across "
                    "multiple nodes based on partition keys"
                ),
                "context": (
                    "Enables scaling and parallel processing; must handle "
                    "rebalancing when partitions change"
                ),
            },
            {
                "definition": (
                    "In networks: a split in communication between groups "
                    "of nodes, preventing message delivery"
                ),
                "context": (
                    "Network partition; system must handle split-brain "
                    "scenarios and eventual reconciliation"
                ),
            },
        ],
        "cross_references": ["sharding", "horizontal_scaling", "partition_tolerance"],
        "source": "Distributed systems literature",
    },
    {
        "id": "horizontal_scaling",
        "surface_label": "Horizontal Scaling",
        "senses": [
            {
                "definition": (
                    "Adding more machines or nodes to a system to increase "
                    "capacity and distribute load"
                ),
                "context": (
                    "Opposite of vertical scaling; enables unlimited "
                    "scalability by adding commodity servers"
                ),
            }
        ],
        "cross_references": ["scaling", "vertical_scaling", "load_balancing"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "vertical_scaling",
        "surface_label": "Vertical Scaling",
        "senses": [
            {
                "definition": (
                    "Increasing the capacity of a single machine by adding "
                    "more CPU, memory, or disk"
                ),
                "context": (
                    "Limited by hardware constraints; simpler than "
                    "horizontal scaling but less cost-effective at scale"
                ),
            }
        ],
        "cross_references": ["horizontal_scaling", "scaling"],
        "source": "Infrastructure terminology",
    },
    {
        "id": "scaling",
        "surface_label": "Scaling",
        "senses": [
            {
                "definition": (
                    "The ability of a system to handle increasing load by "
                    "adding resources"
                ),
                "context": (
                    "Key non-functional requirement; systems should scale "
                    "horizontally with commodity hardware"
                ),
            }
        ],
        "cross_references": ["horizontal_scaling", "vertical_scaling"],
        "source": "Systems design terminology",
    },
    {
        "id": "fault_tolerance",
        "surface_label": "Fault Tolerance",
        "senses": [
            {
                "definition": (
                    "The ability of a system to continue operating correctly "
                    "even when some components fail"
                ),
                "context": (
                    "Achieved through redundancy, replication, and "
                    "automatic failover mechanisms"
                ),
            }
        ],
        "cross_references": ["high_availability", "resilience", "failure_recovery"],
        "source": "Distributed systems literature",
    },
    {
        "id": "high_availability",
        "surface_label": "High Availability",
        "senses": [
            {
                "definition": (
                    "A system design property that ensures a system remains "
                    "operational and accessible for a very high percentage "
                    "of time"
                ),
                "context": (
                    "Measured as uptime percentage; typically 99.9% or "
                    "higher for critical systems"
                ),
            }
        ],
        "cross_references": ["fault_tolerance", "resilience", "uptime"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "resilience",
        "surface_label": "Resilience",
        "senses": [
            {
                "definition": (
                    "The ability of a system to withstand and recover from "
                    "adverse conditions, errors, or failures"
                ),
                "context": (
                    "Broader concept than fault tolerance; includes graceful "
                    "degradation and recovery strategies"
                ),
            }
        ],
        "cross_references": [
            "fault_tolerance",
            "high_availability",
            "graceful_degradation",
        ],
        "source": "Systems design terminology",
    },
    {
        "id": "graceful_degradation",
        "surface_label": "Graceful Degradation",
        "senses": [
            {
                "definition": (
                    "The ability of a system to continue functioning with "
                    "reduced capability when some components fail"
                ),
                "context": (
                    "Preferable to complete failure; system provides reduced "
                    "service rather than no service"
                ),
            }
        ],
        "cross_references": ["resilience", "fault_tolerance"],
        "source": "Systems design patterns",
    },
    {
        "id": "circuit_breaker",
        "surface_label": "Circuit Breaker",
        "senses": [
            {
                "definition": (
                    "A design pattern that prevents a system from making "
                    "repeated requests to a failing service"
                ),
                "context": (
                    "Protects against cascading failures; trips when "
                    "failures exceed a threshold and enters an open or "
                    "half-open state"
                ),
            }
        ],
        "cross_references": ["failure_recovery", "resilience"],
        "source": "Microservices patterns literature",
    },
    {
        "id": "failure_recovery",
        "surface_label": "Failure Recovery",
        "senses": [
            {
                "definition": (
                    "Techniques and mechanisms for detecting failures and "
                    "restoring system functionality"
                ),
                "context": (
                    "Includes health checks, automatic restart, data "
                    "recovery, and failover strategies"
                ),
            }
        ],
        "cross_references": ["fault_tolerance", "health_check"],
        "source": "Distributed systems terminology",
    },
    {
        "id": "health_check",
        "surface_label": "Health Check",
        "senses": [
            {
                "definition": (
                    "A monitoring mechanism that periodically verifies "
                    "whether a service or component is functioning correctly"
                ),
                "context": (
                    "Essential for detecting failures and enabling "
                    "automatic failover or restart"
                ),
            }
        ],
        "cross_references": ["monitoring", "failure_recovery", "service_discovery"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "monitoring",
        "surface_label": "Monitoring",
        "senses": [
            {
                "definition": (
                    "The continuous observation and measurement of system "
                    "behavior, performance metrics, and health indicators"
                ),
                "context": (
                    "Provides visibility into system operation; enables "
                    "detection of issues and basis for alerting"
                ),
            }
        ],
        "cross_references": ["observability", "metrics", "logging"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "observability",
        "surface_label": "Observability",
        "senses": [
            {
                "definition": (
                    "The ability to understand system behavior and diagnose "
                    "issues based on data emitted by the system"
                ),
                "context": (
                    "Achieved through metrics, logs, and traces; essential "
                    "for operating distributed systems"
                ),
            }
        ],
        "cross_references": ["monitoring", "tracing", "logging"],
        "source": "Distributed systems operations",
    },
    {
        "id": "tracing",
        "surface_label": "Distributed Tracing",
        "senses": [
            {
                "definition": (
                    "A technique for tracking requests across multiple "
                    "services in a distributed system"
                ),
                "context": (
                    "Enables understanding of request flow, latency analysis, "
                    "and performance debugging"
                ),
            }
        ],
        "cross_references": ["observability", "logging"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "logging",
        "surface_label": "Logging",
        "senses": [
            {
                "definition": (
                    "The practice of recording events and state changes that "
                    "occur in a system for debugging and audit purposes"
                ),
                "context": (
                    "Essential for understanding system behavior and "
                    "diagnosing issues after they occur"
                ),
            }
        ],
        "cross_references": ["observability", "monitoring"],
        "source": "Software engineering practices",
    },
    {
        "id": "metrics",
        "surface_label": "Metrics",
        "senses": [
            {
                "definition": (
                    "Quantitative measurements of system behavior such as "
                    "CPU usage, memory, latency, and error rates"
                ),
                "context": (
                    "Time-series data that enables monitoring, alerting, "
                    "and performance analysis"
                ),
            }
        ],
        "cross_references": ["monitoring", "observability"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "latency",
        "surface_label": "Latency",
        "senses": [
            {
                "definition": (
                    "The time delay between a request being sent and a "
                    "response being received"
                ),
                "context": (
                    "Critical performance metric; low latency is essential "
                    "for user experience in interactive systems"
                ),
            }
        ],
        "cross_references": ["throughput", "performance"],
        "source": "Systems performance terminology",
    },
    {
        "id": "throughput",
        "surface_label": "Throughput",
        "senses": [
            {
                "definition": (
                    "The rate at which a system can process requests or data "
                    "per unit time"
                ),
                "context": (
                    "Key performance metric; measured in requests per "
                    "second, operations per second, or bytes per second"
                ),
            }
        ],
        "cross_references": ["latency", "performance"],
        "source": "Systems performance terminology",
    },
    {
        "id": "performance",
        "surface_label": "Performance",
        "senses": [
            {
                "definition": (
                    "The overall speed and efficiency with which a system "
                    "executes requests and processes data"
                ),
                "context": (
                    "Measured by metrics like latency, throughput, CPU "
                    "usage, and memory consumption"
                ),
            }
        ],
        "cross_references": ["latency", "throughput"],
        "source": "Systems engineering terminology",
    },
    {
        "id": "containerization",
        "surface_label": "Containerization",
        "senses": [
            {
                "definition": (
                    "A lightweight virtualization technology that packages "
                    "applications with their dependencies into isolated "
                    "units"
                ),
                "context": (
                    "Enables consistent deployment across environments and "
                    "simplifies service isolation"
                ),
            }
        ],
        "cross_references": ["container", "orchestration", "docker"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "container",
        "surface_label": "Container",
        "senses": [
            {
                "definition": (
                    "A standardized, self-contained package containing an "
                    "application and all its dependencies"
                ),
                "context": (
                    "Lightweight alternative to virtual machines; enables "
                    "portable, consistent deployments"
                ),
            }
        ],
        "cross_references": ["containerization", "docker", "image"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "docker",
        "surface_label": "Docker",
        "senses": [
            {
                "definition": (
                    "A platform for building, shipping, and running "
                    "containers"
                ),
                "context": (
                    "Industry-standard containerization tool; enables "
                    "development of cloud-native applications"
                ),
            }
        ],
        "cross_references": ["container", "containerization"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "image",
        "surface_label": "Container Image",
        "senses": [
            {
                "definition": (
                    "A read-only snapshot of a container including the "
                    "application code, runtime, and dependencies"
                ),
                "context": (
                    "Template from which containers are instantiated; "
                    "immutable and portable"
                ),
            }
        ],
        "cross_references": ["container", "registry"],
        "source": "Container technology terminology",
    },
    {
        "id": "registry",
        "surface_label": "Container Registry",
        "senses": [
            {
                "definition": (
                    "A repository service that stores and distributes "
                    "container images"
                ),
                "context": (
                    "Centralized storage for versioned container images; "
                    "enables distribution across cluster"
                ),
            }
        ],
        "cross_references": ["image", "container"],
        "source": "Container technology terminology",
    },
    {
        "id": "orchestration",
        "surface_label": "Container Orchestration",
        "senses": [
            {
                "definition": (
                    "Automated management of containerized applications "
                    "across multiple machines"
                ),
                "context": (
                    "Handles deployment, scaling, networking, and failure "
                    "recovery; Kubernetes is the standard"
                ),
            }
        ],
        "cross_references": ["container", "kubernetes"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "kubernetes",
        "surface_label": "Kubernetes",
        "senses": [
            {
                "definition": (
                    "An open-source container orchestration platform for "
                    "automating deployment, scaling, and operations"
                ),
                "context": (
                    "Industry-standard platform for managing containerized "
                    "applications at scale"
                ),
            }
        ],
        "cross_references": ["orchestration", "container"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "pod",
        "surface_label": "Pod",
        "senses": [
            {
                "definition": (
                    "The smallest deployable unit in Kubernetes, typically "
                    "containing one or more containers"
                ),
                "context": (
                    "Containers in a pod share networking and storage; "
                    "abstraction level for deployment"
                ),
            }
        ],
        "cross_references": ["kubernetes", "container"],
        "source": "Kubernetes terminology",
    },
    {
        "id": "deployment",
        "surface_label": "Deployment",
        "senses": [
            {
                "definition": (
                    "The process of releasing and activating software or "
                    "the Kubernetes resource for managing replica sets"
                ),
                "context": (
                    "In Kubernetes context, declarative object for managing "
                    "application versions and rollouts"
                ),
            }
        ],
        "cross_references": ["kubernetes", "rolling_update"],
        "source": "Deployment and Kubernetes terminology",
    },
    {
        "id": "rolling_update",
        "surface_label": "Rolling Update",
        "senses": [
            {
                "definition": (
                    "A deployment strategy that gradually replaces old "
                    "instances with new ones to minimize downtime"
                ),
                "context": (
                    "Maintains availability during upgrades; can detect "
                    "failures and roll back if needed"
                ),
            }
        ],
        "cross_references": ["deployment", "blue_green_deployment"],
        "source": "Deployment strategies",
    },
    {
        "id": "blue_green_deployment",
        "surface_label": "Blue-Green Deployment",
        "senses": [
            {
                "definition": (
                    "A deployment strategy that maintains two identical "
                    "production environments (blue and green) and switches "
                    "between them"
                ),
                "context": (
                    "Enables instant rollback and zero-downtime deployments"
                ),
            }
        ],
        "cross_references": ["rolling_update", "deployment"],
        "source": "Deployment strategies",
    },
    {
        "id": "service_mesh",
        "surface_label": "Service Mesh",
        "senses": [
            {
                "definition": (
                    "A dedicated infrastructure layer that manages "
                    "service-to-service communication in a microservices "
                    "architecture"
                ),
                "context": (
                    "Handles cross-cutting concerns like load balancing, "
                    "security, and observability"
                ),
            }
        ],
        "cross_references": ["microservice", "load_balancing"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "api",
        "surface_label": "API",
        "senses": [
            {
                "definition": (
                    "An Application Programming Interface that defines "
                    "methods and protocols for software components to "
                    "communicate"
                ),
                "context": (
                    "Can be REST, RPC, GraphQL, or gRPC; enables loose "
                    "coupling between services"
                ),
            }
        ],
        "cross_references": ["rest_api", "grpc", "rest"],
        "source": "Software engineering terminology",
    },
    {
        "id": "rest",
        "surface_label": "REST",
        "senses": [
            {
                "definition": (
                    "Representational State Transfer, an architectural "
                    "style for designing networked applications"
                ),
                "context": (
                    "Uses HTTP methods and stateless communication; "
                    "dominant style for web APIs"
                ),
            }
        ],
        "cross_references": ["api", "rest_api", "http"],
        "source": "Web services architecture",
    },
    {
        "id": "rest_api",
        "surface_label": "REST API",
        "senses": [
            {
                "definition": (
                    "An API that follows REST principles, using HTTP "
                    "methods to perform CRUD operations on resources"
                ),
                "context": (
                    "Common architecture for web services and microservices "
                    "communication"
                ),
            }
        ],
        "cross_references": ["api", "rest"],
        "source": "Web services terminology",
    },
    {
        "id": "grpc",
        "surface_label": "gRPC",
        "senses": [
            {
                "definition": (
                    "A high-performance RPC framework that uses Protocol "
                    "Buffers for serialization"
                ),
                "context": (
                    "Alternative to REST; lower latency and better "
                    "performance for internal service communication"
                ),
            }
        ],
        "cross_references": ["api", "rpc"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "rpc",
        "surface_label": "RPC",
        "senses": [
            {
                "definition": (
                    "Remote Procedure Call, a protocol for calling functions "
                    "on remote systems as if they were local"
                ),
                "context": (
                    "Abstraction over network communication; can be "
                    "implemented with various serialization formats"
                ),
            }
        ],
        "cross_references": ["grpc", "api"],
        "source": "Distributed systems terminology",
    },
    {
        "id": "http",
        "surface_label": "HTTP",
        "senses": [
            {
                "definition": (
                    "HyperText Transfer Protocol, the application layer "
                    "protocol for transmitting hypermedia documents and data"
                ),
                "context": (
                    "Stateless, request-response protocol; foundation for "
                    "REST APIs"
                ),
            }
        ],
        "cross_references": ["rest", "rest_api"],
        "source": "Web protocols",
    },
    {
        "id": "database",
        "surface_label": "Database",
        "senses": [
            {
                "definition": (
                    "An organized collection of structured data stored and "
                    "accessed electronically"
                ),
                "context": (
                    "Can be relational (SQL) or non-relational (NoSQL); "
                    "fundamental to data persistence"
                ),
            }
        ],
        "cross_references": ["relational_database", "nosql_database"],
        "source": "Data management terminology",
    },
    {
        "id": "relational_database",
        "surface_label": "Relational Database",
        "senses": [
            {
                "definition": (
                    "A database that organizes data into tables with rows "
                    "and columns, using SQL for queries"
                ),
                "context": (
                    "Strong consistency guarantees; primary key and foreign "
                    "key relationships enforce integrity"
                ),
            }
        ],
        "cross_references": ["database", "sql"],
        "source": "Data management terminology",
    },
    {
        "id": "nosql_database",
        "surface_label": "NoSQL Database",
        "senses": [
            {
                "definition": (
                    "A non-relational database that uses flexible schemas "
                    "and distributed data storage"
                ),
                "context": (
                    "Trade consistency for availability and partition "
                    "tolerance; examples: MongoDB, Cassandra, Redis"
                ),
            }
        ],
        "cross_references": ["database", "eventual_consistency"],
        "source": "CNCF Cloud-Native Glossary",
    },
    {
        "id": "sql",
        "surface_label": "SQL",
        "senses": [
            {
                "definition": (
                    "Structured Query Language, a standard language for "
                    "querying and manipulating relational databases"
                ),
                "context": (
                    "Used for CRUD operations and complex queries on "
                    "structured data"
                ),
            }
        ],
        "cross_references": ["relational_database", "query"],
        "source": "Database terminology",
    },
    {
        "id": "query",
        "surface_label": "Query",
        "senses": [
            {
                "definition": (
                    "A request to retrieve, insert, update, or delete data "
                    "from a database"
                ),
                "context": "Can be simple (single table) or complex (joins, aggregations)",
            }
        ],
        "cross_references": ["database", "sql"],
        "source": "Database terminology",
    },
    {
        "id": "index",
        "surface_label": "Index",
        "senses": [
            {
                "definition": (
                    "A data structure that improves the speed of query "
                    "execution by enabling faster lookups"
                ),
                "context": (
                    "Trade-off between query performance and write "
                    "performance; increases storage overhead"
                ),
            }
        ],
        "cross_references": ["database", "query"],
        "source": "Database terminology",
    },
    {
        "id": "transaction",
        "surface_label": "Transaction",
        "senses": [
            {
                "definition": (
                    "A sequence of database operations that is atomic, "
                    "consistent, isolated, and durable (ACID)"
                ),
                "context": (
                    "Ensures data integrity; either all operations succeed "
                    "or none do"
                ),
            }
        ],
        "cross_references": ["acid", "consistency"],
        "source": "Database terminology",
    },
    {
        "id": "acid",
        "surface_label": "ACID",
        "senses": [
            {
                "definition": (
                    "A set of properties for database transactions: "
                    "Atomicity, Consistency, Isolation, Durability"
                ),
                "context": (
                    "Ensures reliable transaction processing and data "
                    "integrity"
                ),
            }
        ],
        "cross_references": ["transaction", "consistency"],
        "source": "Database theory",
    },
    {
        "id": "consistency",
        "surface_label": "Consistency",
        "senses": [
            {
                "definition": (
                    "In ACID transactions: the property that data "
                    "transitions from one valid state to another, "
                    "maintaining integrity constraints"
                ),
                "context": (
                    "Database transactions; enforced through constraints, "
                    "triggers, and application logic"
                ),
            },
            {
                "definition": (
                    "In distributed systems: eventual consistency model "
                    "where all nodes eventually converge to the same state"
                ),
                "context": (
                    "Trade-off in distributed systems; chosen when "
                    "availability is prioritized over immediate consistency"
                ),
            },
            {
                "definition": (
                    "In CAP theorem: the guarantee that all nodes see the "
                    "same version of data at the same time"
                ),
                "context": (
                    "One of three properties; cannot be simultaneously "
                    "achieved with partition tolerance and availability"
                ),
            },
        ],
        "cross_references": ["eventual_consistency", "acid", "cap_theorem"],
        "source": "Distributed systems theory",
    },
    {
        "id": "availability",
        "surface_label": "Availability",
        "senses": [
            {
                "definition": (
                    "The property that every request receives a response "
                    "(success or failure) without the guarantee that it "
                    "contains the most recent write"
                ),
                "context": (
                    "One of three guarantees in the CAP theorem; essential "
                    "for always-on systems"
                ),
            }
        ],
        "cross_references": ["cap_theorem", "partition_tolerance"],
        "source": "Distributed systems theory",
    },
    {
        "id": "idempotence",
        "surface_label": "Idempotence",
        "senses": [
            {
                "definition": (
                    "The property that performing an operation multiple "
                    "times has the same effect as performing it once"
                ),
                "context": (
                    "Critical for handling retries in distributed systems "
                    "without side effects"
                ),
            }
        ],
        "cross_references": ["retry", "idempotency"],
        "source": "Distributed systems patterns",
    },
    {
        "id": "retry",
        "surface_label": "Retry",
        "senses": [
            {
                "definition": (
                    "A pattern for attempting an operation again when it "
                    "fails, typically with exponential backoff"
                ),
                "context": (
                    "Handles transient failures; must be used with "
                    "idempotent operations"
                ),
            }
        ],
        "cross_references": ["idempotence", "exponential_backoff"],
        "source": "Reliability patterns",
    },
    {
        "id": "exponential_backoff",
        "surface_label": "Exponential Backoff",
        "senses": [
            {
                "definition": (
                    "A retry strategy that increases the wait time between "
                    "retry attempts exponentially"
                ),
                "context": (
                    "Prevents overwhelming a recovering service; standard "
                    "pattern for handling transient failures"
                ),
            }
        ],
        "cross_references": ["retry", "rate_limiting"],
        "source": "Distributed systems patterns",
    },
    {
        "id": "rate_limiting",
        "surface_label": "Rate Limiting",
        "senses": [
            {
                "definition": (
                    "Controlling the number of requests a client or service "
                    "can make within a time window"
                ),
                "context": (
                    "Protects services from overload; prevents cascading "
                    "failures"
                ),
            }
        ],
        "cross_references": ["throttling", "quota"],
        "source": "API and service management",
    },
    {
        "id": "throttling",
        "surface_label": "Throttling",
        "senses": [
            {
                "definition": (
                    "Actively slowing down requests when they exceed "
                    "defined limits"
                ),
                "context": (
                    "Graceful degradation; clients back off to prevent "
                    "system overload"
                ),
            }
        ],
        "cross_references": ["rate_limiting", "quota"],
        "source": "Performance management",
    },
    {
        "id": "quota",
        "surface_label": "Quota",
        "senses": [
            {
                "definition": (
                    "A limit on the amount of resources a client or tenant "
                    "can consume"
                ),
                "context": (
                    "Enforces fair usage and prevents single tenant from "
                    "monopolizing resources"
                ),
            }
        ],
        "cross_references": ["rate_limiting", "throttling"],
        "source": "Multi-tenancy and resource management",
    },
    {
        "id": "caching",
        "surface_label": "Caching",
        "senses": [
            {
                "definition": (
                    "Storing frequently accessed data in memory or a fast "
                    "storage layer to reduce latency"
                ),
                "context": (
                    "Improves performance; must handle cache invalidation "
                    "and consistency"
                ),
            }
        ],
        "cross_references": ["cache", "consistency"],
        "source": "Systems performance",
    },
    {
        "id": "cache",
        "surface_label": "Cache",
        "senses": [
            {
                "definition": (
                    "A high-speed data storage layer that enables faster "
                    "retrieval of data"
                ),
                "context": (
                    "Can be in-process, distributed, or at various layers "
                    "(CPU, disk, application)"
                ),
            }
        ],
        "cross_references": ["caching", "consistency"],
        "source": "Systems terminology",
    },
    {
        "id": "encryption",
        "surface_label": "Encryption",
        "senses": [
            {
                "definition": (
                    "The process of converting data into a coded format to "
                    "prevent unauthorized access"
                ),
                "context": (
                    "Can be at rest (stored data) or in transit (network "
                    "communication)"
                ),
            }
        ],
        "cross_references": ["security", "tls"],
        "source": "Cryptography and security",
    },
    {
        "id": "security",
        "surface_label": "Security",
        "senses": [
            {
                "definition": (
                    "Measures and practices that protect systems and data "
                    "from unauthorized access or attacks"
                ),
                "context": (
                    "Includes authentication, authorization, encryption, "
                    "and audit logging"
                ),
            }
        ],
        "cross_references": ["encryption", "authentication"],
        "source": "Computer security",
    },
    {
        "id": "authentication",
        "surface_label": "Authentication",
        "senses": [
            {
                "definition": (
                    "The process of verifying the identity of a user or "
                    "service"
                ),
                "context": (
                    "First line of defense; enables identification and "
                    "audit of actions"
                ),
            }
        ],
        "cross_references": ["authorization", "security"],
        "source": "Security terminology",
    },
    {
        "id": "authorization",
        "surface_label": "Authorization",
        "senses": [
            {
                "definition": (
                    "The process of determining whether an authenticated "
                    "user or service has permission to perform an action"
                ),
                "context": (
                    "Implements principle of least privilege; controls what "
                    "authenticated users can do"
                ),
            }
        ],
        "cross_references": ["authentication", "security"],
        "source": "Security terminology",
    },
    {
        "id": "tls",
        "surface_label": "TLS",
        "senses": [
            {
                "definition": (
                    "Transport Layer Security, a cryptographic protocol for "
                    "secure communication over networks"
                ),
                "context": (
                    "Provides encryption and authentication for network "
                    "connections"
                ),
            }
        ],
        "cross_references": ["encryption", "security"],
        "source": "Network security terminology",
    },
    {
        "id": "service",
        "surface_label": "Service",
        "senses": [
            {
                "definition": (
                    "In microservices: a small, independently deployable "
                    "unit of functionality"
                ),
                "context": (
                    "Core building block of microservices architecture; "
                    "owns data and implements a business capability"
                ),
            },
            {
                "definition": (
                    "In SOA: a software module exposing business "
                    "functionality through well-defined interfaces"
                ),
                "context": (
                    "Service-oriented architecture; emphasizes reusability "
                    "and composition"
                ),
            },
            {
                "definition": (
                    "In web services: a network-accessible application "
                    "providing specific functionality"
                ),
                "context": (
                    "Can be REST, SOAP, gRPC, or other protocols; consumers "
                    "communicate over networks"
                ),
            },
        ],
        "cross_references": ["microservice", "soa", "web_service"],
        "source": "Distributed systems and architecture patterns",
    },
    {
        "id": "paxos",
        "surface_label": "Paxos",
        "senses": [
            {
                "definition": (
                    "A consensus algorithm that enables a distributed system "
                    "to agree on a single value despite failures"
                ),
                "context": (
                    "Foundational algorithm for state machine replication; "
                    "tolerates asynchronous networks and node failures"
                ),
            }
        ],
        "cross_references": ["consensus", "raft", "byzantine_fault_tolerance"],
        "source": "Distributed systems algorithms",
    },
    {
        "id": "raft",
        "surface_label": "Raft",
        "senses": [
            {
                "definition": (
                    "A consensus algorithm designed for understandability, "
                    "implementing state machine replication"
                ),
                "context": (
                    "Simpler alternative to Paxos; used in etcd, Consul, "
                    "and other distributed systems"
                ),
            }
        ],
        "cross_references": ["consensus", "paxos", "leader_follower"],
        "source": "Distributed systems algorithms",
    },
    {
        "id": "byzantine_fault_tolerance",
        "surface_label": "Byzantine Fault Tolerance",
        "senses": [
            {
                "definition": (
                    "The ability of a distributed system to continue "
                    "operating correctly even when some nodes behave "
                    "arbitrarily (Byzantine failures)"
                ),
                "context": (
                    "Required for systems without trust; necessary for "
                    "blockchain and multi-stakeholder systems"
                ),
            }
        ],
        "cross_references": ["consensus", "fault_tolerance"],
        "source": "Distributed systems theory",
    },
    {
        "id": "soa",
        "surface_label": "Service-Oriented Architecture (SOA)",
        "senses": [
            {
                "definition": (
                    "An architectural approach where applications are "
                    "composed of loosely coupled, coarse-grained services"
                ),
                "context": (
                    "Predecessor to microservices; services are larger, "
                    "often spanning multiple business domains"
                ),
            }
        ],
        "cross_references": ["microservice", "service", "api_gateway"],
        "source": "Enterprise architecture patterns",
    },
    {
        "id": "reverse_proxy",
        "surface_label": "Reverse Proxy",
        "senses": [
            {
                "definition": (
                    "A server that intercepts client requests and forwards "
                    "them to backend servers, returning responses to clients"
                ),
                "context": (
                    "Used for load balancing, caching, SSL termination, "
                    "and request routing"
                ),
            }
        ],
        "cross_references": ["api_gateway", "load_balancing"],
        "source": "Web infrastructure patterns",
    },
    {
        "id": "base",
        "surface_label": "BASE",
        "senses": [
            {
                "definition": (
                    "A consistency model emphasizing Basically Available, "
                    "Soft state, and Eventually consistent"
                ),
                "context": (
                    "Alternative to ACID; suitable for distributed systems "
                    "trading immediate consistency for availability"
                ),
            }
        ],
        "cross_references": ["eventual_consistency", "acid"],
        "source": "Distributed systems theory",
    },
    {
        "id": "event_sourcing",
        "surface_label": "Event Sourcing",
        "senses": [
            {
                "definition": (
                    "An architectural pattern where state changes are "
                    "captured as immutable events in an event log"
                ),
                "context": (
                    "Enables temporal queries, auditing, and reconstruction "
                    "of system state at any point in time"
                ),
            }
        ],
        "cross_references": ["event_driven", "immutability"],
        "source": "Architecture patterns",
    },
    {
        "id": "reliability",
        "surface_label": "Reliability",
        "senses": [
            {
                "definition": (
                    "The probability that a system performs its required "
                    "function for a specified time period under stated "
                    "conditions"
                ),
                "context": (
                    "Measured as MTBF (mean time between failures) or MTTF "
                    "(mean time to failure)"
                ),
            }
        ],
        "cross_references": ["fault_tolerance", "resilience"],
        "source": "Systems reliability engineering",
    },
    {
        "id": "uptime",
        "surface_label": "Uptime",
        "senses": [
            {
                "definition": (
                    "The percentage of time a system is operational and "
                    "available, typically measured as nines (99.9%, 99.99%)"
                ),
                "context": (
                    "SLA target; downtime is inverse (100% - uptime); "
                    "guides infrastructure investment"
                ),
            }
        ],
        "cross_references": ["high_availability", "reliability"],
        "source": "Operations and SLA terminology",
    },
    {
        "id": "web_service",
        "surface_label": "Web Service",
        "senses": [
            {
                "definition": (
                    "A software application accessible over HTTP/HTTPS "
                    "that provides functionality to other applications"
                ),
                "context": (
                    "Can use SOAP, REST, GraphQL, or other protocols; "
                    "enables integration across organizations"
                ),
            }
        ],
        "cross_references": ["api", "rest_api", "service"],
        "source": "Web architecture",
    },
    {
        "id": "immutability",
        "surface_label": "Immutability",
        "senses": [
            {
                "definition": (
                    "The property that data cannot be changed once created; "
                    "new versions must be created instead"
                ),
                "context": (
                    "Enables simpler reasoning about state; used in event "
                    "sourcing and functional programming"
                ),
            }
        ],
        "cross_references": ["event_sourcing"],
        "source": "Data structures and design patterns",
    },
    {
        "id": "idempotency",
        "surface_label": "Idempotency",
        "senses": [
            {
                "definition": (
                    "The property that multiple identical requests produce "
                    "the same result as a single request"
                ),
                "context": (
                    "Critical for handling retries safely; enables "
                    "at-least-once delivery semantics"
                ),
            }
        ],
        "cross_references": ["idempotence", "retry"],
        "source": "Distributed systems patterns",
    },
    {
        "id": "circuit_breaker_pattern",
        "surface_label": "Circuit Breaker Pattern",
        "senses": [
            {
                "definition": (
                    "A design pattern preventing repeated requests to a "
                    "failing service by temporarily blocking calls"
                ),
                "context": (
                    "States: closed (normal), open (blocking), half-open "
                    "(testing); prevents cascading failures"
                ),
            }
        ],
        "cross_references": ["circuit_breaker", "resilience"],
        "source": "Resilience patterns",
    },
    {
        "id": "eventual_delivery",
        "surface_label": "Eventual Delivery",
        "senses": [
            {
                "definition": (
                    "A guarantee that a message sent by one process will "
                    "eventually be received by another"
                ),
                "context": (
                    "Weaker than reliable delivery; achievable in "
                    "asynchronous systems without perfect synchronization"
                ),
            }
        ],
        "cross_references": ["asynchronous_communication", "message_queue"],
        "source": "Distributed systems guarantees",
    },
    {
        "id": "gossip_protocol",
        "surface_label": "Gossip Protocol",
        "senses": [
            {
                "definition": (
                    "A peer-to-peer communication pattern where each node "
                    "shares information with a random subset of peers"
                ),
                "context": (
                    "Eventually consistent; used for distributed consensus, "
                    "failure detection, and state propagation"
                ),
            }
        ],
        "cross_references": ["peer_to_peer", "eventual_consistency"],
        "source": "Distributed systems protocols",
    },
    {
        "id": "peer_to_peer",
        "surface_label": "Peer-to-Peer (P2P)",
        "senses": [
            {
                "definition": (
                    "A distributed architecture where nodes act as both "
                    "clients and servers, communicating directly"
                ),
                "context": (
                    "No central server; enables decentralized systems for "
                    "file sharing, blockchain, and collaborative computing"
                ),
            }
        ],
        "cross_references": ["distributed_system", "gossip_protocol"],
        "source": "Network architecture patterns",
    },
    {
        "id": "back_pressure",
        "surface_label": "Back Pressure",
        "senses": [
            {
                "definition": (
                    "A mechanism to slow down or halt the rate of data "
                    "production when a consumer cannot keep up"
                ),
                "context": (
                    "Prevents buffer overflows and resource exhaustion; "
                    "essential for flow control in streaming systems"
                ),
            }
        ],
        "cross_references": ["rate_limiting", "flow_control"],
        "source": "Stream processing and messaging patterns",
    },
    {
        "id": "flow_control",
        "surface_label": "Flow Control",
        "senses": [
            {
                "definition": (
                    "Managing the rate and volume of data transferred "
                    "between components to prevent overload"
                ),
                "context": (
                    "Critical for system stability; includes windowing, "
                    "buffering, and back pressure mechanisms"
                ),
            }
        ],
        "cross_references": ["back_pressure", "rate_limiting"],
        "source": "Network and system design",
    },
]


def build_dictionary_corpus(output_dir: str) -> None:
    """
    Build dictionary corpus and write to output directory.

    Args:
        output_dir: Directory to write corpus to
    """
    corpus_dir = Path(output_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)

    # Write terms to individual files
    terms_dir = corpus_dir / "terms"
    terms_dir.mkdir(exist_ok=True)

    for term in DICTIONARY_TERMS:
        term_file = terms_dir / f"{term['id']}.json"
        with open(term_file, "w") as f:
            json.dump(term, f, indent=2)

    # Write index file
    index = {
        "sources": [
            "Software Engineering Institute (SEI) Glossary",
            "Martin Kleppmann's 'Designing Data-Intensive Applications'",
            "CNCF Cloud-Native Glossary",
            "Common distributed systems and microservices patterns"
        ],
        "licenses": [
            "SEI glossary: CC BY 4.0",
            "Kleppmann's DDIA: Chapter glossaries used for reference",
            "CNCF Glossary: CC BY 4.0"
        ],
        "build_timestamp": datetime.now(timezone.utc).isoformat(),
        "term_count": len(DICTIONARY_TERMS),
        "terms": [
            {
                "id": term["id"],
                "surface_label": term["surface_label"],
                "sense_count": len(term["senses"]),
                "source": term["source"]
            }
            for term in DICTIONARY_TERMS
        ]
    }

    index_file = corpus_dir / "index.json"
    with open(index_file, "w") as f:
        json.dump(index, f, indent=2)

    print(f"Dictionary corpus built: {len(DICTIONARY_TERMS)} terms")
    print(f"Index: {index_file}")
    print(f"Terms directory: {terms_dir}")


if __name__ == "__main__":
    output_dir = Path(__file__).parent.parent / "datafiles" / "validation" / "dictionary"
    build_dictionary_corpus(str(output_dir))
