#!/bin/bash
# Helper script to watch E2E test backend logs

LOG_FILE="../local-server/logs/context_studio.log"

echo "Watching backend logs: $LOG_FILE"
echo "Press Ctrl+C to stop"
echo "---"

# Tail the log file
tail -f "$LOG_FILE"
