#!/usr/bin/env python3
"""
Test Runner Suite Summary

This directory contains multiple test runner tools for different use cases:

1. core_test_mapper.py - Simple, clean implementation of the exact function requested
2. test_runner.py - Full-featured command-line tool with comprehensive options
3. test_failure_example.py - Example usage and patterns
4. README_test_runner.md - Complete documentation

Quick Start:
"""

from core_test_mapper import run_tests_with_file_mapping, run_tests_with_file_mapping_enhanced


def demo_basic_usage():
    """Demonstrate the basic requested functionality."""
    print("🔧 Basic Usage (exact function as requested):")
    print("=" * 50)
    
    try:
        # This is the exact function signature requested by the user
        failures = run_tests_with_file_mapping_enhanced(['tests/unit_tests/', '-x'])
        
        print(f"Found test results for {len(failures)} files")
        
        # Show summary
        if '_summary' in failures:
            summary = failures['_summary']
            print(f"📊 Summary: {summary['passed']} passed, {summary['failed']} failed")
        
        # Show failures by source file
        for source_file, results in failures.items():
            if source_file == '_summary':
                continue
                
            failed_results = [r for r in results if r['outcome'] == 'failed']
            if failed_results:
                print(f"\n❌ {source_file}:")
                for failure in failed_results:
                    print(f"   • {failure['test_name'].split('::')[-1]}")
                    if failure['line']:
                        print(f"     Line {failure['line']}")
                        
    except Exception as e:
        print(f"Error: {e}")


def demo_advanced_usage():
    """Demonstrate advanced features."""
    print("\n🚀 Advanced Usage:")
    print("=" * 50)
    
    # Import the full test runner
    from test_runner import TestFailureMapper
    
    mapper = TestFailureMapper()
    
    # Run with specific options
    results = mapper.run_tests_with_file_mapping(
        test_args=['tests/unit_tests/', '-v', '--tb=short'],
        include_passed=False
    )
    
    print(f"Advanced mapper found results for {len(results)} files")
    
    # Show formatted output
    formatted = mapper.format_results(results)
    print("\nFormatted Output Preview:")
    print(formatted[:500] + "..." if len(formatted) > 500 else formatted)


def show_available_tools():
    """Show all available tools in this directory."""
    print("\n🛠️  Available Tools:")
    print("=" * 50)
    
    tools = [
        ("core_test_mapper.py", "Simple implementation with exact requested function"),
        ("test_runner.py", "Full CLI tool with comprehensive features"),
        ("test_failure_example.py", "Example usage patterns"),
        ("README_test_runner.md", "Complete documentation and examples"),
    ]
    
    for tool, description in tools:
        print(f"📄 {tool:<25} - {description}")
    
    print("\n💡 Quick Commands:")
    print("   python core_test_mapper.py                    # Simple demo")
    print("   python test_runner.py tests/unit_tests/      # Run specific tests")
    print("   python test_runner.py --format json          # JSON output")
    print("   python test_runner.py --include-passed       # Include all results")


if __name__ == "__main__":
    print("🧪 Test Runner Suite for Agents")
    print("="*60)
    
    show_available_tools()
    demo_basic_usage()
    demo_advanced_usage()
    
    print("\n✅ Test runner suite is ready for agent use!")
    print("   See README_test_runner.md for full documentation")