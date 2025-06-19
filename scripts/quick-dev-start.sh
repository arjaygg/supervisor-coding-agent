#!/bin/bash

# Quick Development Setup Script for Supervisor Agent
# This script sets up the development environment with minimal configuration

set -e

echo "🚀 Setting up Supervisor Agent for development..."

# Check if we're in the right directory
if [ ! -f "supervisor_agent/api/main.py" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.template .env
    echo "✅ Created .env file with development defaults"
else
    echo "✅ .env file already exists"
fi

# Check if Python virtual environment exists
if [ ! -d "venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment and install dependencies
echo "📦 Installing Python dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo "🔧 Setting up database..."
# Use SQLite for quick development setup
export DATABASE_URL="sqlite:///./supervisor_agent.db"
python -c "
from supervisor_agent.db.database import engine
from supervisor_agent.db.models import Base
Base.metadata.create_all(bind=engine)
print('Database tables created')
"

echo "🎯 Starting services..."

echo ""
echo "🎉 Setup complete! You can now:"
echo ""
echo "1. Start the API server:"
echo "   source venv/bin/activate"
echo "   python supervisor_agent/api/main.py"
echo ""
echo "2. In another terminal, start the frontend:"
echo "   cd frontend"
echo "   npm install"
echo "   npm run dev"
echo ""
echo "3. Access the dashboard at: http://localhost:3000"
echo "   API docs at: http://localhost:8000/docs"
echo ""
echo "⚠️  Note: Running in mock mode - no real Claude CLI required"
echo "   Tasks will generate simulated responses for testing"
echo ""