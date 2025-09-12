# LLM Traceability UX Integration Guide

## Overview

The LLM Traceability system provides comprehensive tracking of AI-generated suggestions and user interactions, enabling data-driven improvements to prompt engineering and user experience. This guide explains how the UX team can leverage the traceability APIs to create meaningful user experiences around AI suggestion tracking.

## Key Concepts

### Execution Tracking
Every LLM suggestion request is tracked with a unique `execution_id` that follows the suggestion through its entire lifecycle:
- **Start**: When a user requests an AI suggestion
- **Complete**: When the AI returns a response
- **Selection**: When a user selects/applies the suggestion

### Selection Recording
When users interact with AI suggestions (accept, modify, or reject), these actions are recorded to understand:
- Which suggestions are most useful
- What modifications users commonly make
- Which types of requests produce the best results

### Analytics & Insights
Aggregated data provides insights into:
- Success rates by suggestion type
- Performance metrics
- User behavior patterns
- Areas for prompt improvement

## Available APIs

### 1. Selection Recording API

**Endpoint**: `POST /api/llm/record-selection`

**Purpose**: Record when a user selects or applies an AI suggestion

**Request Body**:
```json
{
  "execution_id": "uuid-from-suggestion-response",
  "record_type": "structure_node",
  "record_id": "node-123", 
  "suggestion_field": "definition",
  "selected_content": "The actual text the user selected/applied"
}
```

**When to Use**:
- User clicks "Accept" on a suggestion
- User applies a suggestion with modifications
- User copies suggestion content
- User saves/commits changes that include AI suggestions

### 2. Execution Analytics API  

**Endpoint**: `GET /api/llm/execution-analytics`

**Purpose**: Get aggregated statistics about AI suggestion usage

**Query Parameters**:
- `pipeline_type` (optional): Filter by suggestion type
  - `suggest_term_definition`
  - `suggest_layer_definition` 
  - `suggest_domain_definition`
- `days_back` (optional): Number of days to include (default: 30)

**Response**:
```json
{
  "success": true,
  "data": {
    "total_executions": 1250,
    "successful_executions": 1189,
    "success_rate": 0.95,
    "avg_execution_time": 1847.3,
    "total_tokens_used": 125430,
    "total_selections": 456,
    "selection_rate": 0.38
  },
  "filters": {
    "pipeline_type": "all",
    "days_back": 30
  }
}
```

**When to Use**:
- Dashboard/analytics views
- Performance monitoring displays
- Usage statistics for admins
- A/B testing result analysis

### 3. Execution History API

**Endpoint**: `GET /api/llm/execution-history/{execution_id}`

**Purpose**: Get detailed information about a specific AI suggestion

**Response**:
```json
{
  "success": true,
  "data": {
    "execution": {
      "id": "execution-uuid",
      "pipeline_type": "suggest_term_definition",
      "status": "success",
      "user_prompt": "Define: machine learning",
      "response_message": "Machine learning is...",
      "execution_time_ms": 1500,
      "token_usage": {
        "input_tokens": 25,
        "output_tokens": 87,
        "total_tokens": 112
      },
      "started_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:30:01Z"
    },
    "selections": [
      {
        "id": "selection-uuid",
        "record_type": "structure_node",
        "record_id": "node-123",
        "suggestion_field": "definition", 
        "selected_content": "Machine learning is...",
        "date_created": "2024-01-15T10:31:00Z"
      }
    ]
  }
}
```

**When to Use**:
- Detailed audit trails
- Debugging suggestion issues
- User history/activity logs
- Quality assurance workflows

### 4. Health Check API

**Endpoint**: `GET /api/llm/health`

**Purpose**: Verify traceability system is operational

**When to Use**:
- System status dashboards
- Automated health monitoring
- Troubleshooting connectivity issues

## UX Implementation Patterns

### 1. Suggestion Selection Tracking

**Pattern**: Track user acceptance of AI suggestions

```javascript
// When user accepts a suggestion
async function acceptSuggestion(executionId, nodeId, field, content) {
  try {
    await fetch('/api/llm/record-selection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        execution_id: executionId,
        record_type: 'structure_node',
        record_id: nodeId,
        suggestion_field: field,
        selected_content: content
      })
    });
    
    // Show success feedback to user
    showToast('Suggestion applied successfully');
  } catch (error) {
    // Handle gracefully - don't block user workflow
    console.warn('Failed to record selection:', error);
  }
}
```

**UI Considerations**:
- Always record selections asynchronously
- Don't block user workflow if recording fails
- Provide subtle feedback when suggestions are tracked
- Consider showing "learning from your choices" messages

### 2. Usage Analytics Dashboard

**Pattern**: Display AI suggestion usage statistics

```javascript
// Fetch analytics for dashboard
async function loadAnalytics(timeframe = 30) {
  const response = await fetch(`/api/llm/execution-analytics?days_back=${timeframe}`);
  const { data } = await response.json();
  
  return {
    totalSuggestions: data.total_executions,
    successRate: `${Math.round(data.success_rate * 100)}%`,
    avgResponseTime: `${data.avg_execution_time}ms`,
    selectionRate: `${Math.round(data.selection_rate * 100)}%`,
    tokensUsed: data.total_tokens_used.toLocaleString()
  };
}
```

**UI Components**:
- Success rate indicators (with color coding)
- Usage trend charts
- Performance metrics cards  
- Comparison views (by suggestion type)

### 3. Suggestion Quality Feedback

**Pattern**: Allow users to rate suggestion quality

```javascript
// Enhanced selection recording with quality rating
async function recordSelectionWithRating(executionId, nodeId, field, content, rating) {
  // Record the basic selection
  await recordSelection(executionId, nodeId, field, content);
  
  // Could extend to include quality ratings in future
  // For now, the fact that they selected it indicates quality
  
  // Show appreciation for feedback
  if (rating >= 4) {
    showToast('Thanks! This helps us improve suggestions');
  }
}
```

**UI Elements**:
- Thumbs up/down on suggestions
- Star ratings
- Quick feedback buttons ("Helpful", "Not quite", "Perfect")
- Optional feedback text areas

### 4. Suggestion History & Audit Trail

**Pattern**: Show users their AI suggestion history

```javascript
// Load user's suggestion history
async function loadSuggestionHistory(nodeId) {
  // This would require extending the API to filter by record_id
  // For now, this represents the desired UX pattern
  
  const suggestions = await fetchUserSuggestionHistory(nodeId);
  
  return suggestions.map(s => ({
    timestamp: new Date(s.execution.started_at),
    prompt: s.execution.user_prompt,
    suggestion: s.execution.response_message,
    wasSelected: s.selections.length > 0,
    executionTime: s.execution.execution_time_ms
  }));
}
```

**UI Components**:
- Suggestion timeline/history view
- "Previously suggested" indicators
- Suggestion comparison tools
- Revert to previous suggestion options

## Best Practices

### 1. User Privacy & Transparency

- **Be Transparent**: Let users know their interactions are being tracked for improvement
- **Provide Value**: Show users how tracking helps improve their experience
- **Respect Privacy**: Only track interactions, not personal content details
- **Allow Opt-out**: Consider preference to disable tracking

### 2. Performance Considerations

- **Async Recording**: Never block user workflows for tracking calls
- **Graceful Degradation**: App should work fully even if tracking fails
- **Batch Updates**: Consider batching multiple selections if performance is critical
- **Error Handling**: Log tracking failures but don't show errors to users

### 3. User Experience

- **Subtle Feedback**: Provide gentle confirmation when selections are recorded
- **Learning Indicators**: Show "AI is learning from your choices" messages
- **Progress Visualization**: Use analytics to show AI improvement over time
- **Context Awareness**: Consider showing relevant usage stats contextually

### 4. Data Visualization

- **Success Rates**: Use color-coded indicators (green/yellow/red)
- **Trends**: Show improvement over time
- **Comparisons**: Allow filtering by suggestion type, time period
- **Actionable Insights**: Highlight patterns users can act on

## Error Handling

### API Error Responses

All APIs return structured error responses:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes**:
- `400`: Bad request (invalid execution_id, missing fields)
- `404`: Resource not found (execution doesn't exist)
- `422`: Validation error (invalid enum values, malformed data)
- `500`: Server error (database issues, system problems)
- `503`: Service unavailable (traceability system down)

### UX Error Handling Strategy

```javascript
async function recordSelectionSafely(data) {
  try {
    await recordSelection(data);
  } catch (error) {
    // Log for debugging but don't disrupt user
    console.warn('Selection tracking failed:', error.message);
    
    // Optionally queue for retry
    queueForRetry(data);
    
    // Don't show error to user unless critical
    // Tracking is enhancement, not core functionality
  }
}
```

## Future Enhancements

The traceability system is designed to be extensible. Future UX opportunities include:

- **Smart Suggestions**: Use selection patterns to improve future suggestions
- **Personalization**: Tailor suggestions based on user preferences
- **A/B Testing**: Test different prompt strategies with real usage data
- **Quality Scoring**: Develop suggestion quality metrics based on selection rates
- **Collaborative Learning**: Share successful patterns across users (with privacy)

## Getting Started

1. **Review the APIs**: Understand the four available endpoints
2. **Identify Touch Points**: Find where users interact with AI suggestions in your UX
3. **Implement Selection Tracking**: Add recording calls to suggestion acceptance flows
4. **Add Analytics Views**: Create dashboards using the analytics API  
5. **Test Error Handling**: Ensure graceful degradation when tracking fails
6. **Gather Feedback**: Ask users about the value of tracking features

The traceability system provides a foundation for data-driven AI improvement. Start with basic selection tracking and gradually add more sophisticated analytics and user-facing features as the system matures.