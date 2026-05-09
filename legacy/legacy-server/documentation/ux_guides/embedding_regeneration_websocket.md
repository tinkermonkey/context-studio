# Embedding Regeneration WebSocket API Guide

This guide explains how to use the WebSocket API for regenerating structure_nodes embeddings with real-time progress updates.

## Endpoints

### WebSocket Endpoint
- **URL**: `ws://localhost:8001/api/embeddings/regenerate`
- **Query Parameters**:
  - `force` (optional, default: `false`): If `true`, regenerate all embeddings even if they exist

### REST Endpoints
- **GET** `/api/embeddings/status` - Check if regeneration is running
- **POST** `/api/embeddings/stop` - Stop current regeneration process

## WebSocket Usage

### JavaScript Example

```javascript
// Connect to WebSocket
const force = false; // Set to true to regenerate all embeddings
const ws = new WebSocket(`ws://localhost:8001/api/embeddings/regenerate?force=${force}`);

ws.onopen = () => {
    console.log('Connected to embedding regeneration WebSocket');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    switch (data.type) {
        case 'connected':
            console.log('✓ Connection confirmed');
            break;

        case 'started':
            console.log(`🚀 Started: ${data.message}`);
            console.log(`Start time: ${data.start_time}`);
            break;

        case 'progress':
            const progress = data.progress;
            updateUI(progress);
            break;

        case 'completed':
            console.log(`✅ Completed: ${data.message}`);
            console.log(`Total processed: ${data.total_processed}`);
            console.log(`Duration: ${data.duration_seconds}s`);
            break;

        case 'error':
            console.error(`❌ Error: ${data.message}`);
            break;
    }
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('WebSocket connection closed');
};

function updateUI(progress) {
    // Update progress bar
    const progressBar = document.getElementById('progress-bar');
    progressBar.style.width = `${progress.completion_percentage}%`;

    // Update progress text
    document.getElementById('progress-text').textContent =
        `${progress.completion_percentage.toFixed(1)}% (${progress.completed_nodes}/${progress.total_nodes})`;

    // Update current item
    document.getElementById('current-item').textContent =
        `${progress.current_node_type}: ${progress.current_node_title}`;

    // Update ETA
    const eta = Math.round(progress.estimated_remaining_seconds);
    document.getElementById('eta').textContent = `ETA: ${eta}s`;

    // Update processing rate
    document.getElementById('rate').textContent =
        `Rate: ${progress.processing_rate_per_second.toFixed(2)} nodes/sec`;

    // Show errors if any
    if (progress.error_count > 0) {
        document.getElementById('error-count').textContent =
            `Errors: ${progress.error_count}`;
    }
}
```

### React Hook Example

```javascript
import { useState, useEffect, useRef } from 'react';

export function useEmbeddingRegeneration() {
    const [status, setStatus] = useState('disconnected');
    const [progress, setProgress] = useState(null);
    const [error, setError] = useState(null);
    const wsRef = useRef(null);

    const connect = (force = false) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return; // Already connected
        }

        const ws = new WebSocket(`ws://localhost:8001/api/embeddings/regenerate?force=${force}`);
        wsRef.current = ws;

        ws.onopen = () => setStatus('connected');

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            switch (data.type) {
                case 'started':
                    setStatus('running');
                    setProgress(null);
                    setError(null);
                    break;

                case 'progress':
                    setProgress(data.progress);
                    break;

                case 'completed':
                    setStatus('completed');
                    break;

                case 'error':
                    setStatus('error');
                    setError(data.message);
                    break;
            }
        };

        ws.onerror = () => {
            setStatus('error');
            setError('WebSocket connection error');
        };

        ws.onclose = () => setStatus('disconnected');
    };

    const disconnect = () => {
        wsRef.current?.close();
    };

    useEffect(() => {
        return () => disconnect();
    }, []);

    return {
        status,
        progress,
        error,
        connect,
        disconnect
    };
}
```

## Message Types

### Connection Messages
```json
{
    "type": "connected",
    "message": "WebSocket connected for embedding regeneration",
    "force_regenerate": false
}
```

### Start Message
```json
{
    "type": "started",
    "message": "Starting embedding regeneration...",
    "start_time": "2025-09-26T06:42:41.970067"
}
```

### Progress Message
```json
{
    "type": "progress",
    "progress": {
        "total_nodes": 7,
        "completed_nodes": 3,
        "completion_percentage": 42.9,
        "current_node_title": "Apple iPhone",
        "current_node_type": "term",
        "start_time": "2025-09-26T06:42:41.970067",
        "current_time": "2025-09-26T06:42:44.123456",
        "estimated_remaining_seconds": 5.2,
        "processing_rate_per_second": 0.77,
        "error_count": 0,
        "errors": []
    }
}
```

### Completion Message
```json
{
    "type": "completed",
    "message": "Successfully regenerated embeddings for 7 structure_nodes",
    "total_processed": 7,
    "duration_seconds": 4.99
}
```

### Error Message
```json
{
    "type": "error",
    "message": "Embedding regeneration failed: Connection timeout"
}
```

## UI Recommendations

### Progress Display
- **Progress Bar**: Use `completion_percentage` for visual progress
- **Status Text**: Show `completed_nodes / total_nodes`
- **Current Item**: Display `current_node_type: current_node_title`
- **ETA**: Show `estimated_remaining_seconds` formatted as time
- **Rate**: Display `processing_rate_per_second` for performance insight

### Error Handling
- Show `error_count` if > 0
- Display recent errors from `progress.errors` array (last 5 errors)
- Provide retry option on connection failures
- Allow manual stop via REST endpoint

### User Experience
- **Disable navigation** during regeneration to prevent data corruption
- **Show confirmation dialog** before starting regeneration
- **Persist progress** in case of page refresh (use localStorage)
- **Provide cancel button** that calls the stop endpoint
- **Show completion notification** with processing statistics

## REST API Usage

### Check Status
```javascript
const response = await fetch('/api/embeddings/status');
const status = await response.json();
console.log('Is running:', status.is_running);
```

### Stop Regeneration
```javascript
const response = await fetch('/api/embeddings/stop', { method: 'POST' });
const result = await response.json();
console.log('Stopped:', result.stopped);
```

## Performance Notes

- Typical processing rate: 0.5-1.5 nodes/second depending on content length
- Memory usage increases with number of nodes being processed
- WebSocket connection automatically closes when regeneration completes
- Multiple concurrent regeneration requests are blocked at the service level