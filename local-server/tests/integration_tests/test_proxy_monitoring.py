#!/usr/bin/env python3
"""
Test script for proxy monitoring functionality.
"""

import requests
import json
import time
import sys
import os

# Add the project root to the path to import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from utils.monitoring_analysis import analyze_proxy_health, get_performance_summary
    ANALYSIS_AVAILABLE = True
except ImportError:
    ANALYSIS_AVAILABLE = False
    print("Warning: Monitoring analysis utilities not available")

def test_proxy_monitoring():
    """Test the new proxy monitoring endpoint"""
    base_url = "http://localhost:8000"
    
    print("Testing proxy monitoring endpoint...")
    
    # Test status endpoint first
    try:
        response = requests.get(f"{base_url}/api/nlp_analysis/proxy/status")
        print(f"Status endpoint: {response.status_code}")
        if response.status_code == 200:
            status_data = response.json()
            print(f"Proxy running: {status_data.get('proxy_running', False)}")
            print(f"Proxy enabled: {status_data.get('proxy_enabled', False)}")
        else:
            print(f"Status error: {response.text}")
    except Exception as e:
        print(f"Error calling status endpoint: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Test monitoring endpoint
    try:
        response = requests.get(f"{base_url}/api/nlp_analysis/proxy/monitor")
        print(f"Monitor endpoint: {response.status_code}")
        
        if response.status_code == 200:
            monitor_data = response.json()
            print(f"Success: {monitor_data.get('success', False)}")
            print(f"Proxy running: {monitor_data.get('proxy_running', False)}")
            
            stats = monitor_data.get('stats')
            if stats:
                print("\nMonitoring Statistics:")
                print(f"Cache stats available: {'cache' in stats}")
                print(f"Upstream stats available: {'upstream' in stats}")
                print(f"Database stats available: {'database' in stats}")
                print(f"Proxy health available: {'proxy_health' in stats}")
                print(f"Throttling stats available: {'throttling' in stats}")
                print(f"Timestamp: {stats.get('timestamp', 'N/A')}")
                
                # Print detailed stats if available
                for stat_type in ['cache', 'upstream', 'database', 'proxy_health', 'throttling']:
                    if stat_type in stats and stats[stat_type]:
                        print(f"\n{stat_type.replace('_', ' ').title()}:")
                        stat_data = stats[stat_type]
                        if isinstance(stat_data, dict) and 'error' not in stat_data:
                            print(json.dumps(stat_data, indent=2))
                        else:
                            print(f"  Error or unavailable: {stat_data}")
                
                # Perform analysis if available
                if ANALYSIS_AVAILABLE and stats:
                    print("\n" + "="*50)
                    print("PERFORMANCE ANALYSIS")
                    print("="*50)
                    
                    # Get health analysis
                    health_analysis = analyze_proxy_health(stats)
                    print(f"\nOverall Health: {health_analysis['overall_health'].upper()}")
                    
                    if health_analysis['alerts']:
                        print("\nAlerts:")
                        for alert in health_analysis['alerts']:
                            print(f"  [{alert['level'].upper()}] {alert['type']}: {alert['message']}")
                            print(f"    Recommendation: {alert['recommendation']}")
                    
                    # Get performance summary
                    perf_summary = get_performance_summary(stats)
                    if 'metrics' in perf_summary:
                        print(f"\nPerformance Summary:")
                        print(json.dumps(perf_summary['metrics'], indent=2))
            else:
                print(f"Message: {monitor_data.get('message', 'No message')}")
        else:
            print(f"Monitor error: {response.text}")
            
    except Exception as e:
        print(f"Error calling monitor endpoint: {e}")

if __name__ == "__main__":
    test_proxy_monitoring()
