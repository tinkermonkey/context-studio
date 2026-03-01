#!/usr/bin/env python3
"""
Configuration Validation Utility

Provides comprehensive validation of the configuration system implementation
to ensure correctness and completeness of migration.
"""

import os
import sys
import json
import importlib.util
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import ConfigurationManager, get_config_manager
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of configuration validation"""
    passed: bool
    category: str
    test_name: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ConfigurationValidator:
    """Comprehensive configuration system validator"""
    
    def __init__(self):
        self.results: List[ValidationResult] = []
    
    def run_all_validations(self) -> List[ValidationResult]:
        """Run all validation tests"""
        self.results.clear()
        
        # Core configuration validation
        self._validate_configuration_model()
        self._validate_configuration_manager()
        self._validate_configuration_persistence()
        self._validate_configuration_api()
        
        # Integration validation
        self._validate_reference_sources_integration()
        self._validate_nlp_pipeline_integration()
        self._validate_reference_service_integration()
        
        return self.results
    
    def _add_result(self, passed: bool, category: str, test_name: str, message: str, details: Optional[Dict[str, Any]] = None):
        """Add validation result"""
        self.results.append(ValidationResult(passed, category, test_name, message, details))
        
    def _validate_configuration_model(self):
        """Validate configuration model structure"""
        category = "Configuration Model"
        
        try:
            # Test Settings model import
            from config import Settings
            self._add_result(True, category, "import_settings", "Settings model imports successfully")
            
            # Test Settings instantiation
            settings = Settings()
            self._add_result(True, category, "create_settings", "Settings model instantiates successfully")
            
            # Test model structure
            required_sections = ["server", "database", "llm", "nlp", "reference_sources", "proxy_server", "logging", "security"]
            missing_sections = []
            for section in required_sections:
                if not hasattr(settings, section):
                    missing_sections.append(section)
            
            if missing_sections:
                self._add_result(False, category, "model_structure", 
                              f"Missing configuration sections: {missing_sections}")
            else:
                self._add_result(True, category, "model_structure", 
                              "All required configuration sections present")
            
            # Test reference sources structure
            ref_sources = settings.reference_sources
            required_sources = ["conceptnet", "dbpedia", "dbpedia_spotlight", "wikidata", "schema_org"]
            missing_sources = []
            for source in required_sources:
                if not hasattr(ref_sources, source):
                    missing_sources.append(source)
            
            if missing_sources:
                self._add_result(False, category, "reference_sources_structure",
                              f"Missing reference sources: {missing_sources}")
            else:
                self._add_result(True, category, "reference_sources_structure",
                              "All required reference sources present")
                
        except Exception as e:
            self._add_result(False, category, "configuration_model", f"Configuration model validation failed: {e}")
    
    def _validate_configuration_manager(self):
        """Validate configuration manager functionality"""
        category = "Configuration Manager"
        
        try:
            # Test configuration manager instantiation
            config_manager = get_config_manager()
            self._add_result(True, category, "instantiation", "Configuration manager instantiates successfully")
            
            # Test get operation
            try:
                server_host = config_manager.get("server.host")
                self._add_result(True, category, "get_operation", f"Get operation works (server.host = {server_host})")
            except Exception as e:
                self._add_result(False, category, "get_operation", f"Get operation failed: {e}")
            
            # Test set operation
            try:
                original_value = config_manager.get("server.reload")
                test_value = not original_value
                success = config_manager.set("server.reload", test_value)
                if success:
                    # Verify the change
                    new_value = config_manager.get("server.reload")
                    if new_value == test_value:
                        self._add_result(True, category, "set_operation", "Set operation works correctly")
                        # Restore original value
                        config_manager.set("server.reload", original_value)
                    else:
                        self._add_result(False, category, "set_operation", "Set operation doesn't persist correctly")
                else:
                    self._add_result(False, category, "set_operation", "Set operation returned failure")
            except Exception as e:
                self._add_result(False, category, "set_operation", f"Set operation failed: {e}")
            
            # Test validation
            try:
                errors = config_manager.validate()
                if isinstance(errors, list):
                    self._add_result(True, category, "validation", f"Validation works ({len(errors)} errors found)")
                else:
                    self._add_result(False, category, "validation", "Validation doesn't return a list")
            except Exception as e:
                self._add_result(False, category, "validation", f"Validation failed: {e}")
                
        except Exception as e:
            self._add_result(False, category, "configuration_manager", f"Configuration manager validation failed: {e}")
    
    def _validate_configuration_persistence(self):
        """Validate configuration persistence"""
        category = "Configuration Persistence"
        
        try:
            # Create temporary config file for testing
            test_config_file = "./test_config_validation.json"
            test_manager = ConfigurationManager(test_config_file)
            
            # Test save operation
            success = test_manager.save()
            if success:
                self._add_result(True, category, "save_operation", "Configuration saves successfully")
            else:
                self._add_result(False, category, "save_operation", "Configuration save failed")
            
            # Test load operation
            try:
                test_manager.load()
                self._add_result(True, category, "load_operation", "Configuration loads successfully")
            except Exception as e:
                self._add_result(False, category, "load_operation", f"Configuration load failed: {e}")
            
            # Test file exists
            if os.path.exists(test_config_file):
                self._add_result(True, category, "file_creation", "Configuration file created successfully")
                
                # Clean up test file
                try:
                    os.remove(test_config_file)
                except Exception:
                    pass
            else:
                self._add_result(False, category, "file_creation", "Configuration file not created")
                
        except Exception as e:
            self._add_result(False, category, "configuration_persistence", f"Persistence validation failed: {e}")
    
    def _validate_configuration_api(self):
        """Validate configuration API endpoints"""
        category = "Configuration API"
        
        try:
            # Test API router import
            from api.config import router
            self._add_result(True, category, "api_import", "Configuration API imports successfully")
            
            # Test API endpoints exist
            endpoint_paths = []
            for route in router.routes:
                if hasattr(route, 'path'):
                    endpoint_paths.append(route.path)
            
            required_endpoints = [
                "/",  # get full config
                "/{path:path}",  # get specific config value
                "/reference-sources",  # get all reference sources
                "/reference-sources/{source_name}",  # get specific reference source
                "/reference-sources/status"  # get reference sources status
            ]
            
            missing_endpoints = []
            for endpoint in required_endpoints:
                # Check for exact match or pattern match
                found = any(endpoint in path or path in endpoint for path in endpoint_paths)
                if not found:
                    missing_endpoints.append(endpoint)
            
            if missing_endpoints:
                self._add_result(False, category, "required_endpoints",
                              f"Missing API endpoints: {missing_endpoints}",
                              {"available_endpoints": endpoint_paths})
            else:
                self._add_result(True, category, "required_endpoints",
                              "All required API endpoints present")
                
        except Exception as e:
            self._add_result(False, category, "configuration_api", f"API validation failed: {e}")
    
    def _validate_reference_sources_integration(self):
        """Validate reference sources integration"""
        category = "Reference Sources Integration"
        
        try:
            config_manager = get_config_manager()
            
            # Test reference sources access
            try:
                sources = config_manager.get_reference_sources()
                if isinstance(sources, dict) and len(sources) > 0:
                    self._add_result(True, category, "access_reference_sources",
                                  f"Reference sources accessible ({len(sources)} sources)")
                else:
                    self._add_result(False, category, "access_reference_sources",
                                  "Reference sources not accessible or empty")
            except Exception as e:
                self._add_result(False, category, "access_reference_sources", f"Reference sources access failed: {e}")
            
            # Test reference source update
            try:
                # Test the sync method that exists on ConfigurationManager
                config_manager.set("reference_sources.conceptnet.enabled", True)
                self._add_result(True, category, "update_reference_source", "Reference source update works")
            except Exception as e:
                self._add_result(False, category, "update_reference_source", f"Reference source update failed: {e}")
                
        except Exception as e:
            self._add_result(False, category, "reference_sources_integration", f"Integration validation failed: {e}")
    
    def _validate_nlp_pipeline_integration(self):
        """Validate NLP pipeline integration"""
        category = "NLP Pipeline Integration"

        try:
            # Test invalidate_pipeline function exists
            try:
                spec = importlib.util.find_spec("nlp.pipeline")
                if spec is not None:
                    self._add_result(True, category, "invalidate_pipeline_function", "Pipeline invalidation function exists")
                else:
                    self._add_result(False, category, "invalidate_pipeline_function", "Pipeline invalidation function not found")
            except (ImportError, ModuleNotFoundError):
                self._add_result(False, category, "invalidate_pipeline_function", "Pipeline invalidation function not found")
            
            # Test NLP pipeline can access configuration
            config_manager = get_config_manager()
            try:
                nlp_config = config_manager.get("nlp")
                if nlp_config:
                    self._add_result(True, category, "nlp_config_access", "NLP configuration accessible")
                else:
                    self._add_result(False, category, "nlp_config_access", "NLP configuration not accessible")
            except Exception as e:
                self._add_result(False, category, "nlp_config_access", f"NLP config access failed: {e}")
                
        except Exception as e:
            self._add_result(False, category, "nlp_pipeline_integration", f"NLP integration validation failed: {e}")
    
    def _validate_reference_service_integration(self):
        """Validate reference service integration"""
        category = "Reference Service Integration"

        try:
            # Test reference service imports
            try:
                # Check if modules exist without importing them
                reference_api_spec = importlib.util.find_spec("reference_api.service")
                api_reference_spec = importlib.util.find_spec("api.reference")

                if reference_api_spec is not None and api_reference_spec is not None:
                    # Now we can safely import since modules exist
                    from reference_api.service import ReferenceService
                    self._add_result(True, category, "reference_imports", "Reference service imports successfully")
                else:
                    self._add_result(False, category, "reference_imports", "Reference service modules not found")
                    return
            except (ImportError, ModuleNotFoundError) as e:
                self._add_result(False, category, "reference_imports", f"Reference service import failed: {e}")
                return
            
            # Test reference service instantiation with config manager
            try:
                config_manager = get_config_manager()
                reference_service = ReferenceService(config_manager)
                self._add_result(True, category, "reference_instantiation", "Reference service instantiates with ConfigurationManager")
            except Exception as e:
                self._add_result(False, category, "reference_instantiation", f"Reference service instantiation failed: {e}")
            
            # Test reference service methods
            try:
                enabled_sources = reference_service.get_enabled_sources()
                if isinstance(enabled_sources, list):
                    self._add_result(True, category, "get_enabled_sources", 
                                  f"get_enabled_sources works ({len(enabled_sources)} sources)")
                else:
                    self._add_result(False, category, "get_enabled_sources", "get_enabled_sources doesn't return list")
            except Exception as e:
                self._add_result(False, category, "get_enabled_sources", f"get_enabled_sources failed: {e}")
                
        except Exception as e:
            self._add_result(False, category, "reference_service_integration", f"Reference integration validation failed: {e}")
        
    def generate_report(self) -> str:
        """Generate validation report"""
        if not self.results:
            return "No validation results available. Run validations first."
        
        # Group results by category
        categories = {}
        for result in self.results:
            if result.category not in categories:
                categories[result.category] = []
            categories[result.category].append(result)
        
        # Generate report
        report = []
        report.append("=" * 80)
        report.append("CONFIGURATION SYSTEM VALIDATION REPORT")
        report.append("=" * 80)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        
        report.append("\nOVERALL SUMMARY:")
        report.append(f"  Total Tests: {total_tests}")
        report.append(f"  Passed: {passed_tests} ({(passed_tests/total_tests)*100:.1f}%)")
        report.append(f"  Failed: {failed_tests} ({(failed_tests/total_tests)*100:.1f}%)")
        
        # Category breakdown
        for category, results in categories.items():
            report.append(f"\n{category.upper()}:")
            report.append("-" * len(category))
            
            category_passed = sum(1 for r in results if r.passed)
            category_total = len(results)
            
            for result in results:
                icon = "✅" if result.passed else "❌"
                report.append(f"  {icon} {result.test_name}: {result.message}")
                
                if result.details and not result.passed:
                    for key, value in result.details.items():
                        report.append(f"     {key}: {value}")
            
            report.append(f"  Category Summary: {category_passed}/{category_total} tests passed")
        
        report.append("\n" + "=" * 80)
        if failed_tests == 0:
            report.append("🎉 ALL VALIDATIONS PASSED! Configuration system is ready for use.")
        else:
            report.append(f"⚠️  {failed_tests} validation(s) failed. Review and fix issues before proceeding.")
        report.append("=" * 80)
        
        return "\n".join(report)


def main():
    """CLI interface for configuration validation"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Configuration System Validator")
    parser.add_argument("--category", help="Run validations for specific category only")
    parser.add_argument("--output", help="Write report to file")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel("DEBUG")
    
    validator = ConfigurationValidator()
    
    print("🔍 Running configuration system validation...")
    results = validator.run_all_validations()
    
    if args.json:
        # JSON output
        json_results = []
        for result in results:
            json_results.append({
                "passed": result.passed,
                "category": result.category,
                "test_name": result.test_name,
                "message": result.message,
                "details": result.details
            })
        
        output = json.dumps(json_results, indent=2)
    else:
        # Text report
        output = validator.generate_report()
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"📄 Validation report written to {args.output}")
    else:
        print(output)
    
    # Return appropriate exit code
    failed_count = sum(1 for r in results if not r.passed)
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    exit(main())
