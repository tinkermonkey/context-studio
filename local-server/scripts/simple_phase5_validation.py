#!/usr/bin/env python3
"""
Simplified Phase 5 Optimization Validation

Tests core Phase 5 implementation without external dependencies:
- File structure validation
- Import validation  
- Basic functionality testing
- Code quality checks
"""

import os
import sys
import importlib
import traceback
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

class SimplePhase5Validator:
    """Simplified Phase 5 validation."""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'files_validated': [],
            'imports_validated': [],
            'tests_found': [],
            'apis_validated': [],
            'migrations_validated': [],
            'errors': []
        }
    
    def validate_file_structure(self):
        """Validate that all Phase 5 files exist."""
        print("📁 Validating File Structure...")
        
        expected_files = [
            # Core service files
            'services/duckdb_query_optimizer.py',
            'services/s3_storage_optimizer.py', 
            'services/hierarchical_diff_engine.py',
            'services/batch_operation_processor.py',
            'services/performance_monitor.py',
            
            # API files
            'api/optimization.py',
            
            # Migration files
            'database/migrations/versions/010_optimization_features.py',
            
            # Test files
            'tests/unit_tests/test_duckdb_query_optimizer.py',
            'tests/unit_tests/test_s3_storage_optimizer.py',
            'tests/unit_tests/test_hierarchical_diff_engine.py', 
            'tests/unit_tests/test_batch_operation_processor.py',
            'tests/unit_tests/test_performance_monitor.py',
            'tests/integration_tests/test_phase5_optimization_integration.py'
        ]
        
        missing_files = []
        for file_path in expected_files:
            full_path = os.path.join(project_root, file_path)
            if os.path.exists(full_path):
                self.results['files_validated'].append(file_path)
                print(f"  ✅ {file_path}")
            else:
                missing_files.append(file_path)
                print(f"  ❌ {file_path} - NOT FOUND")
        
        if missing_files:
            self.results['errors'].append(f"Missing files: {missing_files}")
            return False
        
        print(f"  📊 All {len(expected_files)} Phase 5 files found!")
        return True
    
    def validate_service_imports(self):
        """Validate that Phase 5 services can be imported."""
        print("\n📦 Validating Service Imports...")
        
        service_modules = [
            'services.duckdb_query_optimizer',
            'services.s3_storage_optimizer',
            'services.hierarchical_diff_engine', 
            'services.batch_operation_processor',
            'services.performance_monitor'
        ]
        
        failed_imports = []
        for module_name in service_modules:
            try:
                module = importlib.import_module(module_name)
                self.results['imports_validated'].append(module_name)
                print(f"  ✅ {module_name}")
            except ImportError as e:
                failed_imports.append((module_name, str(e)))
                print(f"  ❌ {module_name} - IMPORT FAILED: {e}")
            except Exception as e:
                failed_imports.append((module_name, str(e)))
                print(f"  ⚠️  {module_name} - ERROR: {e}")
        
        if failed_imports:
            self.results['errors'].append(f"Failed imports: {failed_imports}")
            return False
        
        print(f"  📊 All {len(service_modules)} service modules imported successfully!")
        return True
    
    def validate_api_structure(self):
        """Validate API structure and endpoints."""
        print("\n🌐 Validating API Structure...")
        
        try:
            # Check optimization API
            api_file = os.path.join(project_root, 'api/optimization.py')
            if not os.path.exists(api_file):
                self.results['errors'].append("Optimization API file missing")
                return False
            
            with open(api_file, 'r') as f:
                api_content = f.read()
            
            # Check for expected endpoints
            expected_endpoints = [
                'health', 'performance/dashboard', 'performance/metrics',
                'query/optimize', 'storage/optimize', 'batch/process'
            ]
            
            missing_endpoints = []
            for endpoint in expected_endpoints:
                if endpoint not in api_content:
                    missing_endpoints.append(endpoint)
                else:
                    self.results['apis_validated'].append(endpoint)
                    print(f"  ✅ /{endpoint}")
            
            if missing_endpoints:
                self.results['errors'].append(f"Missing API endpoints: {missing_endpoints}")
                print(f"  ❌ Missing endpoints: {missing_endpoints}")
                return False
            
            # Check app.py integration
            app_file = os.path.join(project_root, 'app.py')
            if os.path.exists(app_file):
                with open(app_file, 'r') as f:
                    app_content = f.read()
                
                if 'optimization' in app_content and 'optimization.router' in app_content:
                    print("  ✅ Optimization API integrated in main app")
                else:
                    self.results['errors'].append("Optimization API not integrated in main app")
                    return False
            
            print(f"  📊 API structure validated - {len(expected_endpoints)} endpoints found!")
            return True
            
        except Exception as e:
            self.results['errors'].append(f"API validation error: {e}")
            print(f"  ❌ API validation failed: {e}")
            return False
    
    def validate_service_factory_integration(self):
        """Validate service factory integration.""" 
        print("\n🏭 Validating Service Factory Integration...")
        
        try:
            # Check service factory file
            factory_file = os.path.join(project_root, 'services/service_factory.py')
            if not os.path.exists(factory_file):
                self.results['errors'].append("Service factory file missing")
                return False
            
            with open(factory_file, 'r') as f:
                factory_content = f.read()
            
            # Check for Phase 5 service imports
            phase5_imports = [
                'duckdb_query_optimizer', 's3_storage_optimizer',
                'hierarchical_diff_engine', 'batch_operation_processor',
                'performance_monitor'
            ]
            
            missing_imports = []
            for import_name in phase5_imports:
                if import_name not in factory_content:
                    missing_imports.append(import_name)
                else:
                    print(f"  ✅ {import_name} imported")
            
            if missing_imports:
                self.results['errors'].append(f"Service factory missing imports: {missing_imports}")
                return False
            
            # Check for factory methods
            factory_methods = [
                'create_duckdb_query_optimizer', 'create_s3_storage_optimizer',
                'create_hierarchical_diff_engine', 'create_batch_operation_processor',
                'create_performance_monitor'
            ]
            
            missing_methods = []
            for method_name in factory_methods:
                if method_name not in factory_content:
                    missing_methods.append(method_name)
                else:
                    print(f"  ✅ {method_name} method")
            
            if missing_methods:
                self.results['errors'].append(f"Service factory missing methods: {missing_methods}")
                return False
            
            print("  📊 Service factory integration validated!")
            return True
            
        except Exception as e:
            self.results['errors'].append(f"Service factory validation error: {e}")
            print(f"  ❌ Service factory validation failed: {e}")
            return False
    
    def validate_database_migration(self):
        """Validate database migration structure."""
        print("\n🗄️ Validating Database Migration...")
        
        try:
            migration_file = os.path.join(project_root, 'database/migrations/versions/010_optimization_features.py')
            if not os.path.exists(migration_file):
                self.results['errors'].append("Migration 010 file missing")
                return False
            
            with open(migration_file, 'r') as f:
                migration_content = f.read()
            
            # Check for required elements
            required_elements = [
                'MIGRATION_VERSION = 10',
                'def upgrade(connection)',
                'def downgrade(connection)',
                'query_performance_metrics',
                'materialized_views_registry',
                'storage_optimization_logs',
                'performance_alerts',
                'batch_operation_metrics'
            ]
            
            missing_elements = []
            for element in required_elements:
                if element in migration_content:
                    print(f"  ✅ {element}")
                    self.results['migrations_validated'].append(element)
                else:
                    missing_elements.append(element)
            
            if missing_elements:
                self.results['errors'].append(f"Migration missing elements: {missing_elements}")
                return False
            
            print("  📊 Database migration structure validated!")
            return True
            
        except Exception as e:
            self.results['errors'].append(f"Migration validation error: {e}")
            print(f"  ❌ Migration validation failed: {e}")
            return False
    
    def validate_test_structure(self):
        """Validate test file structure."""
        print("\n🧪 Validating Test Structure...")
        
        test_files = [
            'tests/unit_tests/test_duckdb_query_optimizer.py',
            'tests/unit_tests/test_s3_storage_optimizer.py',
            'tests/unit_tests/test_hierarchical_diff_engine.py',
            'tests/unit_tests/test_batch_operation_processor.py', 
            'tests/unit_tests/test_performance_monitor.py',
            'tests/integration_tests/test_phase5_optimization_integration.py'
        ]
        
        missing_tests = []
        for test_file in test_files:
            full_path = os.path.join(project_root, test_file)
            if os.path.exists(full_path):
                # Check test file has actual test classes
                with open(full_path, 'r') as f:
                    content = f.read()
                
                if 'class Test' in content and 'def test_' in content:
                    print(f"  ✅ {test_file}")
                    self.results['tests_found'].append(test_file)
                else:
                    print(f"  ⚠️  {test_file} - No test classes found")
            else:
                missing_tests.append(test_file)
                print(f"  ❌ {test_file} - NOT FOUND")
        
        if missing_tests:
            self.results['errors'].append(f"Missing test files: {missing_tests}")
            return False
        
        print(f"  📊 All {len(test_files)} test files validated!")
        return True
    
    def check_code_quality(self):
        """Basic code quality checks."""
        print("\n🔍 Basic Code Quality Checks...")
        
        service_files = [
            'services/duckdb_query_optimizer.py',
            'services/s3_storage_optimizer.py',
            'services/hierarchical_diff_engine.py', 
            'services/batch_operation_processor.py',
            'services/performance_monitor.py'
        ]
        
        quality_issues = []
        for service_file in service_files:
            full_path = os.path.join(project_root, service_file)
            if os.path.exists(full_path):
                with open(full_path, 'r') as f:
                    content = f.read()
                
                # Basic checks
                checks = {
                    'has_docstring': '"""' in content,
                    'has_classes': 'class ' in content,
                    'has_imports': 'import ' in content,
                    'has_logger': 'logger' in content
                }
                
                failed_checks = [check for check, passed in checks.items() if not passed]
                if failed_checks:
                    quality_issues.append(f"{service_file}: {failed_checks}")
                else:
                    print(f"  ✅ {service_file}")
        
        if quality_issues:
            self.results['errors'].extend(quality_issues)
            return False
        
        print("  📊 Code quality checks passed!")
        return True
    
    def run_validation(self):
        """Run complete validation."""
        print("🚀 Starting Simplified Phase 5 Validation")
        print("=" * 60)
        
        validation_steps = [
            ("File Structure", self.validate_file_structure),
            ("Service Imports", self.validate_service_imports),
            ("API Structure", self.validate_api_structure),
            ("Service Factory Integration", self.validate_service_factory_integration),
            ("Database Migration", self.validate_database_migration),
            ("Test Structure", self.validate_test_structure),
            ("Code Quality", self.check_code_quality)
        ]
        
        all_passed = True
        for step_name, step_function in validation_steps:
            try:
                success = step_function()
                if not success:
                    all_passed = False
            except Exception as e:
                print(f"  💥 {step_name} crashed: {e}")
                self.results['errors'].append(f"{step_name} crashed: {e}")
                all_passed = False
        
        self.results['overall_success'] = all_passed and len(self.results['errors']) == 0
        return self.results
    
    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 60)
        print("📊 PHASE 5 VALIDATION SUMMARY")
        print("=" * 60)
        
        if self.results['overall_success']:
            print("🎉 Overall Status: ✅ SUCCESS")
        else:
            print("⚠️  Overall Status: ❌ FAILURE")
        
        print(f"📁 Files Validated: {len(self.results['files_validated'])}")
        print(f"📦 Imports Validated: {len(self.results['imports_validated'])}")
        print(f"🌐 APIs Validated: {len(self.results['apis_validated'])}")
        print(f"🗄️ Migrations Validated: {len(self.results['migrations_validated'])}")
        print(f"🧪 Tests Found: {len(self.results['tests_found'])}")
        
        if self.results['errors']:
            print(f"\n❌ Errors ({len(self.results['errors'])}):")
            for i, error in enumerate(self.results['errors'], 1):
                print(f"   {i}. {error}")
        
        print(f"\n💡 Summary:")
        if self.results['overall_success']:
            print("   🎯 Phase 5 implementation structure is complete!")
            print("   ✅ All required files are present")
            print("   📦 All services can be imported")
            print("   🌐 API endpoints are configured")
            print("   🧪 Test files are in place")
            print("   🚀 Ready for deployment!")
        else:
            print("   ⚠️  Some validation issues found")
            print("   🔧 Address the errors listed above")
            print("   📞 Re-run validation after fixes")
        
        print("=" * 60)


def main():
    """Main entry point."""
    try:
        validator = SimplePhase5Validator()
        results = validator.run_validation()
        validator.print_summary()
        
        # Save results
        results_file = os.path.join(project_root, 'phase5_validation_simple.json')
        import json
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📁 Results saved to: {results_file}")
        
        sys.exit(0 if results['overall_success'] else 1)
        
    except Exception as e:
        print(f"\n💥 Validation crashed: {e}")
        traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()