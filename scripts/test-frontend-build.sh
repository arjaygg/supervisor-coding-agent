#!/bin/bash

# Simple test for frontend build without Docker

set -e

echo "🧪 Testing frontend build (no Docker)..."

# Get project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "📂 Working in: $(pwd)"
echo "🔍 Checking if we're in the right place..."
if [ ! -d "frontend" ]; then
    echo "❌ Frontend directory not found. Are you in the project root?"
    exit 1
fi

cd frontend
echo "📂 Now in: $(pwd)"

echo "📦 Installing dependencies..."
npm ci

echo "🔧 Setting build environment..."
export NODE_ENV=production
export VITE_API_URL=https://dev.dev-assist.example.com/api
export VITE_WS_URL=wss://dev.dev-assist.example.com/ws

echo "🏗️ Running build..."
npm run build

echo "📁 Checking build output..."
if [ -d "build" ]; then
    echo "✅ Build directory created successfully"
    echo "📋 Build contents:"
    ls -la build/
    echo "📊 Build size:"
    du -sh build/
    
    echo "🔍 Checking for index.html..."
    if [ -f "build/index.html" ]; then
        echo "✅ index.html found"
        echo "📄 First few lines of index.html:"
        head -5 build/index.html
    else
        echo "❌ index.html not found in build directory"
    fi
else
    echo "❌ Build directory not found"
    exit 1
fi

echo "🎉 Frontend build test completed successfully!"
echo "💡 Next step: Try the Docker build with ./scripts/debug-frontend-build.sh"