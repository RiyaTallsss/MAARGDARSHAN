#!/bin/bash
# Quick script to run frontend locally

echo "🚀 Starting MAARGDARSHAN Frontend..."
echo ""
echo "Opening in browser..."
echo "URL: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd frontend
python3 -m http.server 8000
