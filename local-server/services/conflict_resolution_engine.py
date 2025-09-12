"""
Advanced Conflict Resolution Engine - Intelligent conflict detection and resolution

This module provides sophisticated conflict detection with semantic analysis and
both automatic and guided manual resolution capabilities for collaborative workflows.
"""

import uuid
import json
from typing import List, Optional, Dict, Any, Set, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text
from dataclasses import dataclass

from enum import Enum
from services.version_manager import VersionManager
from services.version_manager import EntityVersion, ChangeState
from utils.logger import get_logger

logger = get_logger(__name__)


class ConflictType(Enum):
    """Types of conflicts that can occur."""
    CONCURRENT_MODIFICATION = "concurrent_modification"
    STRUCTURAL_CONFLICT = "structural_conflict"
    DEPENDENCY_CONFLICT = "dependency_conflict"
    SEMANTIC_CONFLICT = "semantic_conflict"


@dataclass
class ConflictDescriptor:
    """Describes a conflict between entity versions."""
    conflict_id: str
    conflict_type: ConflictType
    entity_type: str
    entity_id: str
    local_version: EntityVersion
    remote_version: EntityVersion
    conflict_details: Dict[str, Any]
    resolution_suggestions: List[Dict[str, Any]]
    severity: str  # 'low', 'medium', 'high'


@dataclass
class ConflictAnalysis:
    """Result of conflict analysis between versions."""
    has_conflicts: bool
    conflict_descriptors: List[ConflictDescriptor]
    auto_resolvable: int
    manual_required: int
    high_severity: int


class IntelligentConflictDetector:
    """Advanced conflict detection with semantic analysis."""
    
    def __init__(self, version_manager: VersionManager, nlp_analyzer=None):
        """
        Initialize the conflict detector.
        
        Args:
            version_manager: Version management service
            nlp_analyzer: Optional NLP analyzer for semantic analysis
        """
        self.version_manager = version_manager
        self.nlp_analyzer = nlp_analyzer  # Optional NLP for semantic analysis
        logger.info("IntelligentConflictDetector initialized")
    
    def detect_conflicts(self, local_versions: List[EntityVersion], 
                        remote_versions: List[EntityVersion]) -> List[ConflictDescriptor]:
        """
        Detect and categorize conflicts between version sets.
        
        Args:
            local_versions: Local entity versions
            remote_versions: Remote entity versions
            
        Returns:
            List of ConflictDescriptor objects
        """
        logger.info(f"Detecting conflicts between {len(local_versions)} local and {len(remote_versions)} remote versions")
        
        conflicts = []
        
        # Group versions by entity
        local_by_entity = self._group_versions_by_entity(local_versions)
        remote_by_entity = self._group_versions_by_entity(remote_versions)
        
        # Find entities with conflicting versions
        conflicting_entities = set(local_by_entity.keys()) & set(remote_by_entity.keys())
        
        for entity_key in conflicting_entities:
            local_version = local_by_entity[entity_key][-1]  # Latest local version
            remote_version = remote_by_entity[entity_key][-1]  # Latest remote version
            
            conflict_descriptor = self._analyze_version_conflict(local_version, remote_version)
            if conflict_descriptor:
                conflicts.append(conflict_descriptor)
        
        logger.info(f"Detected {len(conflicts)} conflicts")
        return conflicts
    
    def analyze_conflicts(self, conflicts: List[ConflictDescriptor]) -> ConflictAnalysis:
        """
        Analyze conflict set to determine resolution complexity.
        
        Args:
            conflicts: List of conflict descriptors
            
        Returns:
            ConflictAnalysis with summary statistics
        """
        auto_resolvable = sum(1 for c in conflicts if c.severity == "low")
        manual_required = len(conflicts) - auto_resolvable
        high_severity = sum(1 for c in conflicts if c.severity == "high")
        
        return ConflictAnalysis(
            has_conflicts=len(conflicts) > 0,
            conflict_descriptors=conflicts,
            auto_resolvable=auto_resolvable,
            manual_required=manual_required,
            high_severity=high_severity
        )
    
    def _group_versions_by_entity(self, versions: List[EntityVersion]) -> Dict[Tuple[str, str], List[EntityVersion]]:
        """Group versions by entity type and ID."""
        grouped = {}
        for version in versions:
            key = (version.entity_type, version.entity_id)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(version)
        
        # Sort by timestamp within each group
        for key in grouped:
            grouped[key].sort(key=lambda v: v.created_at)
        
        return grouped
    
    def _analyze_version_conflict(self, local_version: EntityVersion, 
                                 remote_version: EntityVersion) -> Optional[ConflictDescriptor]:
        """
        Analyze specific version conflict and generate resolution suggestions.
        
        Args:
            local_version: Local entity version
            remote_version: Remote entity version
            
        Returns:
            ConflictDescriptor if conflict detected, None otherwise
        """
        # Skip if versions are identical
        if self._versions_identical(local_version, remote_version):
            return None
        
        # Compare content structures
        structural_conflicts = self._detect_structural_conflicts(local_version.content, remote_version.content)
        
        # Check for dependency conflicts
        dependency_conflicts = self._detect_dependency_conflicts(local_version, remote_version)
        
        # Semantic analysis if NLP available
        semantic_conflicts = []
        if self.nlp_analyzer:
            semantic_conflicts = self._detect_semantic_conflicts(local_version, remote_version)
        
        # Determine primary conflict type and severity
        if semantic_conflicts:
            conflict_type = ConflictType.SEMANTIC_CONFLICT
            severity = "high"
        elif dependency_conflicts:
            conflict_type = ConflictType.DEPENDENCY_CONFLICT
            severity = "medium"
        elif structural_conflicts:
            conflict_type = ConflictType.STRUCTURAL_CONFLICT
            severity = "medium"
        else:
            conflict_type = ConflictType.CONCURRENT_MODIFICATION
            severity = "low"
        
        # Generate resolution suggestions
        suggestions = self._generate_resolution_suggestions(
            conflict_type, local_version, remote_version
        )
        
        return ConflictDescriptor(
            conflict_id=str(uuid.uuid4()),
            conflict_type=conflict_type,
            entity_type=local_version.entity_type,
            entity_id=local_version.entity_id,
            local_version_id=local_version.id,
            remote_version_id=remote_version.id,
            conflict_details={
                "structural_conflicts": structural_conflicts,
                "dependency_conflicts": dependency_conflicts,
                "semantic_conflicts": semantic_conflicts,
                "local_author": local_version.author_id,
                "remote_author": remote_version.author_id,
                "local_timestamp": local_version.created_at.isoformat(),
                "remote_timestamp": remote_version.created_at.isoformat()
            },
            resolution_suggestions=suggestions,
            severity=severity,
            created_at=datetime.now(timezone.utc)
        )
    
    def _versions_identical(self, local_version: EntityVersion, remote_version: EntityVersion) -> bool:
        """Check if two versions are functionally identical."""
        return (local_version.content == remote_version.content and
                local_version.author_id == remote_version.author_id and
                abs((local_version.created_at - remote_version.created_at).total_seconds()) < 1)
    
    def _detect_structural_conflicts(self, local_content: Dict, remote_content: Dict) -> List[Dict[str, Any]]:
        """Detect structural differences in entity content."""
        conflicts = []
        
        # Check for field-level conflicts
        all_fields = set(local_content.keys()) | set(remote_content.keys())
        
        for field in all_fields:
            local_value = local_content.get(field)
            remote_value = remote_content.get(field)
            
            if local_value != remote_value:
                conflict_severity = self._assess_field_conflict_severity(field, local_value, remote_value)
                
                conflicts.append({
                    "field": field,
                    "local_value": local_value,
                    "remote_value": remote_value,
                    "conflict_type": "field_value_mismatch",
                    "severity": conflict_severity,
                    "is_addition": local_value is None or remote_value is None,
                    "is_deletion": local_value is None or remote_value is None,
                    "data_type_conflict": type(local_value) != type(remote_value) if local_value is not None and remote_value is not None else False
                })
        
        return conflicts
    
    def _assess_field_conflict_severity(self, field: str, local_value: Any, remote_value: Any) -> str:
        """Assess severity of field-level conflict."""
        # Critical fields that indicate high-severity conflicts
        critical_fields = {"id", "type", "key", "name", "title"}
        
        if field in critical_fields:
            return "high"
        
        # Type changes are medium severity
        if local_value is not None and remote_value is not None and type(local_value) != type(remote_value):
            return "medium"
        
        # Simple value changes are low severity
        return "low"
    
    def _detect_dependency_conflicts(self, local_version: EntityVersion, remote_version: EntityVersion) -> List[Dict[str, Any]]:
        """Detect dependency-related conflicts."""
        conflicts = []
        
        # Extract dependencies from content
        local_deps = self._extract_dependencies(local_version.content)
        remote_deps = self._extract_dependencies(remote_version.content)
        
        # Find conflicting dependencies
        all_dep_keys = set(local_deps.keys()) | set(remote_deps.keys())
        
        for dep_key in all_dep_keys:
            local_dep = local_deps.get(dep_key)
            remote_dep = remote_deps.get(dep_key)
            
            if local_dep != remote_dep:
                conflicts.append({
                    "dependency_key": dep_key,
                    "local_dependency": local_dep,
                    "remote_dependency": remote_dep,
                    "conflict_type": "dependency_mismatch"
                })
        
        return conflicts
    
    def _extract_dependencies(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract dependency information from entity content."""
        dependencies = {}
        
        # Look for common dependency patterns
        dependency_fields = ["parent_id", "referenced_entities", "links", "dependencies"]
        
        for field in dependency_fields:
            if field in content:
                dependencies[field] = content[field]
        
        return dependencies
    
    def _detect_semantic_conflicts(self, local_version: EntityVersion, remote_version: EntityVersion) -> List[Dict[str, Any]]:
        """Detect semantic conflicts using NLP analysis."""
        if not self.nlp_analyzer:
            return []
        
        conflicts = []
        
        try:
            # Extract text content for semantic analysis
            local_text = self._extract_text_content(local_version.content)
            remote_text = self._extract_text_content(remote_version.content)
            
            if local_text and remote_text:
                # Semantic similarity analysis
                similarity = self.nlp_analyzer.compute_similarity(local_text, remote_text)
                
                if similarity < 0.5:  # Low semantic similarity indicates potential conflict
                    conflicts.append({
                        "conflict_type": "semantic_divergence",
                        "similarity_score": similarity,
                        "local_text": local_text,
                        "remote_text": remote_text,
                        "severity": "high" if similarity < 0.3 else "medium"
                    })
        
        except Exception as e:
            logger.warning(f"Semantic conflict detection failed: {e}")
        
        return conflicts
    
    def _extract_text_content(self, content: Dict[str, Any]) -> str:
        """Extract text content from entity for semantic analysis."""
        text_fields = ["title", "description", "content", "text", "body"]
        
        text_parts = []
        for field in text_fields:
            if field in content and isinstance(content[field], str):
                text_parts.append(content[field])
        
        return " ".join(text_parts) if text_parts else ""
    
    def _generate_resolution_suggestions(self, conflict_type: ConflictType,
                                       local_version: EntityVersion, 
                                       remote_version: EntityVersion) -> List[Dict[str, Any]]:
        """Generate resolution suggestions based on conflict analysis."""
        suggestions = []
        
        if conflict_type == ConflictType.CONCURRENT_MODIFICATION:
            suggestions.extend([
                {
                    "type": "take_local",
                    "description": "Keep local changes",
                    "confidence": 0.5,
                    "rationale": "Preserves current working state"
                },
                {
                    "type": "take_remote", 
                    "description": "Accept remote changes",
                    "confidence": 0.5,
                    "rationale": "Incorporates latest collaborative changes"
                },
                {
                    "type": "merge_fields",
                    "description": "Merge non-conflicting fields automatically",
                    "confidence": 0.8,
                    "rationale": "Combines compatible changes from both versions"
                }
            ])
        
        elif conflict_type == ConflictType.STRUCTURAL_CONFLICT:
            suggestions.extend([
                {
                    "type": "manual_merge",
                    "description": "Manual resolution required due to structural changes",
                    "confidence": 0.3,
                    "rationale": "Structural changes need human review"
                },
                {
                    "type": "create_variant",
                    "description": "Create separate entity variants",
                    "confidence": 0.6,
                    "rationale": "Preserves both structural approaches"
                }
            ])
        
        elif conflict_type == ConflictType.DEPENDENCY_CONFLICT:
            suggestions.extend([
                {
                    "type": "resolve_dependencies",
                    "description": "Update dependencies to compatible versions",
                    "confidence": 0.7,
                    "rationale": "Maintains system consistency"
                },
                {
                    "type": "manual_dependency_review",
                    "description": "Review dependency changes manually",
                    "confidence": 0.4,
                    "rationale": "Dependencies require careful consideration"
                }
            ])
        
        elif conflict_type == ConflictType.SEMANTIC_CONFLICT:
            suggestions.extend([
                {
                    "type": "semantic_merge",
                    "description": "Attempt semantic merging with NLP assistance",
                    "confidence": 0.6,
                    "rationale": "Combines semantic meaning from both versions"
                },
                {
                    "type": "expert_review",
                    "description": "Requires domain expert review",
                    "confidence": 0.3,
                    "rationale": "Semantic conflicts need domain knowledge"
                }
            ])
        
        # Add timestamp-based suggestion if there's a clear temporal order
        time_diff = (remote_version.created_at - local_version.created_at).total_seconds()
        if abs(time_diff) > 300:  # 5 minutes difference
            newer_version = "remote" if time_diff > 0 else "local"
            suggestions.append({
                "type": f"take_{newer_version}",
                "description": f"Use newer version ({newer_version})",
                "confidence": 0.7,
                "rationale": "Temporal ordering suggests this is the intended version"
            })
        
        return suggestions


class ConflictResolutionEngine:
    """Handles automatic and guided manual conflict resolution."""
    
    def __init__(self, db: Session, conflict_detector: IntelligentConflictDetector, 
                 version_manager: VersionManager):
        """
        Initialize the resolution engine.
        
        Args:
            db: Database session
            conflict_detector: Conflict detection service
            version_manager: Version management service
        """
        self.db = db
        self.conflict_detector = conflict_detector
        self.version_manager = version_manager
        logger.info("ConflictResolutionEngine initialized")
    
    def resolve_conflicts_auto(self, conflicts: List[ConflictDescriptor]) -> Dict[str, Any]:
        """
        Attempt automatic resolution of conflicts.
        
        Args:
            conflicts: List of conflicts to resolve
            
        Returns:
            Resolution results
        """
        logger.info(f"Attempting automatic resolution of {len(conflicts)} conflicts")
        
        auto_resolved = []
        manual_required = []
        
        for conflict in conflicts:
            if conflict.severity == "low":
                resolution = self._auto_resolve_conflict(conflict)
                if resolution:
                    auto_resolved.append(resolution)
                    # Store resolution in database
                    self._store_conflict_resolution(conflict, resolution)
                else:
                    manual_required.append(conflict)
            else:
                manual_required.append(conflict)
        
        success_rate = len(auto_resolved) / len(conflicts) if conflicts else 1.0
        
        logger.info(f"Auto-resolved {len(auto_resolved)}/{len(conflicts)} conflicts (success rate: {success_rate:.1%})")
        
        return {
            "auto_resolved": auto_resolved,
            "manual_required": manual_required,
            "success_rate": success_rate,
            "total_conflicts": len(conflicts)
        }
    
    def resolve_conflict_manual(self, conflict_id: str, resolution_choice: Dict[str, Any],
                               resolved_by: str) -> Dict[str, Any]:
        """
        Apply manual conflict resolution.
        
        Args:
            conflict_id: Conflict identifier
            resolution_choice: User's resolution choice
            resolved_by: User performing resolution
            
        Returns:
            Resolution result
        """
        logger.info(f"Applying manual resolution for conflict {conflict_id} by {resolved_by}")
        
        # Get conflict details
        conflict = self._get_conflict(conflict_id)
        if not conflict:
            return {"status": "error", "message": f"Conflict {conflict_id} not found"}
        
        try:
            # Apply resolution based on choice
            if resolution_choice["type"] == "take_local":
                local_version = self.version_manager.get_version(conflict.local_version_id)
                merged_content = local_version.content
                
            elif resolution_choice["type"] == "take_remote":
                remote_version = self.version_manager.get_version(conflict.remote_version_id)
                merged_content = remote_version.content
                
            elif resolution_choice["type"] == "custom_merge":
                merged_content = resolution_choice["merged_content"]
                
            elif resolution_choice["type"] == "merge_fields":
                local_version = self.version_manager.get_version(conflict.local_version_id)
                remote_version = self.version_manager.get_version(conflict.remote_version_id)
                merged_content = self._merge_fields_automatically(local_version.content, remote_version.content)
                
            else:
                return {"status": "error", "message": f"Unknown resolution type: {resolution_choice['type']}"}
            
            # Create resolved version
            resolved_version = self.version_manager.create_version(
                entity_type=conflict.entity_type,
                entity_id=conflict.entity_id,
                content=merged_content,
                author_id=resolved_by,
                state=ChangeState.MERGED
            )
            
            # Record resolution
            resolution_result = {
                "conflict_id": conflict_id,
                "resolution_type": resolution_choice["type"],
                "resolved_version_id": resolved_version.id,
                "resolved_by": resolved_by,
                "resolved_at": datetime.now(timezone.utc).isoformat()
            }
            
            self._store_conflict_resolution(conflict, resolution_result)
            
            logger.info(f"Successfully resolved conflict {conflict_id}")
            
            return {
                "status": "resolved",
                "conflict_id": conflict_id,
                "resolved_version_id": resolved_version.id,
                "resolution_type": resolution_choice["type"]
            }
            
        except Exception as e:
            logger.error(f"Failed to resolve conflict {conflict_id}: {e}")
            return {"status": "error", "message": f"Failed to resolve conflict: {e}"}
    
    def get_conflict_suggestions(self, conflict_id: str) -> List[Dict[str, Any]]:
        """Get resolution suggestions for a conflict."""
        conflict = self._get_conflict(conflict_id)
        if not conflict:
            return []
        
        return conflict.resolution_suggestions
    
    def _auto_resolve_conflict(self, conflict: ConflictDescriptor) -> Optional[Dict[str, Any]]:
        """Attempt automatic resolution using CRDT and heuristics."""
        # Use highest confidence suggestion
        best_suggestion = max(conflict.resolution_suggestions, 
                            key=lambda x: x.get("confidence", 0),
                            default=None)
        
        if not best_suggestion or best_suggestion["confidence"] < 0.7:
            return None  # Confidence too low for auto-resolution
        
        try:
            if best_suggestion["type"] == "merge_fields":
                local_version = self.version_manager.get_version(conflict.local_version_id)
                remote_version = self.version_manager.get_version(conflict.remote_version_id)
                
                merged_content = self._merge_fields_automatically(
                    local_version.content,
                    remote_version.content
                )
                
                resolved_version = self.version_manager.create_version(
                    entity_type=conflict.entity_type,
                    entity_id=conflict.entity_id,
                    content=merged_content,
                    author_id="system",
                    state=ChangeState.MERGED
                )
                
                return {
                    "conflict_id": conflict.conflict_id,
                    "resolution_type": "auto_merge_fields",
                    "resolved_version_id": resolved_version.id,
                    "confidence": best_suggestion["confidence"]
                }
                
        except Exception as e:
            logger.warning(f"Auto-resolution failed for conflict {conflict.conflict_id}: {e}")
            return None
        
        return None
    
    def _merge_fields_automatically(self, local_content: Dict[str, Any], 
                                   remote_content: Dict[str, Any]) -> Dict[str, Any]:
        """Merge fields automatically using CRDT-like semantics."""
        merged = {}
        
        all_fields = set(local_content.keys()) | set(remote_content.keys())
        
        for field in all_fields:
            local_value = local_content.get(field)
            remote_value = remote_content.get(field)
            
            if local_value == remote_value:
                # No conflict, use either value
                merged[field] = local_value
            elif local_value is None:
                # Local is missing, use remote
                merged[field] = remote_value
            elif remote_value is None:
                # Remote is missing, use local
                merged[field] = local_value
            else:
                # Conflict - use more recent or longer value as heuristic
                if isinstance(local_value, str) and isinstance(remote_value, str):
                    merged[field] = local_value if len(local_value) > len(remote_value) else remote_value
                else:
                    # Default to local value
                    merged[field] = local_value
        
        return merged
    
    def _get_conflict(self, conflict_id: str) -> Optional[ConflictDescriptor]:
        """Get conflict by ID from database."""
        try:
            result = self.db.execute(
                text("SELECT * FROM conflict_descriptors WHERE conflict_id = ?"),
                (conflict_id,)
            ).fetchone()
            
            return row_to_conflict_descriptor(result) if result else None
            
        except Exception as e:
            logger.error(f"Failed to get conflict {conflict_id}: {e}")
            return None
    
    def _store_conflict_resolution(self, conflict: ConflictDescriptor, 
                                  resolution: Dict[str, Any]) -> None:
        """Store conflict resolution in database."""
        try:
            self.db.execute(
                text("""
                    UPDATE conflict_descriptors 
                    SET resolved_at = ?, resolved_by = ?, resolution_choice = ?
                    WHERE conflict_id = ?
                """),
                (
                    datetime.now(timezone.utc).isoformat(),
                    resolution.get("resolved_by", "system"),
                    json.dumps(resolution),
                    conflict.conflict_id
                )
            )
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to store conflict resolution: {e}")
            self.db.rollback()