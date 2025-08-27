"""Performance tests for predicate operations."""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import time
import json
import uuid
from statistics import mean, median
from unittest.mock import Mock, patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database.models import Base, Predicate, Domain, Layer, Term, TermRelationship
from database.predicate_utils import validate_term_relationship_predicate, validate_predicate_set


class TestPredicatePerformance:
    """Performance tests for predicate operations."""

    @pytest.fixture
    def db_session(self):
        """Create in-memory database session for testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()

    def create_test_predicates(self, db_session, count=1000):
        """Create a large number of test predicates."""
        predicates = []
        for i in range(count):
            predicate = Predicate(
                identifier=f"predicate_{i:04d}",
                title=f"Predicate {i:04d}",
                definition=f"Test predicate number {i}",
                mapping=json.dumps({
                    "test": {"index": i, "type": "performance_test"}
                })
            )
            predicates.append(predicate)
            
            # Batch insert for better performance
            if len(predicates) == 100:
                db_session.add_all(predicates)
                db_session.commit()
                predicates = []
        
        # Insert remaining predicates
        if predicates:
            db_session.add_all(predicates)
            db_session.commit()

    def measure_time(self, func, *args, **kwargs):
        """Measure execution time of a function."""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        return result, end_time - start_time

    def test_predicate_lookup_by_identifier_performance(self, db_session):
        """Test performance of predicate lookups by identifier."""
        # Create test data
        self.create_test_predicates(db_session, count=1000)
        
        # Test single lookups
        lookup_times = []
        test_identifiers = [f"predicate_{i:04d}" for i in range(0, 1000, 100)]
        
        for identifier in test_identifiers:
            _, exec_time = self.measure_time(
                lambda: db_session.query(Predicate).filter_by(identifier=identifier).first()
            )
            lookup_times.append(exec_time)
        
        # Performance assertions
        avg_lookup_time = mean(lookup_times)
        max_lookup_time = max(lookup_times)
        
        assert avg_lookup_time < 0.01, f"Average lookup time {avg_lookup_time:.4f}s exceeds 10ms"
        assert max_lookup_time < 0.05, f"Max lookup time {max_lookup_time:.4f}s exceeds 50ms"
        
        print(f"Predicate lookup performance:")
        print(f"  Average time: {avg_lookup_time:.4f}s")
        print(f"  Median time: {median(lookup_times):.4f}s")
        print(f"  Max time: {max_lookup_time:.4f}s")

    def test_predicate_lookup_by_id_performance(self, db_session):
        """Test performance of predicate lookups by ID."""
        # Create test data
        self.create_test_predicates(db_session, count=1000)
        
        # Get all predicate IDs
        predicates = db_session.query(Predicate).all()
        test_ids = [pred.id for pred in predicates[::100]]  # Every 100th predicate
        
        # Test lookups by ID
        lookup_times = []
        for pred_id in test_ids:
            _, exec_time = self.measure_time(
                lambda: db_session.query(Predicate).filter_by(id=pred_id).first()
            )
            lookup_times.append(exec_time)
        
        # Performance assertions
        avg_lookup_time = mean(lookup_times)
        max_lookup_time = max(lookup_times)
        
        assert avg_lookup_time < 0.01, f"Average ID lookup time {avg_lookup_time:.4f}s exceeds 10ms"
        assert max_lookup_time < 0.05, f"Max ID lookup time {max_lookup_time:.4f}s exceeds 50ms"

    def test_predicate_bulk_creation_performance(self, db_session):
        """Test performance of bulk predicate creation."""
        batch_sizes = [10, 50, 100, 500]
        creation_times = {}
        
        for batch_size in batch_sizes:
            # Create predicates in batches
            predicates = []
            for i in range(batch_size):
                predicate = Predicate(
                    identifier=f"bulk_{batch_size}_{i:04d}",
                    title=f"Bulk {batch_size} Predicate {i:04d}",
                    definition=f"Bulk creation test predicate {i}"
                )
                predicates.append(predicate)
            
            # Measure bulk insert time
            _, exec_time = self.measure_time(
                lambda preds: (db_session.add_all(preds), db_session.commit()),
                predicates
            )
            
            creation_times[batch_size] = exec_time
            time_per_predicate = exec_time / batch_size
            
            # Performance assertions
            assert time_per_predicate < 0.01, f"Time per predicate {time_per_predicate:.4f}s exceeds 10ms for batch size {batch_size}"
            
            print(f"Bulk creation (batch size {batch_size}):")
            print(f"  Total time: {exec_time:.4f}s")
            print(f"  Time per predicate: {time_per_predicate:.6f}s")

    def test_predicate_search_performance(self, db_session):
        """Test performance of predicate search operations."""
        # Create test data with varied titles
        search_terms = ["synonym", "antonym", "related", "part", "cause", "effect", "similar", "opposite"]
        predicates = []
        
        for i in range(1000):
            base_term = search_terms[i % len(search_terms)]
            predicate = Predicate(
                identifier=f"{base_term}_{i:04d}",
                title=f"{base_term.title()} Relation {i:04d}",
                definition=f"A {base_term} relationship for testing"
            )
            predicates.append(predicate)
            
            if len(predicates) == 100:
                db_session.add_all(predicates)
                db_session.commit()
                predicates = []
        
        if predicates:
            db_session.add_all(predicates)
            db_session.commit()
        
        # Test different search patterns
        search_patterns = [
            ("title LIKE '%synonym%'", "Partial title match"),
            ("title LIKE 'Related%'", "Title prefix match"),
            ("definition LIKE '%relationship%'", "Definition search"),
            ("identifier LIKE 'synonym_%'", "Identifier prefix match")
        ]
        
        for pattern, description in search_patterns:
            _, exec_time = self.measure_time(
                lambda p: db_session.query(Predicate).filter(text(p)).all(),
                pattern
            )
            
            # Performance assertion
            assert exec_time < 0.1, f"{description} search time {exec_time:.4f}s exceeds 100ms"
            
            print(f"{description} search: {exec_time:.4f}s")

    def test_predicate_set_validation_performance(self, db_session):
        """Test performance of predicate set validation."""
        # Create test predicates
        self.create_test_predicates(db_session, count=500)
        
        # Test validation with different set sizes
        set_sizes = [5, 10, 25, 50, 100]
        validation_times = {}
        
        for set_size in set_sizes:
            # Create predicate set
            predicate_set = [f"predicate_{i:04d}" for i in range(set_size)]
            
            # Measure validation time
            _, exec_time = self.measure_time(
                validate_predicate_set,
                predicate_set,
                db_session
            )
            
            validation_times[set_size] = exec_time
            
            # Performance assertion
            assert exec_time < 0.1, f"Validation time {exec_time:.4f}s exceeds 100ms for set size {set_size}"
            
            print(f"Predicate set validation (size {set_size}): {exec_time:.4f}s")

    def test_domain_predicate_validation_performance(self, db_session):
        """Test performance of domain predicate validation for term relationships."""
        # Create test data
        self.create_test_predicates(db_session, count=100)
        
        # Create layer
        layer = Layer(
            id=str(uuid.uuid4()),
            title="Performance Test Layer",
            definition="Layer for performance testing"
        )
        db_session.add(layer)
        db_session.commit()
        
        # Create domain with predicate set
        predicate_set = [f"predicate_{i:04d}" for i in range(20)]
        domain = Domain(
            id=str(uuid.uuid4()),
            layer_id=layer.id,
            title="Performance Test Domain",
            definition="Domain for performance testing",
            predicate_set=json.dumps(predicate_set)
        )
        db_session.add(domain)
        db_session.commit()
        
        # Create terms
        terms = []
        for i in range(2):
            term = Term(
                id=str(uuid.uuid4()),
                domain_id=domain.id,
                layer_id=layer.id,
                title=f"Test Term {i}",
                definition=f"Term {i} for performance testing"
            )
            terms.append(term)
        
        db_session.add_all(terms)
        db_session.commit()
        
        # Test validation performance for different predicates
        test_predicates = ["predicate_0005", "predicate_0010", "predicate_0015", "nonexistent_predicate"]
        validation_times = []
        
        for predicate in test_predicates:
            # Create test relationship
            relationship = TermRelationship(
                id=str(uuid.uuid4()),
                source_term_id=terms[0].id,
                target_term_id=terms[1].id,
                predicate=predicate
            )
            
            # Measure validation time
            _, exec_time = self.measure_time(
                validate_term_relationship_predicate,
                relationship,
                db_session
            )
            
            validation_times.append(exec_time)
        
        # Performance assertions
        avg_validation_time = mean(validation_times)
        max_validation_time = max(validation_times)
        
        assert avg_validation_time < 0.05, f"Average validation time {avg_validation_time:.4f}s exceeds 50ms"
        assert max_validation_time < 0.1, f"Max validation time {max_validation_time:.4f}s exceeds 100ms"
        
        print(f"Term relationship validation performance:")
        print(f"  Average time: {avg_validation_time:.4f}s")
        print(f"  Max time: {max_validation_time:.4f}s")

    @patch('config.get_settings')
    def test_conceptnet_import_performance(self, mock_get_settings, db_session):
        """Test performance of ConceptNet predicate import."""
        # Mock config with large number of relations
        mock_settings = Mock()
        mock_settings.concepcy_config = {
            "relations_of_interest": [
                "RelatedTo", "FormOf", "IsA", "PartOf", "HasA", "UsedFor",
                "CapableOf", "AtLocation", "Causes", "HasSubevent", "HasFirstSubevent",
                "HasLastSubevent", "HasPrerequisite", "HasProperty", "MotivatedByGoal",
                "ObstructedBy", "Desires", "CreatedBy", "Synonym", "Antonym",
                "DerivedFrom", "TranslationOf", "DefinedAs", "MannerOf", "LocatedNear",
                "HasContext", "SimilarTo", "EtymologicallyRelatedTo", "EtymologicallyDerivedFrom",
                "CausesDesire", "MadeOf", "ReceivesAction", "ExternalURL"
            ]
        }
        mock_get_settings.return_value = mock_settings
        
        def import_conceptnet_predicates(db):
            """Import ConceptNet relations as predicates."""
            from config import get_settings
            
            settings = get_settings()
            relations = settings.concepcy_config["relations_of_interest"]
            
            predicates = []
            for relation in relations:
                identifier = relation.lower()
                
                # Check if already exists
                existing = db.query(Predicate).filter_by(identifier=identifier).first()
                if existing:
                    continue
                
                mapping = {
                    "conceptnet": {
                        "relation": relation,
                        "url": f"https://conceptnet.io/r/{relation}",
                        "description": f"ConceptNet relation type: {relation}"
                    }
                }
                
                predicate = Predicate(
                    identifier=identifier,
                    title=relation,
                    definition=f"ConceptNet relation: {relation}",
                    mapping=json.dumps(mapping)
                )
                
                predicates.append(predicate)
            
            # Bulk insert
            db.add_all(predicates)
            db.commit()
            return predicates
        
        # Measure import time
        imported_predicates, exec_time = self.measure_time(
            import_conceptnet_predicates,
            db_session
        )
        
        # Performance assertions
        relations_count = len(mock_settings.concepcy_config["relations_of_interest"])
        time_per_relation = exec_time / relations_count if relations_count > 0 else 0
        
        assert exec_time < 5.0, f"Import time {exec_time:.4f}s exceeds 5 seconds"
        assert time_per_relation < 0.2, f"Time per relation {time_per_relation:.4f}s exceeds 200ms"
        
        print(f"ConceptNet import performance:")
        print(f"  Total time: {exec_time:.4f}s")
        print(f"  Relations imported: {len(imported_predicates)}")
        print(f"  Time per relation: {time_per_relation:.4f}s")

    def test_predicate_deletion_cascade_performance(self, db_session):
        """Test performance of predicate deletion with cascading references."""
        # Create predicate
        predicate = Predicate(
            identifier="cascade_test",
            title="Cascade Test Predicate",
            definition="Predicate for testing cascade deletion"
        )
        db_session.add(predicate)
        db_session.commit()
        
        # Create layer
        layer = Layer(
            id=str(uuid.uuid4()),
            title="Cascade Test Layer",
            definition="Layer for cascade testing"
        )
        db_session.add(layer)
        db_session.commit()
        
        # Create multiple domains referencing the predicate
        domains = []
        for i in range(50):
            domain = Domain(
                id=str(uuid.uuid4()),
                layer_id=layer.id,
                title=f"Cascade Domain {i}",
                definition=f"Domain {i} for cascade testing",
                primary_predicate_id=predicate.id
            )
            domains.append(domain)
        
        db_session.add_all(domains)
        db_session.commit()
        
        # Create multiple term relationships referencing the predicate
        relationships = []
        for i in range(100):
            relationship = TermRelationship(
                id=str(uuid.uuid4()),
                source_term_id=str(uuid.uuid4()),
                target_term_id=str(uuid.uuid4()),
                predicate="cascade_test",
                predicate_id=predicate.id
            )
            relationships.append(relationship)
        
        db_session.add_all(relationships)
        db_session.commit()
        
        # Measure deletion time (behavior depends on foreign key constraints)
        _, exec_time = self.measure_time(
            lambda: (db_session.delete(predicate), db_session.commit())
        )
        
        # Performance assertion
        assert exec_time < 1.0, f"Cascade deletion time {exec_time:.4f}s exceeds 1 second"
        
        print(f"Predicate cascade deletion performance:")
        print(f"  Deletion time: {exec_time:.4f}s")
        print(f"  Referenced by {len(domains)} domains and {len(relationships)} relationships")

    def test_large_predicate_set_operations(self, db_session):
        """Test operations with large predicate sets."""
        # Create large number of predicates
        self.create_test_predicates(db_session, count=2000)
        
        # Test large predicate set validation
        large_set = [f"predicate_{i:04d}" for i in range(0, 2000, 10)]  # Every 10th predicate
        
        _, validation_time = self.measure_time(
            validate_predicate_set,
            large_set,
            db_session
        )
        
        # Test pagination of large result sets
        _, pagination_time = self.measure_time(
            lambda: db_session.query(Predicate).offset(1000).limit(100).all()
        )
        
        # Test sorting large result sets
        _, sort_time = self.measure_time(
            lambda: db_session.query(Predicate).order_by(Predicate.title).limit(500).all()
        )
        
        # Performance assertions
        assert validation_time < 0.5, f"Large set validation time {validation_time:.4f}s exceeds 500ms"
        assert pagination_time < 0.1, f"Pagination time {pagination_time:.4f}s exceeds 100ms"
        assert sort_time < 0.2, f"Sorting time {sort_time:.4f}s exceeds 200ms"
        
        print(f"Large predicate set operations:")
        print(f"  Set validation (200 predicates): {validation_time:.4f}s")
        print(f"  Pagination (offset 1000, limit 100): {pagination_time:.4f}s")
        print(f"  Sorting (500 predicates): {sort_time:.4f}s")

    def test_concurrent_predicate_access_simulation(self, db_session):
        """Simulate concurrent access patterns for performance testing."""
        # Create test data
        self.create_test_predicates(db_session, count=500)
        
        # Simulate mixed operations (read-heavy workload)
        operations = [
            lambda: db_session.query(Predicate).filter_by(identifier=f"predicate_{i:04d}").first()
            for i in range(0, 500, 50)
        ] + [
            lambda: db_session.query(Predicate).filter(Predicate.title.like('%Predicate%')).limit(10).all()
            for _ in range(5)
        ] + [
            lambda: validate_predicate_set([f"predicate_{i:04d}" for i in range(0, 20)], db_session)
            for _ in range(3)
        ]
        
        # Measure total time for mixed operations
        start_time = time.time()
        for operation in operations:
            operation()
        end_time = time.time()
        
        total_time = end_time - start_time
        avg_operation_time = total_time / len(operations)
        
        # Performance assertions
        assert total_time < 2.0, f"Total mixed operations time {total_time:.4f}s exceeds 2 seconds"
        assert avg_operation_time < 0.1, f"Average operation time {avg_operation_time:.4f}s exceeds 100ms"
        
        print(f"Concurrent access simulation:")
        print(f"  Total time ({len(operations)} operations): {total_time:.4f}s")
        print(f"  Average operation time: {avg_operation_time:.4f}s")


class TestPredicateMemoryUsage:
    """Test memory usage patterns for predicate operations."""

    @pytest.fixture
    def db_session(self):
        """Create in-memory database session for testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()

    def test_memory_usage_large_dataset(self, db_session):
        """Test memory usage with large predicate datasets."""
        # This test is for monitoring memory usage patterns
        # In a real scenario, you would use memory profiling tools
        
        # Create large dataset
        predicates = []
        for i in range(5000):
            predicate = Predicate(
                identifier=f"memory_test_{i:05d}",
                title=f"Memory Test Predicate {i:05d}",
                definition=f"Predicate {i} for memory usage testing",
                mapping=json.dumps({
                    "test": {"index": i, "data": "x" * 100}  # Some bulk data
                })
            )
            predicates.append(predicate)
            
            # Batch insert to avoid memory issues
            if len(predicates) == 500:
                db_session.add_all(predicates)
                db_session.commit()
                predicates = []
        
        if predicates:
            db_session.add_all(predicates)
            db_session.commit()
        
        # Test memory usage during large queries
        # Query all predicates (should be handled efficiently)
        all_predicates = db_session.query(Predicate).all()
        assert len(all_predicates) == 5000
        
        # Test streaming/pagination for memory efficiency
        predicate_count = 0
        offset = 0
        batch_size = 100
        
        while True:
            batch = db_session.query(Predicate).offset(offset).limit(batch_size).all()
            if not batch:
                break
            predicate_count += len(batch)
            offset += batch_size
        
        assert predicate_count == 5000
        print(f"Successfully processed {predicate_count} predicates in batches")

    def test_memory_efficient_validation(self, db_session):
        """Test memory-efficient predicate set validation."""
        # Create test predicates
        for i in range(1000):
            predicate = Predicate(
                identifier=f"efficient_{i:04d}",
                title=f"Efficient Predicate {i:04d}"
            )
            db_session.add(predicate)
            
            # Commit in batches
            if i % 100 == 99:
                db_session.commit()
        
        db_session.commit()
        
        # Test validation with large sets
        large_predicate_set = [f"efficient_{i:04d}" for i in range(500)]
        
        # This should use efficient querying (IN clause) rather than loading all predicates
        result = validate_predicate_set(large_predicate_set, db_session)
        assert result is True
        
        # Test with some invalid predicates
        mixed_set = large_predicate_set + ["nonexistent_1", "nonexistent_2"]
        result = validate_predicate_set(mixed_set, db_session)
        assert result is False
        
        print("Memory-efficient validation completed successfully")
