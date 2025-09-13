"""
Hierarchical Diff Engine - Advanced diff algorithms for efficient change detection

This service implements sophisticated diff algorithms including hierarchical diffs,
semantic analysis, three-way merge capabilities, and intelligent conflict detection
for enterprise-scale change management and collaboration.
"""

import hashlib
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from sqlalchemy.orm import Session

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConflictDescriptor:
    """Describes a conflict between different versions."""
    conflict_type: str
    path: str
    local_value: Any
    remote_value: Any
    base_value: Optional[Any]
    resolution_suggestions: List[Dict[str, Any]]
    severity: Optional[str] = None
    conflict_id: str = ""
    confidence_score: float = 0.0
    created_at: Optional[datetime] = None


class HierarchicalDiffEngine:
    """Advanced diff algorithms for efficient change detection."""
    
    def __init__(self, db: Session, nlp_service=None):
        """Initialize the hierarchical diff engine with dependencies."""
        self.db = db
        self.nlp_service = nlp_service
        self.diff_cache = {}
        self.semantic_analyzers = {}
        self.performance_metrics = []

        logger.info("HierarchicalDiffEngine initialized with advanced diff capabilities")
        
    def compute_hierarchical_diff(self, before: Dict[str, Any], 
                                 after: Dict[str, Any]) -> Dict[str, Any]:
        """Compute hierarchical diff with structural awareness."""
        
        start_time = time.time()
        logger.info("Computing hierarchical diff with semantic analysis")
        
        diff_result = {
            'added': {},
            'removed': {},
            'modified': {},
            'moved': {},
            'unchanged': {},
            'metadata': {
                'total_changes': 0,
                'change_depth': 0,
                'change_complexity': 0,
                'computation_time_ms': 0
            }
        }
        
        # Compute structural diff
        structural_diff = self._compute_structural_diff(before, after)
        
        # Detect moved elements
        moved_elements = self._detect_moved_elements(before, after, structural_diff)
        
        # Compute semantic similarity for modified elements
        semantic_changes = self._compute_semantic_changes(structural_diff)
        
        # Analyze change patterns
        change_patterns = self._analyze_change_patterns(structural_diff, moved_elements)
        
        # Combine results
        diff_result.update({
            'structural': structural_diff,
            'moved': moved_elements,
            'semantic': semantic_changes,
            'patterns': change_patterns
        })
        
        # Calculate metadata
        diff_result['metadata'] = self._calculate_diff_metadata(diff_result)
        diff_result['metadata']['computation_time_ms'] = (time.time() - start_time) * 1000
        
        logger.info(f"Hierarchical diff completed in {diff_result['metadata']['computation_time_ms']:.2f}ms")
        
        return diff_result
    
    def compute_three_way_diff(self, base: Dict[str, Any], 
                              local: Dict[str, Any], 
                              remote: Dict[str, Any]) -> Dict[str, Any]:
        """Compute three-way diff for merge conflict detection."""
        
        start_time = time.time()
        logger.info("Computing three-way diff for merge conflict detection")
        
        # Compute diffs from base
        local_diff = self.compute_hierarchical_diff(base, local)
        remote_diff = self.compute_hierarchical_diff(base, remote)
        
        # Identify conflicts
        conflicts = self._identify_three_way_conflicts(local_diff, remote_diff)
        
        # Generate merge result
        merge_result = self._generate_merge_result(base, local_diff, remote_diff, conflicts)
        
        # Analyze conflict patterns
        conflict_analysis = self._analyze_conflict_patterns(conflicts)
        
        # Generate resolution suggestions
        resolution_suggestions = self._generate_resolution_suggestions(conflicts, conflict_analysis)
        
        computation_time = (time.time() - start_time) * 1000
        
        result = {
            'local_changes': local_diff,
            'remote_changes': remote_diff,
            'conflicts': conflicts,
            'suggested_merge': merge_result,
            'auto_mergeable': len(conflicts) == 0,
            'conflict_analysis': conflict_analysis,
            'resolution_suggestions': resolution_suggestions,
            'computation_time_ms': computation_time
        }
        
        logger.info(f"Three-way diff completed: {len(conflicts)} conflicts found in {computation_time:.2f}ms")
        
        return result
    
    def _compute_structural_diff(self, before: Dict[str, Any], 
                                after: Dict[str, Any]) -> Dict[str, Any]:
        """Compute structural differences between two objects."""
        
        result = {
            'added_keys': set(after.keys()) - set(before.keys()),
            'removed_keys': set(before.keys()) - set(after.keys()),
            'common_keys': set(before.keys()) & set(after.keys()),
            'modified_values': {},
            'type_changes': {}
        }
        
        # Check modified values in common keys
        for key in result['common_keys']:
            before_val = before[key]
            after_val = after[key]
            
            if before_val != after_val:
                # Check for type changes
                if type(before_val) != type(after_val):
                    result['type_changes'][key] = {
                        'before_type': type(before_val).__name__,
                        'after_type': type(after_val).__name__,
                        'before_value': before_val,
                        'after_value': after_val
                    }
                elif isinstance(before_val, dict) and isinstance(after_val, dict):
                    # Recursively diff nested objects
                    nested_diff = self._compute_structural_diff(before_val, after_val)
                    result['modified_values'][key] = nested_diff
                elif isinstance(before_val, list) and isinstance(after_val, list):
                    # Handle list differences
                    list_diff = self._compute_list_diff(before_val, after_val)
                    result['modified_values'][key] = list_diff
                else:
                    result['modified_values'][key] = {
                        'before': before_val,
                        'after': after_val,
                        'change_type': self._classify_value_change(before_val, after_val),
                        'similarity_score': self._calculate_semantic_similarity(before_val, after_val)
                    }
        
        return result
    
    def _compute_list_diff(self, before_list: List[Any], after_list: List[Any]) -> Dict[str, Any]:
        """Compute differences between two lists."""
        
        # Use sequence matching for list differences
        matcher = SequenceMatcher(None, before_list, after_list)
        opcodes = matcher.get_opcodes()
        
        list_changes = {
            'operations': [],
            'added_items': [],
            'removed_items': [],
            'moved_items': [],
            'similarity_ratio': matcher.ratio()
        }
        
        for op, i1, i2, j1, j2 in opcodes:
            if op == 'delete':
                removed_items = before_list[i1:i2]
                list_changes['removed_items'].extend(removed_items)
                list_changes['operations'].append({
                    'operation': 'delete',
                    'index': i1,
                    'count': i2 - i1,
                    'items': removed_items
                })
            elif op == 'insert':
                added_items = after_list[j1:j2]
                list_changes['added_items'].extend(added_items)
                list_changes['operations'].append({
                    'operation': 'insert',
                    'index': j1,
                    'count': j2 - j1,
                    'items': added_items
                })
            elif op == 'replace':
                old_items = before_list[i1:i2]
                new_items = after_list[j1:j2]
                list_changes['operations'].append({
                    'operation': 'replace',
                    'old_index': i1,
                    'new_index': j1,
                    'old_items': old_items,
                    'new_items': new_items
                })
        
        return list_changes
    
    def _detect_moved_elements(self, before: Dict[str, Any], 
                              after: Dict[str, Any],
                              structural_diff: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect elements that were moved rather than added/removed."""
        
        moved_elements = []
        
        # Look for values that appear in both added and removed sets
        added_values = {k: after[k] for k in structural_diff['added_keys']}
        removed_values = {k: before[k] for k in structural_diff['removed_keys']}
        
        for added_key, added_value in added_values.items():
            best_match = None
            best_score = 0.0
            
            for removed_key, removed_value in removed_values.items():
                similarity = self._values_semantically_equal(added_value, removed_value)
                
                if similarity > best_score and similarity > 0.8:  # High similarity threshold
                    best_score = similarity
                    best_match = removed_key
            
            if best_match:
                moved_elements.append({
                    'from_key': best_match,
                    'to_key': added_key,
                    'value': added_value,
                    'confidence': best_score,
                    'move_type': self._classify_move_type(best_match, added_key)
                })
                
                # Remove from added/removed to avoid duplicate processing
                if best_match in removed_values:
                    del removed_values[best_match]
        
        return moved_elements
    
    def _compute_semantic_changes(self, structural_diff: Dict[str, Any]) -> Dict[str, Any]:
        """Compute semantic similarity scores for changes."""
        
        semantic_changes = {}
        
        for key, change in structural_diff.get('modified_values', {}).items():
            if isinstance(change, dict) and 'before' in change and 'after' in change:
                similarity_score = self._calculate_semantic_similarity(
                    change['before'], change['after']
                )
                
                semantic_changes[key] = {
                    'similarity_score': similarity_score,
                    'change_magnitude': 1.0 - similarity_score,
                    'change_classification': self._classify_semantic_change(similarity_score),
                    'impact_level': self._assess_change_impact(key, change, similarity_score)
                }
        
        return semantic_changes
    
    def _identify_three_way_conflicts(self, local_diff: Dict[str, Any], 
                                     remote_diff: Dict[str, Any]) -> List[ConflictDescriptor]:
        """Identify conflicts in three-way merge."""
        
        conflicts = []
        
        # Check for conflicts in structural changes
        local_modified = set(local_diff['structural'].get('modified_values', {}).keys())
        remote_modified = set(remote_diff['structural'].get('modified_values', {}).keys())
        
        # Same key modified in both branches
        conflicting_keys = local_modified & remote_modified
        
        for key in conflicting_keys:
            local_change = local_diff['structural']['modified_values'][key]
            remote_change = remote_diff['structural']['modified_values'][key]
            
            # Check if the changes are actually different
            if not self._changes_are_equivalent(local_change, remote_change):
                conflict_id = hashlib.sha256(f"conflict_{key}_{time.time()}".encode()).hexdigest()[:16]
                
                conflict_type = self._classify_conflict_type(local_change, remote_change)
                confidence_score = self._calculate_conflict_confidence(local_change, remote_change)
                local_value = self._extract_change_value(local_change, 'after')
                remote_value = self._extract_change_value(remote_change, 'after')

                conflict = ConflictDescriptor(
                    conflict_id=conflict_id,
                    conflict_type=conflict_type,
                    path=key,
                    local_value=local_value,
                    remote_value=remote_value,
                    base_value=self._extract_change_value(local_change, 'before'),
                    confidence_score=confidence_score,
                    resolution_suggestions=self._generate_conflict_resolution_suggestions(
                        local_change, remote_change
                    ),
                    created_at=datetime.now(timezone.utc),
                    severity=self._calculate_conflict_severity(conflict_type, confidence_score, local_value, remote_value)
                )
                
                conflicts.append(conflict)
        
        # Check for add/remove conflicts
        local_added = set(local_diff['structural'].get('added_keys', set()))
        remote_removed = set(remote_diff['structural'].get('removed_keys', set()))
        local_removed = set(local_diff['structural'].get('removed_keys', set()))
        remote_added = set(remote_diff['structural'].get('added_keys', set()))
        
        # Key added locally but removed remotely
        add_remove_conflicts = (local_added & remote_removed) | (remote_added & local_removed)
        
        for key in add_remove_conflicts:
            conflict_id = hashlib.sha256(f"add_remove_conflict_{key}_{time.time()}".encode()).hexdigest()[:16]
            
            conflict_type = "add_remove_conflict"
            confidence_score = 0.9  # High confidence for add/remove conflicts
            local_value = "ADDED" if key in local_added else "REMOVED"
            remote_value = "REMOVED" if key in remote_removed else "ADDED"

            conflict = ConflictDescriptor(
                conflict_id=conflict_id,
                conflict_type=conflict_type,
                path=key,
                local_value=local_value,
                remote_value=remote_value,
                base_value=None,
                confidence_score=confidence_score,
                resolution_suggestions=[
                    {"type": "keep_addition", "description": "Keep the added value"},
                    {"type": "accept_removal", "description": "Accept the removal"}
                ],
                created_at=datetime.now(timezone.utc),
                severity=self._calculate_conflict_severity(conflict_type, confidence_score, local_value, remote_value)
            )
            
            conflicts.append(conflict)
        
        return conflicts
    
    def _generate_merge_result(self, base: Dict[str, Any], 
                              local_diff: Dict[str, Any], 
                              remote_diff: Dict[str, Any],
                              conflicts: List[ConflictDescriptor]) -> Dict[str, Any]:
        """Generate suggested merge result."""
        
        merge_result = base.copy()
        conflict_keys = {conflict.path for conflict in conflicts}
        
        # Apply non-conflicting local changes
        local_structural = local_diff['structural']
        for key in local_structural.get('added_keys', set()):
            if key not in conflict_keys:
                merge_result[key] = local_diff['local_changes'][key] if 'local_changes' in local_diff else None
        
        for key in local_structural.get('removed_keys', set()):
            if key not in conflict_keys and key in merge_result:
                del merge_result[key]
        
        for key, change in local_structural.get('modified_values', {}).items():
            if key not in conflict_keys:
                merge_result[key] = self._extract_change_value(change, 'after')
        
        # Apply non-conflicting remote changes
        remote_structural = remote_diff['structural']
        for key in remote_structural.get('added_keys', set()):
            if key not in conflict_keys:
                merge_result[key] = remote_diff['remote_changes'][key] if 'remote_changes' in remote_diff else None
        
        for key in remote_structural.get('removed_keys', set()):
            if key not in conflict_keys and key in merge_result:
                del merge_result[key]
        
        for key, change in remote_structural.get('modified_values', {}).items():
            if key not in conflict_keys:
                merge_result[key] = self._extract_change_value(change, 'after')
        
        # Mark conflicts in the result
        for conflict in conflicts:
            merge_result[f"__CONFLICT_{conflict.path}__"] = {
                'conflict_id': conflict.conflict_id,
                'local_value': conflict.local_value,
                'remote_value': conflict.remote_value,
                'suggestions': conflict.resolution_suggestions
            }
        
        return merge_result
    
    def _analyze_change_patterns(self, structural_diff: Dict[str, Any], 
                                moved_elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in the changes."""
        
        patterns = {
            'bulk_operations': [],
            'refactoring_indicators': [],
            'schema_changes': [],
            'move_patterns': []
        }
        
        # Detect bulk operations
        added_count = len(structural_diff.get('added_keys', set()))
        removed_count = len(structural_diff.get('removed_keys', set()))
        
        if added_count > 10 or removed_count > 10:
            patterns['bulk_operations'].append({
                'type': 'bulk_add' if added_count > removed_count else 'bulk_remove',
                'count': max(added_count, removed_count),
                'ratio': added_count / removed_count if removed_count > 0 else float('inf')
            })
        
        # Detect refactoring patterns
        if len(moved_elements) > 3:
            patterns['refactoring_indicators'].append({
                'type': 'key_restructuring',
                'moved_count': len(moved_elements),
                'confidence': sum(elem['confidence'] for elem in moved_elements) / len(moved_elements)
            })
        
        # Detect schema changes
        type_changes = structural_diff.get('type_changes', {})
        if type_changes:
            patterns['schema_changes'].append({
                'type': 'type_evolution',
                'affected_keys': list(type_changes.keys()),
                'change_count': len(type_changes)
            })
        
        return patterns
    
    def _analyze_conflict_patterns(self, conflicts: List[ConflictDescriptor]) -> Dict[str, Any]:
        """Analyze patterns in conflicts."""
        
        if not conflicts:
            return {'conflict_types': {}, 'severity_distribution': {}, 'resolution_complexity': 'low'}
        
        conflict_types = {}
        for conflict in conflicts:
            conflict_type = conflict.conflict_type
            conflict_types[conflict_type] = conflict_types.get(conflict_type, 0) + 1
        
        avg_confidence = sum(c.confidence_score for c in conflicts) / len(conflicts)
        
        complexity = 'low'
        if len(conflicts) > 5 or avg_confidence < 0.7:
            complexity = 'high'
        elif len(conflicts) > 2 or avg_confidence < 0.85:
            complexity = 'medium'
        
        return {
            'conflict_types': conflict_types,
            'total_conflicts': len(conflicts),
            'average_confidence': avg_confidence,
            'resolution_complexity': complexity
        }
    
    def _generate_resolution_suggestions(self, conflicts: List[ConflictDescriptor], 
                                       conflict_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate intelligent resolution suggestions."""
        
        suggestions = []
        
        complexity = conflict_analysis.get('resolution_complexity', 'low')
        
        if complexity == 'low':
            suggestions.append({
                'strategy': 'auto_resolve',
                'description': 'Conflicts can likely be resolved automatically',
                'confidence': 0.9,
                'actions': ['Apply semantic merge where possible', 'Use last-writer-wins for simple conflicts']
            })
        elif complexity == 'medium':
            suggestions.append({
                'strategy': 'guided_resolution',
                'description': 'Conflicts require some manual intervention',
                'confidence': 0.7,
                'actions': ['Review each conflict individually', 'Use diff tools for comparison', 'Apply consistent resolution patterns']
            })
        else:
            suggestions.append({
                'strategy': 'expert_review',
                'description': 'Complex conflicts require expert review',
                'confidence': 0.5,
                'actions': ['Schedule team review session', 'Break down into smaller merges', 'Consider alternative merge strategies']
            })
        
        return suggestions
    
    # Helper methods

    def _calculate_conflict_severity(self, conflict_type: str, confidence_score: float,
                                   local_value: Any, remote_value: Any) -> str:
        """Calculate severity level for a conflict."""

        # Critical patterns - conflicts in critical fields
        critical_patterns = ['id', 'key', 'type', 'status', 'delete', 'remove']

        # Check if it's an add/remove conflict (always high severity)
        if conflict_type == "add_remove_conflict":
            return "high"

        # Check if it's a type conflict (usually high severity)
        if conflict_type == "type_conflict":
            return "high"

        # Check for critical field patterns
        if any(pattern in str(local_value).lower() + str(remote_value).lower() for pattern in critical_patterns):
            return "critical"

        # Base severity on confidence score
        if confidence_score >= 0.9:
            return "high"
        elif confidence_score >= 0.7:
            return "medium"
        elif confidence_score >= 0.5:
            return "low"
        else:
            return "low"

    def _classify_value_change(self, before_val: Any, after_val: Any) -> str:
        """Classify the type of value change."""
        
        if isinstance(before_val, str) and isinstance(after_val, str):
            return 'text_modification'
        elif isinstance(before_val, (int, float)) and isinstance(after_val, (int, float)):
            return 'numeric_modification'
        elif isinstance(before_val, (list, dict)) and isinstance(after_val, (list, dict)):
            return 'structural_modification'
        else:
            return 'value_replacement'
    
    def _classify_move_type(self, from_key: str, to_key: str) -> str:
        """Classify the type of move operation."""
        
        if from_key.replace('_', '').lower() == to_key.replace('_', '').lower():
            return 'key_format_change'
        elif from_key in to_key or to_key in from_key:
            return 'key_extension'
        else:
            return 'key_rename'
    
    def _classify_semantic_change(self, similarity_score: float) -> str:
        """Classify semantic change based on similarity score."""
        
        if similarity_score > 0.9:
            return 'minor_modification'
        elif similarity_score > 0.7:
            return 'moderate_modification'
        elif similarity_score > 0.5:
            return 'major_modification'
        else:
            return 'complete_replacement'
    
    def _assess_change_impact(self, key: str, change: Dict[str, Any], similarity_score: float) -> str:
        """Assess the impact level of a change."""
        
        # Simple impact assessment based on key patterns and similarity
        critical_patterns = ['id', 'key', 'name', 'type', 'status']
        
        if any(pattern in key.lower() for pattern in critical_patterns):
            return 'high'
        elif similarity_score < 0.5:
            return 'high'
        elif similarity_score < 0.8:
            return 'medium'
        else:
            return 'low'
    
    def _values_semantically_equal(self, val1: Any, val2: Any, threshold: float = 0.9) -> bool:
        """Check if two values are semantically equal."""
        
        if val1 == val2:
            return True
        
        similarity = self._calculate_semantic_similarity(val1, val2)
        return similarity >= threshold
    
    def _calculate_semantic_similarity(self, val1: Any, val2: Any) -> float:
        """Calculate semantic similarity between two values."""
        
        if val1 == val2:
            return 1.0
        
        if type(val1) != type(val2):
            return 0.0
        
        if isinstance(val1, str) and isinstance(val2, str):
            # Use sequence matcher for string similarity
            return SequenceMatcher(None, val1, val2).ratio()
        elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            # Numeric similarity based on relative difference
            if val1 == 0 and val2 == 0:
                return 1.0
            elif val1 == 0 or val2 == 0:
                return 0.0
            else:
                diff_ratio = abs(val1 - val2) / max(abs(val1), abs(val2))
                return max(0.0, 1.0 - diff_ratio)
        elif isinstance(val1, dict) and isinstance(val2, dict):
            # Dictionary similarity based on key overlap and value similarity
            keys1, keys2 = set(val1.keys()), set(val2.keys())
            common_keys = keys1 & keys2
            
            if not common_keys:
                return 0.0
            
            key_similarity = len(common_keys) / len(keys1 | keys2)
            value_similarities = [
                self._calculate_semantic_similarity(val1[k], val2[k])
                for k in common_keys
            ]
            
            avg_value_similarity = sum(value_similarities) / len(value_similarities)
            return (key_similarity + avg_value_similarity) / 2
        else:
            # For other types, just check equality
            return 1.0 if val1 == val2 else 0.0
    
    def _changes_are_equivalent(self, change1: Dict[str, Any], change2: Dict[str, Any]) -> bool:
        """Check if two changes are equivalent."""
        
        # Simple equivalence check - could be more sophisticated
        after1 = self._extract_change_value(change1, 'after')
        after2 = self._extract_change_value(change2, 'after')
        
        return self._values_semantically_equal(after1, after2)
    
    def _extract_change_value(self, change: Dict[str, Any], key: str) -> Any:
        """Extract value from a change object."""
        
        if isinstance(change, dict):
            return change.get(key)
        else:
            return change
    
    def _classify_conflict_type(self, local_change: Dict[str, Any], remote_change: Dict[str, Any]) -> str:
        """Classify the type of conflict."""
        
        # Basic conflict type classification
        local_val = self._extract_change_value(local_change, 'after')
        remote_val = self._extract_change_value(remote_change, 'after')
        
        if type(local_val) != type(remote_val):
            return 'type_conflict'
        elif isinstance(local_val, str) and isinstance(remote_val, str):
            return 'text_conflict'
        elif isinstance(local_val, (int, float)) and isinstance(remote_val, (int, float)):
            return 'numeric_conflict'
        elif isinstance(local_val, (dict, list)) and isinstance(remote_val, (dict, list)):
            return 'structural_conflict'
        else:
            return 'value_conflict'
    
    def _calculate_conflict_confidence(self, local_change: Dict[str, Any], remote_change: Dict[str, Any]) -> float:
        """Calculate confidence score for conflict detection."""
        
        # Higher confidence means more certain it's actually a conflict
        local_val = self._extract_change_value(local_change, 'after')
        remote_val = self._extract_change_value(remote_change, 'after')
        
        similarity = self._calculate_semantic_similarity(local_val, remote_val)
        
        # Less similar values = higher confidence it's a real conflict
        return 1.0 - similarity
    
    def _generate_conflict_resolution_suggestions(self, local_change: Dict[str, Any], 
                                                remote_change: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate suggestions for resolving a specific conflict."""
        
        suggestions = [
            {"type": "use_local", "description": "Keep the local version"},
            {"type": "use_remote", "description": "Keep the remote version"},
            {"type": "manual_merge", "description": "Manually combine both versions"}
        ]
        
        # Add intelligent suggestions based on change type
        local_val = self._extract_change_value(local_change, 'after')
        remote_val = self._extract_change_value(remote_change, 'after')
        
        if isinstance(local_val, str) and isinstance(remote_val, str):
            suggestions.append({
                "type": "text_merge", 
                "description": "Use text merging algorithms to combine content"
            })
        elif isinstance(local_val, (list, dict)) and isinstance(remote_val, (list, dict)):
            suggestions.append({
                "type": "structural_merge", 
                "description": "Merge structures intelligently"
            })
        
        return suggestions
    
    def _calculate_diff_metadata(self, diff_result: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate metadata for the diff result."""
        
        structural = diff_result.get('structural', {})
        
        total_changes = (
            len(structural.get('added_keys', set())) +
            len(structural.get('removed_keys', set())) +
            len(structural.get('modified_values', {})) +
            len(diff_result.get('moved', []))
        )
        
        # Calculate change depth (how nested the changes are)
        change_depth = self._calculate_change_depth(structural.get('modified_values', {}))
        
        # Calculate change complexity score
        change_complexity = self._calculate_change_complexity(diff_result)
        
        return {
            'total_changes': total_changes,
            'change_depth': change_depth,
            'change_complexity': change_complexity,
            'has_moves': len(diff_result.get('moved', [])) > 0,
            'has_type_changes': len(structural.get('type_changes', {})) > 0
        }
    
    def _calculate_change_depth(self, modified_values: Dict[str, Any], current_depth: int = 0) -> int:
        """Calculate the maximum depth of changes."""
        
        max_depth = current_depth
        
        for change in modified_values.values():
            if isinstance(change, dict) and 'modified_values' in change:
                nested_depth = self._calculate_change_depth(
                    change['modified_values'], 
                    current_depth + 1
                )
                max_depth = max(max_depth, nested_depth)
        
        return max_depth
    
    def _calculate_change_complexity(self, diff_result: Dict[str, Any]) -> float:
        """Calculate a complexity score for the changes."""
        
        structural = diff_result.get('structural', {})
        
        # Base complexity from number of changes
        base_complexity = len(structural.get('modified_values', {})) * 0.3
        
        # Add complexity for moves
        move_complexity = len(diff_result.get('moved', [])) * 0.5
        
        # Add complexity for type changes
        type_complexity = len(structural.get('type_changes', {})) * 0.7
        
        # Add complexity for patterns
        pattern_complexity = len(diff_result.get('patterns', {}).get('bulk_operations', [])) * 0.4
        
        total_complexity = base_complexity + move_complexity + type_complexity + pattern_complexity
        
        # Normalize to 0-1 scale (approximately)
        return min(1.0, total_complexity / 10.0)
    
    def get_performance_statistics(self) -> Dict[str, Any]:
        """Get performance statistics for the diff engine."""
        
        if not self.performance_metrics:
            return {
                'total_diffs_computed': 0,
                'average_computation_time_ms': 0,
                'cache_hit_rate': 0
            }
        
        total_diffs = len(self.performance_metrics)
        avg_time = sum(self.performance_metrics) / total_diffs
        cache_hits = len(self.diff_cache)
        
        return {
            'total_diffs_computed': total_diffs,
            'average_computation_time_ms': avg_time,
            'cache_entries': cache_hits,
            'cache_hit_rate': cache_hits / max(1, total_diffs)
        }