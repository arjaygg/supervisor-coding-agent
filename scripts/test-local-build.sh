#!/bin/bash

# Local test script that replicates the promote-to-dev workflow

set -e  # Exit on any error

echo "🧪 Testing promote-to-dev workflow locally..."

# Get project root directory (one level up from scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "📂 Working in: $(pwd)"

# Simulate PR number
PR_NUMBER=${1:-999}
echo "Testing with PR number: $PR_NUMBER"

# Set environment variables (same as workflow)
export NODE_ENV=production
export VITE_API_URL=https://dev.dev-assist.example.com/api
export VITE_WS_URL=wss://dev.dev-assist.example.com/ws

echo "🏗️ Building API image..."
docker build -t dev-assist-api:dev-$PR_NUMBER .

echo "🏗️ Building Frontend image..."
cd frontend
docker build -f Dockerfile.prod -t dev-assist-frontend:dev-$PR_NUMBER \
  --build-arg VITE_API_URL=$VITE_API_URL \
  --build-arg VITE_WS_URL=$VITE_WS_URL .

cd ..

echo "💾 Saving images (simulating workflow)..."
docker save dev-assist-api:dev-$PR_NUMBER | gzip > /tmp/dev-api-image.tar.gz
docker save dev-assist-frontend:dev-$PR_NUMBER | gzip > /tmp/dev-frontend-image.tar.gz

echo "🔄 Testing image loading..."
docker load < /tmp/dev-api-image.tar.gz
docker load < /tmp/dev-frontend-image.tar.gz

echo "✅ All builds successful!"
echo "Images created:"
docker images | grep "dev-assist.*:dev-$PR_NUMBER"

echo "🧹 Cleanup..."
rm -f /tmp/dev-api-image.tar.gz /tmp/dev-frontend-image.tar.gz

echo "🎉 Local test completed successfully!"