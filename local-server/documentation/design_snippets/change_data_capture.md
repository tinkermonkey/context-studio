> Is operational transformation a type of change data capture, or is change data capture a different pattern?

Great question! **Change Data Capture (CDC) and Operational Transformation (OT) are different patterns that serve different purposes**, though they can be used together in some architectures.

## Change Data Capture (CDC)

CDC is about **detecting and capturing changes** as they happen:

**Purpose**: Identify what changed, when, and how
**Focus**: Data synchronization and replication
**Typical Use Cases**: 
- Database replication
- Data warehousing/ETL
- Event-driven architectures
- Audit logging

**Example**: Your SQLite triggers capturing changes to the `graph_events` table - that's classic CDC.

```sql
-- This is CDC - capturing the change
CREATE TRIGGER node_update_trigger
AFTER UPDATE ON nodes
BEGIN
    INSERT INTO graph_events (event_type, entity_id, old_data, new_data)
    VALUES ('node_updated', NEW.id, OLD.properties, NEW.properties);
END;
```

## Operational Transformation (OT)

OT is about **resolving conflicts** when multiple changes happen concurrently:

**Purpose**: Merge concurrent edits while preserving intent
**Focus**: Conflict resolution and consistency
**Typical Use Cases**:
- Collaborative editing (Google Docs)
- Real-time multi-user applications  
- Distributed systems with concurrent modifications

**Example**: When two users edit the same node simultaneously, OT determines how to merge those changes.

```python
# This is OT - transforming operations to resolve conflicts
def transform_operations(op1, op2):
    """Transform op1 given that op2 happened first"""
    if op1.entity_id == op2.entity_id:
        # Both operations affect same entity - need transformation
        if op1.operation_type == 'update' and op2.operation_type == 'update':
            # Merge the property updates
            merged_properties = {**op2.new_value, **op1.new_value}
            return op1._replace(new_value=merged_properties)
    return op1  # No transformation needed
```

## How They Work Together

In your collaborative graph system, you're using **both patterns**:

### 1. **CDC for Local Change Tracking**
```python
# Capturing what changed locally
def record_operation(self, operation_type: str, entity_type: str, 
                    entity_id: str, old_value: Dict = None, 
                    new_value: Dict = None):
    operation = ChangeOperation(  # This is CDC
        operation_type=operation_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value
    )
```

### 2. **OT for Conflict Resolution**
```python
# Resolving conflicts when merging changes
def resolve_concurrent_modifications(self, local_op, server_op):
    """This is OT - transforming operations to resolve conflicts"""
    if local_op.entity_id == server_op.entity_id:
        # Transform local operation based on what happened on server
        return self.transform_operation(local_op, server_op)
```

## Relationship Diagram

```
User Makes Edit → CDC Captures Change → Store in Changeset
                                              ↓
Multiple Users' Changes → Conflict Detection → OT Resolves Conflicts → Apply to Primary Copy
```

## Other Related Patterns

**Conflict-Free Replicated Data Types (CRDTs)**: Another approach to handle concurrent changes without explicit conflict resolution - the data structure itself handles merges automatically.

**Event Sourcing**: Stores the sequence of changes (events) as the primary source of truth, rather than just the current state.

**Three-Way Merge**: Git-style conflict resolution using a common ancestor.

## In Your System

Your architecture elegantly combines both:

1. **CDC Phase**: SQLite triggers and your `ChangeTracker` capture all modifications
2. **OT Phase**: Your `ConflictResolver` and merge logic handle concurrent changes

This is a robust pattern used by systems like:
- **Git**: CDC (tracking file changes) + OT (three-way merge)
- **Google Docs**: CDC (keystroke capture) + OT (operational transformation)
- **CouchDB**: CDC (document changes) + OT (revision trees for conflicts)

So your instinct to use both patterns together is spot-on - they complement each other perfectly for collaborative editing scenarios!

> that's great, thank you. the local first database approach seems very feasible. Now, I want to explore how users will synchronize their suggested edits with each other via a primary copy which lives in a shared location. My thought is to capture edits directly, record each change operation that a user makes locally, and then allow the user to condense their changes before pushing them to the primary copy where other users can vote on whether the changes should be accepted. In that model the primary copy is the source of truth, and a user's local changes are considered provisional until accepted. Does that approach make sense and are there norms for doing this that I should consider?

Your approach is excellent and aligns well with established patterns in distributed systems! This is essentially a **operational transformation** model combined with **optimistic replication** - very similar to how collaborative editing systems like Google Docs, Git, and modern databases handle distributed changes.

## Architectural Pattern: **Propose-Review-Merge with Operational Transform**

Your model maps closely to these established patterns:

### 1. **Git-like Workflow** (Branch-Merge-Review)
- Local changes = feature branch
- Primary copy = main branch  
- Voting/approval = pull request review
- Merge = accepting changes

### 2. **Collaborative Editing** (Google Docs, Figma)
- Operational transformation for conflict resolution
- Eventually consistent with authoritative server state

### 3. **Database Replication** (Multi-master with conflict resolution)
- Local writes with eventual consistency
- Conflict resolution through voting/rules

## Implementation Architecture

Here's a robust approach following industry norms:

### 1. **Change Operation Capture**

```python
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

@dataclass
class ChangeOperation:
    id: str
    operation_type: str  # 'create_node', 'update_node', 'delete_node', 'create_edge', etc.
    entity_type: str     # 'node' or 'edge'
    entity_id: str
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    user_id: str = None
    local_sequence: int = None  # For ordering operations within a changeset
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.id is None:
            self.id = str(uuid.uuid4())

@dataclass
class ChangeSet:
    id: str
    title: str
    description: str
    operations: List[ChangeOperation]
    author_id: str
    created_at: datetime
    status: str = "draft"  # draft, proposed, approved, rejected, merged
    base_version: str = None  # Version of primary copy this is based on
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.id is None:
            self.id = str(uuid.uuid4())

class LocalChangeTracker:
    def __init__(self, db_path: str, user_id: str):
        self.db_path = db_path
        self.user_id = user_id
        self.current_changeset = None
        self.sequence_counter = 0
        self._setup_database()
    
    def _setup_database(self):
        """Setup local database tables for change tracking"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS changesets (
                id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                author_id TEXT,
                created_at TEXT,
                status TEXT,
                base_version TEXT
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS change_operations (
                id TEXT PRIMARY KEY,
                changeset_id TEXT,
                operation_type TEXT,
                entity_type TEXT,
                entity_id TEXT,
                old_value TEXT,
                new_value TEXT,
                timestamp TEXT,
                user_id TEXT,
                local_sequence INTEGER,
                FOREIGN KEY (changeset_id) REFERENCES changesets (id)
            )
        ''')
        conn.commit()
        conn.close()
    
    def begin_changeset(self, title: str, description: str = ""):
        """Start a new changeset"""
        self.current_changeset = ChangeSet(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            author_id=self.user_id,
            created_at=datetime.now(),
            operations=[],
            base_version=self._get_current_primary_version()
        )
        self.sequence_counter = 0
        return self.current_changeset.id
    
    def record_operation(self, operation_type: str, entity_type: str, 
                        entity_id: str, old_value: Dict = None, 
                        new_value: Dict = None):
        """Record a change operation"""
        if not self.current_changeset:
            raise ValueError("No active changeset. Call begin_changeset() first.")
        
        operation = ChangeOperation(
            id=str(uuid.uuid4()),
            operation_type=operation_type,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            user_id=self.user_id,
            local_sequence=self.sequence_counter
        )
        
        self.current_changeset.operations.append(operation)
        self.sequence_counter += 1
        
        # Persist to local database
        self._persist_operation(operation)
        
        return operation.id
    
    def commit_changeset(self) -> str:
        """Finalize the current changeset"""
        if not self.current_changeset:
            raise ValueError("No active changeset to commit.")
        
        changeset_id = self.current_changeset.id
        self._persist_changeset(self.current_changeset)
        self.current_changeset = None
        return changeset_id
```

### 2. **Change Condensation & Optimization**

```python
class ChangeOptimizer:
    """Optimize and condense changes before proposing"""
    
    def optimize_changeset(self, changeset: ChangeSet) -> ChangeSet:
        """Apply various optimizations to reduce changeset size"""
        operations = changeset.operations.copy()
        
        # Remove redundant operations
        operations = self._remove_redundant_operations(operations)
        
        # Merge consecutive updates to same entity
        operations = self._merge_consecutive_updates(operations)
        
        # Remove create-delete pairs
        operations = self._remove_create_delete_pairs(operations)
        
        # Sort operations for optimal application order
        operations = self._sort_operations_for_application(operations)
        
        return ChangeSet(
            id=changeset.id,
            title=changeset.title,
            description=changeset.description,
            operations=operations,
            author_id=changeset.author_id,
            created_at=changeset.created_at,
            base_version=changeset.base_version
        )
    
    def _remove_redundant_operations(self, operations: List[ChangeOperation]) -> List[ChangeOperation]:
        """Remove operations that are overridden by later operations"""
        # Keep track of the latest operation for each entity
        latest_ops = {}
        
        for op in operations:
            key = (op.entity_type, op.entity_id)
            if key not in latest_ops or op.local_sequence > latest_ops[key].local_sequence:
                latest_ops[key] = op
        
        return list(latest_ops.values())
    
    def _merge_consecutive_updates(self, operations: List[ChangeOperation]) -> List[ChangeOperation]:
        """Merge consecutive update operations on the same entity"""
        if not operations:
            return operations
        
        merged = []
        current_group = [operations[0]]
        
        for op in operations[1:]:
            last_op = current_group[-1]
            
            # Check if this operation can be merged with the previous group
            if (op.entity_type == last_op.entity_type and 
                op.entity_id == last_op.entity_id and
                op.operation_type == 'update_node' and 
                last_op.operation_type == 'update_node'):
                current_group.append(op)
            else:
                # Process current group
                if len(current_group) == 1:
                    merged.append(current_group[0])
                else:
                    # Merge the group into a single operation
                    merged_op = self._merge_operation_group(current_group)
                    merged.append(merged_op)
                
                current_group = [op]
        
        # Process the final group
        if len(current_group) == 1:
            merged.append(current_group[0])
        else:
            merged_op = self._merge_operation_group(current_group)
            merged.append(merged_op)
        
        return merged
```

### 3. **Conflict Detection & Resolution**

```python
class ConflictResolver:
    """Handle conflicts between local changes and primary copy"""
    
    def detect_conflicts(self, local_changeset: ChangeSet, 
                        primary_state: Dict, 
                        base_version: str) -> List[Dict]:
        """Detect conflicts between local changes and primary copy"""
        conflicts = []
        
        for operation in local_changeset.operations:
            conflict = self._check_operation_conflict(operation, primary_state, base_version)
            if conflict:
                conflicts.append(conflict)
        
        return conflicts
    
    def _check_operation_conflict(self, operation: ChangeOperation, 
                                 primary_state: Dict, 
                                 base_version: str) -> Optional[Dict]:
        """Check if a single operation conflicts with primary state"""
        entity_key = f"{operation.entity_type}:{operation.entity_id}"
        
        if operation.operation_type == 'create_node':
            # Conflict if entity already exists in primary
            if entity_key in primary_state:
                return {
                    'type': 'create_conflict',
                    'operation_id': operation.id,
                    'reason': 'Entity already exists in primary copy',
                    'primary_value': primary_state[entity_key],
                    'local_value': operation.new_value
                }
        
        elif operation.operation_type == 'update_node':
            # Conflict if entity doesn't exist or has been modified
            if entity_key not in primary_state:
                return {
                    'type': 'update_missing',
                    'operation_id': operation.id,
                    'reason': 'Entity no longer exists in primary copy'
                }
            
            # Check if primary version differs from our base
            if (operation.old_value and 
                primary_state[entity_key] != operation.old_value):
                return {
                    'type': 'concurrent_modification',
                    'operation_id': operation.id,
                    'reason': 'Entity modified by another user',
                    'primary_value': primary_state[entity_key],
                    'local_old_value': operation.old_value,
                    'local_new_value': operation.new_value
                }
        
        elif operation.operation_type == 'delete_node':
            # Conflict if entity doesn't exist or has been modified
            if entity_key not in primary_state:
                return {
                    'type': 'delete_missing',
                    'operation_id': operation.id,
                    'reason': 'Entity already deleted from primary copy'
                }
        
        return None
    
    def resolve_conflicts(self, conflicts: List[Dict], 
                         resolution_strategy: str = 'manual') -> Dict:
        """Resolve conflicts based on strategy"""
        if resolution_strategy == 'manual':
            return {'status': 'requires_manual_resolution', 'conflicts': conflicts}
        elif resolution_strategy == 'primary_wins':
            return {'status': 'resolved', 'resolution': 'primary_copy_takes_precedence'}
        elif resolution_strategy == 'local_wins':
            return {'status': 'resolved', 'resolution': 'local_changes_take_precedence'}
        else:
            raise ValueError(f"Unknown resolution strategy: {resolution_strategy}")
```

### 4. **Proposal & Voting System**

```python
@dataclass
class ChangeProposal:
    id: str
    changeset: ChangeSet
    proposer_id: str
    title: str
    description: str
    created_at: datetime
    status: str = "open"  # open, approved, rejected, merged
    votes: List[Dict] = None
    conflicts: List[Dict] = None
    
    def __post_init__(self):
        if self.votes is None:
            self.votes = []
        if self.conflicts is None:
            self.conflicts = []

class ProposalSystem:
    def __init__(self, primary_db_path: str):
        self.primary_db_path = primary_db_path
        self._setup_database()
    
    def submit_proposal(self, changeset: ChangeSet, title: str = None, 
                       description: str = None) -> str:
        """Submit a changeset as a proposal for review"""
        # Optimize changeset before submission
        optimizer = ChangeOptimizer()
        optimized_changeset = optimizer.optimize_changeset(changeset)
        
        # Check for conflicts
        primary_state = self._get_primary_state()
        conflict_resolver = ConflictResolver()
        conflicts = conflict_resolver.detect_conflicts(
            optimized_changeset, primary_state, changeset.base_version
        )
        
        proposal = ChangeProposal(
            id=str(uuid.uuid4()),
            changeset=optimized_changeset,
            proposer_id=changeset.author_id,
            title=title or changeset.title,
            description=description or changeset.description,
            created_at=datetime.now(),
            conflicts=conflicts
        )
        
        # If there are conflicts, mark proposal as needing resolution
        if conflicts:
            proposal.status = "conflicts_detected"
        
        self._persist_proposal(proposal)
        return proposal.id
    
    def vote_on_proposal(self, proposal_id: str, user_id: str, 
                        vote: str, comment: str = None):
        """Vote on a proposal (approve/reject)"""
        proposal = self._get_proposal(proposal_id)
        
        if proposal.status not in ["open", "conflicts_detected"]:
            raise ValueError(f"Cannot vote on proposal with status: {proposal.status}")
        
        # Remove any existing vote from this user
        proposal.votes = [v for v in proposal.votes if v['user_id'] != user_id]
        
        # Add new vote
        proposal.votes.append({
            'user_id': user_id,
            'vote': vote,
            'comment': comment,
            'timestamp': datetime.now().isoformat()
        })
        
        # Check if proposal should be approved/rejected
        self._evaluate_proposal_status(proposal)
        
        self._persist_proposal(proposal)
    
    def _evaluate_proposal_status(self, proposal: ChangeProposal):
        """Evaluate if proposal should be approved/rejected based on votes"""
        if not proposal.votes:
            return
        
        approve_votes = len([v for v in proposal.votes if v['vote'] == 'approve'])
        reject_votes = len([v for v in proposal.votes if v['vote'] == 'reject'])
        
        # Simple majority rule (customize as needed)
        total_votes = approve_votes + reject_votes
        if total_votes >= 2:  # Minimum votes required
            if approve_votes > reject_votes:
                proposal.status = "approved"
            else:
                proposal.status = "rejected"
```

### 5. **Merge Strategy**

```python
class MergeManager:
    def __init__(self, primary_db_path: str):
        self.primary_db_path = primary_db_path
    
    def merge_proposal(self, proposal_id: str) -> Dict:
        """Merge an approved proposal into the primary copy"""
        proposal = self._get_proposal(proposal_id)
        
        if proposal.status != "approved":
            raise ValueError(f"Cannot merge proposal with status: {proposal.status}")
        
        # Re-check for conflicts before merging
        primary_state = self._get_primary_state()
        conflict_resolver = ConflictResolver()
        conflicts = conflict_resolver.detect_conflicts(
            proposal.changeset, primary_state, proposal.changeset.base_version
        )
        
        if conflicts:
            return {
                'status': 'merge_failed',
                'reason': 'New conflicts detected',
                'conflicts': conflicts
            }
        
        # Apply changes to primary copy
        try:
            self._apply_changeset_to_primary(proposal.changeset)
            proposal.status = "merged"
            self._persist_proposal(proposal)
            
            return {
                'status': 'merged_successfully',
                'proposal_id': proposal_id,
                'operations_applied': len(proposal.changeset.operations)
            }
        except Exception as e:
            return {
                'status': 'merge_failed',
                'reason': str(e)
            }
    
    def _apply_changeset_to_primary(self, changeset: ChangeSet):
        """Apply changeset operations to the primary database"""
        conn = sqlite3.connect(self.primary_db_path)
        
        try:
            for operation in changeset.operations:
                self._apply_operation_to_primary(conn, operation)
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
```

## Key Benefits of This Approach:

1. **Familiar Patterns**: Similar to Git, Google Docs, database replication
2. **Conflict Resolution**: Built-in conflict detection and resolution
3. **Optimistic Concurrency**: Users can work independently
4. **Democratic Process**: Voting system for change approval
5. **Atomic Operations**: Changes are applied as complete units
6. **Audit Trail**: Complete history of all changes and approvals

This approach gives you the benefits of distributed collaboration while maintaining data integrity and providing a clear approval process for changes.