#!/bin/bash
# Heartbeat monitor for RunPod server logs
# Shows new log entries every 10 seconds

LOG_FILE="/Users/frederickige/Dev Projects/Sentence-Samurai/mokuro-server/server.log"

echo "🔍 Monitoring RunPod Server Logs (Ctrl+C to stop)"
echo "   Log file: $LOG_FILE"
echo "   Checking every 10 seconds for new entries..."
echo ""

# Get initial file size
last_size=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)

while true; do
    sleep 10

    # Get current file size
    current_size=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)

    # If file grew, show new lines
    if [ "$current_size" -gt "$last_size" ]; then
        echo "📡 $(date '+%Y-%m-%d %H:%M:%S') - New log entries:"
        tail -n $(( (current_size - last_size) / 80 )) "$LOG_FILE" 2>/dev/null | tail -20 || echo "  (unable to show new logs)"
        last_size=$current_size
    fi
done
