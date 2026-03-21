# Ontology Import Guide

**Date:** 2025-12-12
**Status:** Completed Successfully

## Summary

Successfully imported the ontology.csv file containing 223 nodes into the Context Studio database:
- **12 Layers** (Depth 0)
- **211 Domains** (Depth 1)
- **0 Terms** (Depth 2+)

## Import Details

### Issue Identified

The existing `utils/import_csv.py` utility was incompatible with the current database schema:
- **Old Schema:** Separate `Layer`, `Domain`, and `Term` tables
- **Current Schema:** Unified `structure_nodes` table with `node_type` discriminator

### Solution

Created a new import utility specifically for the current schema:
- **Location:** `utils/import_ontology_csv.py`
- **Compatible with:** StructureNode-based schema (unified table)
- **Features:**
  - Supports create and update operations (upsert by ID)
  - Maintains hierarchy through `parent_node_id` relationships
  - Generates vector embeddings for titles and definitions
  - Provides detailed logging and error handling

## Import Command

To import an ontology CSV file:

```bash
cd /home/austinsand/workspace/orchestrator/context-studio/local-server
source .venv/bin/activate

# Full import
PYTHONPATH=/home/austinsand/workspace/orchestrator/context-studio/local-server \
  python utils/import_ontology_csv.py -f /path/to/file.csv

# Test with first 10 rows
PYTHONPATH=/home/austinsand/workspace/orchestrator/context-studio/local-server \
  python utils/import_ontology_csv.py -f /path/to/file.csv --test

# Skip existing nodes instead of updating
PYTHONPATH=/home/austinsand/workspace/orchestrator/context-studio/local-server \
  python utils/import_ontology_csv.py -f /path/to/file.csv --skip-existing

# Debug mode
PYTHONPATH=/home/austinsand/workspace/orchestrator/context-studio/local-server \
  python utils/import_ontology_csv.py -f /path/to/file.csv -d
```

## Imported Ontology Structure

The imported ontology contains 12 architectural layers with their domains:

### 1. Motivation Layer Schema (12 domains)
Stakeholder, Driver, Assessment, Goal, Outcome, Principle, Requirement, Constraint, Meaning, Value

### 2. Business Layer Schema (14 domains)
BusinessActor, BusinessRole, BusinessCollaboration, BusinessInterface, BusinessProcess, BusinessFunction, BusinessInteraction, BusinessEvent, BusinessService, BusinessObject, Contract, Representation, Product

### 3. Security Layer Schema (34 domains)
SecurityModel, AuthenticationConfig, PasswordPolicy, Role, Permission, SecureResource, ResourceOperation, AccessCondition, FieldAccessControl, SecurityPolicy, PolicyRule, PolicyAction, DataClassification, Classification, Actor, ActorObjective, ActorDependency, InformationEntity, InformationRight, Delegation, SecurityConstraints, SeparationOfDuty, BindingOfDuty, NeedToKnow, SocialDependency, AccountabilityRequirement, Evidence, Threat, Countermeasure, RateLimit, AuditConfig, Condition, RetentionPolicy, ValidationRule

### 4. Application Layer Schema (9 domains)
ApplicationComponent, ApplicationCollaboration, ApplicationInterface, ApplicationFunction, ApplicationInteraction, ApplicationProcess, ApplicationEvent, ApplicationService, DataObject

### 5. Technology Layer Schema (14 domains)
Node, Device, SystemSoftware, TechnologyCollaboration, TechnologyInterface, Path, CommunicationNetwork, TechnologyFunction, TechnologyProcess, TechnologyInteraction, TechnologyEvent, TechnologyService, Artifact

### 6. API Layer Schema (26 domains)
OpenAPIDocument, Info, Server, Paths, PathItem, Operation, Parameter, RequestBody, Responses, Response, MediaType, Components, Schema, Tag, ExternalDocumentation, Contact, License, ServerVariable, Header, Link, Callback, Example, Encoding, OAuthFlows, OAuthFlow, SecurityScheme

### 7. Data Model Layer Schema (20 domains)
JSONSchema, JSONType, StringSchema, NumericSchema, ArraySchema, ObjectSchema, SchemaComposition, Reference, SchemaDefinition, SchemaProperty, DataGovernance, DataQualityMetrics, DatabaseMapping, x-business-object-ref, x-data-governance, x-apm-data-quality-metrics, x-database, x-ui, x-security

### 8. Datastore Layer Schema (10 domains)
Database, DatabaseSchema, Table, Column, Constraint, Index, View, Trigger, Sequence, Function

### 9. UX Layer Schema (26 domains)
UXLibrary, LibraryComponent, LibrarySubView, StatePattern, ActionPattern, UXApplication, UXSpec, ExperienceState, StateAction, StateTransition, Condition, View, SubView, ComponentInstance, ActionComponent, ValidationRule, LayoutConfig, ErrorConfig, ApiConfig, DataConfig, PerformanceTargets, ComponentReference, TransitionTemplate, StateActionTemplate, TableColumn, ChartSeries

### 10. Navigation Layer Schema (15 domains)
NavigationGraph, Route, RouteMeta, BreadcrumbConfig, NavigationTransition, NavigationGuard, GuardCondition, GuardAction, NavigationFlow, FlowStep, ContextVariable, DataMapping, ProcessTracking, FlowAnalytics, NotificationAction

### 11. APM/Observability Layer Schema (20 domains)
Span, SpanEvent, SpanLink, SpanStatus, LogRecord, Resource, InstrumentationScope, ExporterConfig, InstrumentationConfig, LogProcessor, MeterConfig, MetricInstrument, Attribute, APMConfiguration, TraceConfiguration, LogConfiguration, MetricConfiguration, DataQualityMetrics, DataQualityMetric

### 12. Testing Layer Schema (17 domains)
TestCoverageModel, TestCoverageTarget, TargetInputField, InputSpacePartition, PartitionValue, PartitionDependency, ContextVariation, EnvironmentFactor, OutcomeCategory, CoverageRequirement, InputPartitionSelection, CoverageExclusion, TestCaseSketch, InputSelection, CoverageSummary, TargetCoverageSummary, CoverageGap

## CSV Format Requirements

The import utility expects CSV files following the specification in `documentation/csv_import_specification.md`:

### Required Columns
- `Depth` - Integer (0=Layer, 1=Domain, 2+=Term)
- `Title` - String (required, max 255 chars)
- `Definition` - String (optional)
- `ID` - UUID string (optional, auto-generated if omitted)

### Hierarchy Rules
- Rows are processed sequentially
- Depth 0 = Layer (no parent)
- Depth 1 = Domain (parent is most recent Layer)
- Depth 2+ = Term (parent is most recent node at Depth-1)

## Verification

To verify the import:

```bash
source .venv/bin/activate
PYTHONPATH=/home/austinsand/workspace/orchestrator/context-studio/local-server python -c "
from database.utils import get_engine, get_session_local, init_db
from database.models import StructureNode
from database.enums import NodeType

engine = get_engine()
init_db(engine)
SessionLocal = get_session_local(engine)
session = SessionLocal()

for node_type in NodeType:
    count = session.query(StructureNode).filter_by(node_type=node_type).count()
    print(f'{node_type.value}: {count}')

total = session.query(StructureNode).count()
print(f'Total: {total}')
session.close()
"
```

## Future Imports

To import additional ontology data:

1. **Format CSV:** Ensure CSV follows the specification (see `csv_import_specification.md`)
2. **Test First:** Use `--test` flag to import first 10 rows
3. **Review Logs:** Check for warnings or errors
4. **Full Import:** Run without `--test` flag
5. **Verify:** Query database to confirm import

## Deprecated Utility

**Do not use:** `utils/import_csv.py` - This utility is incompatible with the current schema and references deprecated Layer/Domain/Term models.

**Use instead:** `utils/import_ontology_csv.py` - Compatible with current StructureNode schema.

## Related Documentation

- **CSV Import Specification:** `documentation/csv_import_specification.md`
- **Database Schema:** See `database/models.py` for StructureNode model
- **API Documentation:** `documentation/openapi.json`
