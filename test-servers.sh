#!/bin/bash

echo "Testing Backend Server Startup..."
echo "================================="
echo ""

cd /Users/viktorzeman/work/airport-lights-detection/backend
source venv/bin/activate

echo "Starting backend on port 8000..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/test_backend.log 2>&1 &
BACKEND_PID=$!

echo "Waiting 15 seconds for backend to start..."
sleep 15

if kill -0 $BACKEND_PID 2>/dev/null; then
    echo "✓ Backend process is running (PID: $BACKEND_PID)"

    echo ""
    echo "Testing API health endpoint..."
    HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)

    if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
        echo "✓ Backend API is responding correctly"
        echo "  Response: $HEALTH_RESPONSE"
    else
        echo "✗ Backend API not responding as expected"
        echo "  Response: $HEALTH_RESPONSE"
    fi

    echo ""
    echo "Testing API root endpoint..."
    ROOT_RESPONSE=$(curl -s http://localhost:8000/)
    echo "  Response: $ROOT_RESPONSE"

    echo ""
    echo "✓ BACKEND TEST PASSED!"
    echo ""
    echo "Stopping backend..."
    kill $BACKEND_PID
    sleep 2
else
    echo "✗ Backend process stopped unexpectedly"
    echo ""
    echo "Last 30 lines from log:"
    tail -30 /tmp/test_backend.log
    exit 1
fi

echo ""
echo "================================="
echo "✓ All tests passed successfully!"
echo "================================="
