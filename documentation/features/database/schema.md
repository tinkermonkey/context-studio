# Database Schema

## Overview

Context Studio uses SQLite as its primary database with the sqlite-vec extension for vector operations. The schema supports hierarchical knowledge graphs, version control, collaboration workflows, and advanced analytics. Each dataset maintains its own independent database file with a complete schema instance.

## Core Tables

### Structure Nodes (`structure_nodes`)

The unified table for all knowledge graph entities (layers, domains, terms).

```sql
CREATE TABLE structure_nodes (
    id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
    title TEXT NOT NULL,
    description TEXT,
    node_type TEXT NOT NULL CHECK (node_type IN ('layer', 'domain', 'term')),
    parent_id TEXT REFERENCES structure_nodes(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,

    -- Vector embeddings (using sqlite-vec)
    title_embedding BLOB,
    description_embedding BLOB,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Version control
    version INTEGER NOT NULL DEFAULT 1
);

-- Indexes for performance
CREATE INDEX idx_structure_nodes_type ON structure_nodes(node_type);
CREATE INDEX idx_structure_nodes_parent ON structure_nodes(parent_id);
CREATE INDEX idx_structure_nodes_type_parent ON structure_nodes(node_type, parent_id);
CREATE INDEX idx_structure_nodes_title ON structure_nodes(title);
CREATE INDEX idx_structure_nodes_position ON structure_nodes(parent_id, position);

-- Unique constraint: title must be unique within same parent
CREATE UNIQUE INDEX idx_structure_nodes_title_parent
ON structure_nodes(title, COALESCE(parent_id, ''));

-- Virtual table for full-text search
CREATE VIRTUAL TABLE structure_nodes_fts USING fts5(
    id UNINDEXED,
    title,
    description,
    content_rowid=structure_nodes
);
```

### Structure Node Links (`structure_node_links`)

Relationships between structure nodes using predicates.

```sql
CREATE TABLE structure_node_links (
    id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
    from_node_id TEXT NOT NULL REFERENCES structure_nodes(id) ON DELETE CASCADE,
    to_node_id TEXT NOT NULL REFERENCES structure_nodes(id) ON DELETE CASCADE,
    predicate_id TEXT NOT NULL REFERENCES predicates(id) ON DELETE RESTRICT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Version control
    version INTEGER NOT NULL DEFAULT 1,

    -- Prevent duplicate links
    UNIQUE(from_node_id, to_node_id, predicate_id)
);

-- Indexes for graph traversal
CREATE INDEX idx_structure_node_links_from ON structure_node_links(from_node_id);
CREATE INDEX idx_structure_node_links_to ON structure_node_links(to_node_id);
CREATE INDEX idx_structure_node_links_predicate ON structure_node_links(predicate_id);
CREATE INDEX idx_structure_node_links_from_predicate ON structure_node_links(from_node_id, predicate_id);
```

### Predicates (`predicates`)

Define relationship types between nodes.

```sql
CREATE TABLE predicates (
    id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
    name TEXT NOT NULL UNIQUE,
    description TEXT,

    -- JSON schema for predicate validation
    json_mapping TEXT CHECK (json_mapping IS NULL OR json_valid(json_mapping)),

    -- Predicate properties
    inverse_predicate_id TEXT REFERENCES predicates(id),
    is_symmetric BOOLEAN DEFAULT FALSE,
    is_transitive BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Version control
    version INTEGER NOT NULL DEFAULT 1
);

-- Indexes
CREATE INDEX idx_predicates_name ON predicates(name);
```

## Vector Database Integration

### Vector Tables (using sqlite-vec)

```sql
-- Title embeddings for semantic search
CREATE VIRTUAL TABLE vec_structure_nodes_title USING vec0(
    id TEXT PRIMARY KEY,
    embedding FLOAT[384]  -- Sentence transformer embedding size
);

-- Description embeddings
CREATE VIRTUAL TABLE vec_structure_nodes_description USING vec0(
    id TEXT PRIMARY KEY,
    embedding FLOAT[384]
);

-- Concept embeddings from NLP analysis
CREATE VIRTUAL TABLE vec_concepts USING vec0(
    concept_id TEXT PRIMARY KEY,
    concept_text TEXT,
    embedding FLOAT[384],
    source TEXT  -- 'extracted', 'dbpedia', 'conceptnet', etc.
);
```

## Change Management Schema

### Change Events (`change_events`)

Complete audit trail of all entity modifications.

```sql
CREATE TABLE change_events (
    id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),

    -- Entity identification
    entity_type TEXT NOT NULL,  -- 'structure_node', 'structure_node_link', 'predicate'
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('create', 'update', 'delete')),

    -- State snapshots
    before_state TEXT CHECK (before_state IS NULL OR json_valid(before_state)),
    after_state TEXT CHECK (after_state IS NULL OR json_valid(after_state)),

    -- Change metadata
    change_summary TEXT CHECK (change_summary IS NULL OR json_valid(change_summary)),

    -- Attribution
    identity_id TEXT REFERENCES identities(id),

    -- Processing
    processing_status TEXT DEFAULT 'pending' CHECK (
        processing_status IN ('pending', 'processing', 'processed', 'failed')
    ),

    -- Timestamps
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

-- Indexes for change tracking
CREATE INDEX idx_change_events_entity ON change_events(entity_type, entity_id);
CREATE INDEX idx_change_events_timestamp ON change_events(timestamp);
CREATE INDEX idx_change_events_identity ON change_events(identity_id);
CREATE INDEX idx_change_events_status ON change_events(processing_status);

-- Partition-like index for time-based queries
CREATE INDEX idx_change_events_date ON change_events(date(timestamp));
```

### Identities (`identities`)

User/contributor identity management.

```sql
CREATE TABLE identities (
    id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
    display_name TEXT NOT NULL,
    email TEXT,

    -- External authentication
    auth_provider TEXT,
    external_id TEXT,

    -- Activity tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP,

    -- Statistics
    contribution_count INTEGER DEFAULT 0,

    -- Unique constraint for external auth
    UNIQUE(auth_provider, external_id)
);

-- Indexes
CREATE INDEX idx_identities_email ON identities(email);
CREATE INDEX idx_identities_external ON identities(auth_provider, external_id);
```

### Changesets (`changesets`)

Logical groupings of changes for collaboration workflow.

```sql
CREATE TABLE changesets (
    id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
    title TEXT NOT NULL,
    description TEXT,

    -- Change tracking
    change_event_ids TEXT NOT NULL CHECK (json_valid(change_event_ids)),  -- JSON array
    author_identity_id TEXT NOT NULL REFERENCES identities(id),

    -- Workflow status
    status TEXT DEFAULT 'draft' CHECK (
        status IN ('draft', 'proposed', 'reviewing', 'approved', 'rejected', 'merged')
    ),

    -- Review metadata
    reviewers TEXT CHECK (reviewers IS NULL OR json_valid(reviewers)),  -- JSON array
    approval_count INTEGER DEFAULT 0,
    rejection_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    proposed_at TIMESTAMP,
    merged_at TIMESTAMP
);

-- Indexes
CREATE INDEX idx_changesets_status ON changesets(status);
CREATE INDEX idx_changesets_author ON changesets(author_identity_id);
CREATE INDEX idx_changesets_created ON changesets(created_at);
```

### Changeset Reviews (`changeset_reviews`)

Individual review decisions on changesets.

```sql
CREATE TABLE changeset_reviews (
    id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
    changeset_id TEXT NOT NULL REFERENCES changesets(id) ON DELETE CASCADE,
    reviewer_identity_id TEXT NOT NULL REFERENCES identities(id),

    -- Review decision
    decision TEXT NOT NULL CHECK (decision IN ('approve', 'reject', 'request_changes')),
    comments TEXT,

    -- Timestamps
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- One review per reviewer per changeset
    UNIQUE(changeset_id, reviewer_identity_id)
);

-- Indexes
CREATE INDEX idx_changeset_reviews_changeset ON changeset_reviews(changeset_id);
CREATE INDEX idx_changeset_reviews_reviewer ON changeset_reviews(reviewer_identity_id);
```

## LLM Pipeline Schema

### Pipeline Flavors (`pipeline_flavors`)

LLM pipeline configurations.

```sql
CREATE TABLE pipeline_flavors (
    id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
    name TEXT NOT NULL UNIQUE,
    description TEXT,

    -- Provider configuration
    provider TEXT NOT NULL,  -- 'openai', 'anthropic', etc.
    model TEXT NOT NULL,

    -- Prompt configuration
    system_prompt TEXT,
    user_prompt_template TEXT NOT NULL,

    -- Model parameters (JSON)
    parameters TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(parameters)),

    -- Management
    enabled BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Version control
    version INTEGER NOT NULL DEFAULT 1
);

-- Indexes
CREATE INDEX idx_pipeline_flavors_name ON pipeline_flavors(name);
CREATE INDEX idx_pipeline_flavors_provider ON pipeline_flavors(provider);
CREATE INDEX idx_pipeline_flavors_enabled ON pipeline_flavors(enabled);
```

### LLM Executions (`llm_executions`)

Complete execution tracking for LLM requests.

```sql
CREATE TABLE llm_executions (
    id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
    flavor_id TEXT NOT NULL REFERENCES pipeline_flavors(id),

    -- Request details
    inputs TEXT NOT NULL CHECK (json_valid(inputs)),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,

    -- Response details
    response TEXT,
    response_chunks TEXT CHECK (response_chunks IS NULL OR json_valid(response_chunks)),

    -- Performance metrics
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_ms INTEGER,

    -- Cost tracking
    cost_usd REAL,

    -- Quality metrics
    user_selection TEXT CHECK (user_selection IN ('accepted', 'rejected', 'modified')),
    feedback TEXT,

    -- Technical details
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    parameters TEXT CHECK (json_valid(parameters)),
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for analytics
CREATE INDEX idx_llm_executions_flavor ON llm_executions(flavor_id);
CREATE INDEX idx_llm_executions_created ON llm_executions(created_at);
CREATE INDEX idx_llm_executions_provider ON llm_executions(provider);
CREATE INDEX idx_llm_executions_cost ON llm_executions(cost_usd);
CREATE INDEX idx_llm_executions_selection ON llm_executions(user_selection);
```

## Advanced Features Schema

### Working Trees (`working_trees`)

Branch-like working environments for change management.

```sql
CREATE TABLE working_trees (
    id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
    name TEXT NOT NULL,
    description TEXT,

    -- Tree state
    base_changeset_id TEXT REFERENCES changesets(id),
    head_changeset_id TEXT REFERENCES changesets(id),

    -- Metadata
    identity_id TEXT NOT NULL REFERENCES identities(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Status
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'merged', 'abandoned'))
);
```

### Conflict Resolutions (`conflict_resolutions`)

Track resolved merge conflicts.

```sql
CREATE TABLE conflict_resolutions (
    id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),

    -- Conflict identification
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,

    -- Conflicting changesets
    changeset_1_id TEXT NOT NULL REFERENCES changesets(id),
    changeset_2_id TEXT NOT NULL REFERENCES changesets(id),

    -- Resolution
    resolution_strategy TEXT NOT NULL,  -- 'manual', 'crdt', 'last_write_wins'
    resolved_state TEXT CHECK (json_valid(resolved_state)),
    resolver_identity_id TEXT NOT NULL REFERENCES identities(id),

    -- Timestamps
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Schema Migrations

### Migration Tracking (`schema_migrations`)

Track applied database migrations.

```sql
CREATE TABLE schema_migrations (
    version TEXT PRIMARY KEY,
    description TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum TEXT,
    execution_time_ms INTEGER
);

-- Current schema version tracking
INSERT INTO schema_migrations (version, description)
VALUES ('011', 'Remove branch management, optimize performance');
```

## Performance Optimization

### Partitioning Strategy

For large datasets, implement time-based partitioning:

```sql
-- Example: Partition change_events by month
CREATE TABLE change_events_2025_01 (
    -- Same structure as change_events
    CHECK (timestamp >= '2025-01-01' AND timestamp < '2025-02-01')
);

-- Create monthly partitions as needed
CREATE TABLE change_events_2025_02 (
    CHECK (timestamp >= '2025-02-01' AND timestamp < '2025-03-01')
);
```

### Materialized Views

Pre-computed aggregations for performance:

```sql
-- Node count by type and parent (refreshed periodically)
CREATE VIEW node_counts_by_parent AS
SELECT
    COALESCE(parent_id, 'root') as parent_id,
    node_type,
    COUNT(*) as node_count,
    MAX(updated_at) as last_updated
FROM structure_nodes
WHERE deleted_at IS NULL  -- If soft deletes implemented
GROUP BY parent_id, node_type;

-- Changeset statistics
CREATE VIEW changeset_statistics AS
SELECT
    status,
    COUNT(*) as count,
    AVG(julianday(COALESCE(merged_at, CURRENT_TIMESTAMP)) -
        julianday(created_at)) as avg_duration_days
FROM changesets
GROUP BY status;
```

## Data Integrity Constraints

### Referential Integrity
```sql
-- Ensure parent-child relationships are valid
CREATE TRIGGER validate_parent_child_relationship
BEFORE INSERT ON structure_nodes
WHEN NEW.parent_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (SELECT 1 FROM structure_nodes WHERE id = NEW.parent_id)
        THEN RAISE(ABORT, 'Parent node does not exist')
    END;
END;

-- Prevent circular references
CREATE TRIGGER prevent_circular_references
BEFORE INSERT ON structure_nodes
WHEN NEW.parent_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NEW.id = NEW.parent_id
        THEN RAISE(ABORT, 'Node cannot be its own parent')
    END;
END;
```

### Business Logic Constraints
```sql
-- Ensure proper node type hierarchy (layers -> domains -> terms)
CREATE TRIGGER validate_node_hierarchy
BEFORE INSERT ON structure_nodes
WHEN NEW.parent_id IS NOT NULL
BEGIN
    SELECT CASE
        WHEN NEW.node_type = 'layer'
        THEN RAISE(ABORT, 'Layers cannot have parents')

        WHEN NEW.node_type = 'domain' AND
             (SELECT node_type FROM structure_nodes WHERE id = NEW.parent_id) != 'layer'
        THEN RAISE(ABORT, 'Domains must have layer parents')

        WHEN NEW.node_type = 'term' AND
             (SELECT node_type FROM structure_nodes WHERE id = NEW.parent_id) != 'domain'
        THEN RAISE(ABORT, 'Terms must have domain parents')
    END;
END;
```

## Backup and Recovery

### Backup Schema
```sql
-- Backup metadata table
CREATE TABLE backup_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_type TEXT NOT NULL,  -- 'full', 'incremental'
    backup_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    size_bytes INTEGER,
    checksum TEXT,
    status TEXT DEFAULT 'completed'
);
```

### Recovery Procedures
```sql
-- Point-in-time recovery using change events
SELECT entity_id, entity_type, after_state
FROM change_events
WHERE timestamp <= '2025-01-15 12:00:00'
  AND processing_status = 'processed'
ORDER BY timestamp DESC;
```

## Usage Examples

### Complex Queries

#### Hierarchical Queries
```sql
-- Get full path for a node
WITH RECURSIVE node_path AS (
    SELECT id, title, parent_id, 0 as level, title as path
    FROM structure_nodes
    WHERE id = 'target-node-id'

    UNION ALL

    SELECT s.id, s.title, s.parent_id, np.level + 1,
           s.title || ' > ' || np.path
    FROM structure_nodes s
    JOIN node_path np ON s.id = np.parent_id
)
SELECT path FROM node_path ORDER BY level DESC LIMIT 1;
```

#### Change Analysis
```sql
-- Most active contributors in last 30 days
SELECT i.display_name,
       COUNT(*) as change_count,
       COUNT(DISTINCT ce.entity_id) as entities_modified
FROM change_events ce
JOIN identities i ON ce.identity_id = i.id
WHERE ce.timestamp >= date('now', '-30 days')
GROUP BY ce.identity_id, i.display_name
ORDER BY change_count DESC;
```

#### Performance Analytics
```sql
-- LLM execution success rates by provider
SELECT provider,
       COUNT(*) as total_executions,
       COUNT(CASE WHEN error_message IS NULL THEN 1 END) as successful,
       AVG(duration_ms) as avg_duration,
       AVG(cost_usd) as avg_cost
FROM llm_executions
WHERE created_at >= date('now', '-7 days')
GROUP BY provider;
```

## Best Practices

### Schema Design
1. **Normalize appropriately**: Balance normalization with query performance
2. **Use constraints**: Enforce business rules at database level
3. **Index strategically**: Create indexes based on actual query patterns
4. **Version everything**: Include version fields for all entities

### Performance
1. **Analyze queries**: Use EXPLAIN QUERY PLAN regularly
2. **Monitor growth**: Track table sizes and query performance
3. **Archive old data**: Implement data retention policies
4. **Vacuum regularly**: Run VACUUM to reclaim space

### Integrity
1. **Use transactions**: Wrap related operations in transactions
2. **Validate data**: Implement CHECK constraints and triggers
3. **Backup frequently**: Automated backup strategies
4. **Test migrations**: Validate schema changes on copies first