# NLP Analysis Proxy Monitoring - Updated Implementation

## Overview

The `/nlp_analysis/proxy/monitor` endpoint provides comprehensive monitoring statistics from the reference_api_buddy proxy when it's running. This implementation has been updated to match the improved monitoring structure from reference_api_buddy.

## Recent Updates

### Key Changes
- **Updated metric structure**: Changed from `cache_stats`, `upstream_stats`, etc. to `cache`, `upstream`, etc. to match the new API
- **Enhanced data format**: Now provides more detailed and structured metrics with per-domain breakdowns
- **Improved error handling**: Better handling of missing or unavailable monitoring components
- **Analysis utilities**: Added monitoring analysis tools for health assessment and performance summary

### New Monitoring Structure
The monitoring data now follows the improved reference_api_buddy format with:
- More granular cache metrics including compression and TTL distribution
- Detailed upstream performance with per-domain and overall statistics  
- Enhanced throttling information with current state and violation tracking
- Better organized database and proxy health metrics

## Endpoint

**GET** `/api/nlp_analysis/proxy/monitor`

## Response Format

### Success Response (Proxy Running with Monitoring Data)

```json
{
  "success": true,
  "proxy_running": true,
  "stats": {
    "cache": {
      "total_entries": 1247,
      "entries_per_domain": {
        "conceptnet": 892,
        "dbpedia": 355
      },
      "cache_size_bytes": 2485760,
      "cache_size_per_domain": {
        "conceptnet": 1847320,
        "dbpedia": 638440
      },
      "hit_count": 3420,
      "miss_count": 1247,
      "hit_rate": 0.733,
      "miss_rate": 0.267,
      "sets": 1247,
      "compressed": 892,
      "decompressed": 3420,
      "ttl_distribution": {
        "expired": 23,
        "valid": 1224,
        "average_ttl_remaining": 18360
      },
      "expired_entries": 23,
      "evicted_entries": 0
    },
    "upstream": {
      "overall": {
        "total_requests": 1247,
        "avg_response_time_ms": 245.3,
        "success_rate": 0.967,
        "error_rate": 0.033,
        "requests_per_hour": 89.1,
        "errors_by_status": {
          "200": 1206,
          "404": 28,
          "500": 8,
          "503": 5,
          "timeout": 0
        }
      },
      "by_domain": {
        "conceptnet": {
          "total_requests": 892,
          "avg_response_time_ms": 198.7,
          "success_rate": 0.982,
          "error_rate": 0.018,
          "requests_per_hour": 63.7,
          "errors_by_status": {
            "200": 876,
            "404": 12,
            "500": 3,
            "503": 1,
            "timeout": 0
          }
        },
        "dbpedia": {
          "total_requests": 355,
          "avg_response_time_ms": 367.2,
          "success_rate": 0.930,
          "error_rate": 0.070,
          "requests_per_hour": 25.4,
          "errors_by_status": {
            "200": 330,
            "404": 16,
            "500": 5,
            "503": 4,
            "timeout": 0
          }
        }
      }
    },
    "database": {
      "db_file_path": "/path/to/api_buddy_cache.db",
      "db_file_size_bytes": 2847392,
      "db_health": "healthy",
      "in_memory_cache_size": "unavailable"
    },
    "proxy_health": {
      "uptime_seconds": 3647.2,
      "active_threads": 8,
      "recent_errors": []
    },
    "throttling": {
      "requests_per_domain": {
        "conceptnet": {
          "current_hour_requests": 63,
          "total_requests": 892,
          "violations": 2,
          "current_delay_seconds": 4
        },
        "dbpedia": {
          "current_hour_requests": 25,
          "total_requests": 355,
          "violations": 0,
          "current_delay_seconds": 1
        }
      },
      "throttle_state": {
        "conceptnet": {
          "is_throttled": true,
          "violations": 2,
          "delay_seconds": 4,
          "last_violation": 1650123456.78
        },
        "dbpedia": {
          "is_throttled": false,
          "violations": 0,
          "delay_seconds": 1,
          "last_violation": 0.0
        }
      },
      "default_requests_per_hour": 1000,
      "progressive_max_delay": 300,
      "progressive_enabled": true,
      "domain_limits": {
        "conceptnet": 500,
        "dbpedia": 200
      }
    },
    "timestamp": 1692806000
  }
}
```

### Success Response (Proxy Not Running)

```json
{
  "success": true,
  "proxy_running": false,
  "message": "Proxy is not currently running",
  "stats": null
}
```

### Success Response (Monitoring Data Not Available)

```json
{
  "success": true,
  "proxy_running": true,
  "message": "Monitoring data not available",
  "stats": null
}
```

### Error Response

```json
{
  "success": false,
  "error": "Error message describing what went wrong"
}
```

## Implementation Details

### ProxyManager Updates

The `ReferenceAPIProxyManager` class now includes:

- `get_monitoring_stats()`: Collects comprehensive monitoring data from the proxy's MonitoringManager
- `_safe_get_stats()`: Safely calls monitoring methods with error handling

### Monitoring Categories

1. **Cache Stats**: 
   - Total entries and per-domain breakdown
   - Cache size in bytes (total and per-domain)
   - Hit/miss counts and rates
   - Compression statistics
   - TTL distribution and expired/evicted entries

2. **Upstream Stats**: 
   - Overall and per-domain metrics
   - Response times, success/error rates
   - Request volumes and requests per hour
   - Detailed error breakdown by HTTP status code

3. **Database Stats**: 
   - Database file path and size
   - Database health status
   - In-memory cache size information

4. **Proxy Health**: 
   - Uptime in seconds
   - Active thread count
   - Recent error log

5. **Throttling Stats**: 
   - Per-domain request counts and violations
   - Current throttle state and delay seconds
   - Domain-specific limits and configuration
   - Progressive throttling settings

### Error Handling

- Returns `null` stats when proxy is not running
- Returns `null` stats when monitoring data is unavailable
- Individual stat categories that fail return `{"error": "...", "available": false}`
- All errors are logged appropriately
- Robust handling of missing monitoring manager or proxy components

### Key Improvements

The updated implementation now provides:

- **Structured metrics**: Clear separation between overall and per-domain statistics
- **Comprehensive cache metrics**: Including compression stats, TTL distribution, and eviction tracking
- **Detailed upstream metrics**: Per-domain breakdown with success rates and error categorization
- **Enhanced throttling info**: Current state, violations, and progressive throttling configuration
- **Better error reporting**: Granular error handling for each monitoring component

## Testing

Use the provided test script `test_proxy_monitoring.py` to verify the endpoint functionality:

```bash
python test_proxy_monitoring.py
```

This will test both the status and monitoring endpoints and display the results.
