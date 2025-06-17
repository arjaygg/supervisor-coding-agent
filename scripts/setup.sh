#!/bin/bash

# Supervisor Coding Agent - Setup Script
# This script helps set up the Supervisor Coding Agent for local development

set -e

echo "🤖 Supervisor Coding Agent Setup"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in virtual environment
check_venv() {
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        echo -e "${YELLOW}⚠️  Warning: Not running in a virtual environment${NC}"
        echo "It's recommended to create and activate a virtual environment:"
        echo "  python3 -m venv venv"
        echo "  source venv/bin/activate"
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${GREEN}✅ Virtual environment detected: $VIRTUAL_ENV${NC}"
    fi
}

# Check Python version
check_python() {
    echo "Checking Python version..."
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is not installed${NC}"
        exit 1
    fi
    
    python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    required_version="3.11"
    
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
        echo -e "${GREEN}✅ Python $python_version (>= $required_version)${NC}"
    else
        echo -e "${RED}❌ Python $python_version is too old. Requires >= $required_version${NC}"
        exit 1
    fi
}

# Check for Claude CLI
check_claude_cli() {
    echo "Checking for Claude CLI..."
    if command -v claude &> /dev/null; then
        claude_version=$(claude --version 2>/dev/null || echo "unknown")
        echo -e "${GREEN}✅ Claude CLI found: $claude_version${NC}"
    else
        echo -e "${YELLOW}⚠️  Claude CLI not found${NC}"
        echo "Please install Claude CLI from: https://docs.anthropic.com/en/docs/claude-code"
        echo "After installation, make sure 'claude' is in your PATH"
        echo ""
        read -p "Continue setup without Claude CLI? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Install Python dependencies
install_dependencies() {
    echo "Installing Python dependencies..."
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        echo -e "${GREEN}✅ Dependencies installed${NC}"
    else
        echo -e "${RED}❌ requirements.txt not found${NC}"
        exit 1
    fi
}

# Setup environment file
setup_env() {
    echo "Setting up environment configuration..."
    if [ ! -f ".env" ]; then
        if [ -f ".env.sample" ]; then
            cp .env.sample .env
            echo -e "${GREEN}✅ Created .env from .env.sample${NC}"
            echo -e "${YELLOW}⚠️  Please edit .env file with your configuration${NC}"
        else
            echo -e "${RED}❌ .env.sample not found${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✅ .env file already exists${NC}"
    fi
}

# Check Docker installation
check_docker() {
    echo "Checking Docker installation..."
    if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
        docker_version=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
        compose_version=$(docker-compose --version | cut -d' ' -f3 | cut -d',' -f1)
        echo -e "${GREEN}✅ Docker $docker_version and Docker Compose $compose_version found${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Docker or Docker Compose not found${NC}"
        echo "For containerized setup, please install Docker and Docker Compose"
        return 1
    fi
}

# Run tests to verify setup
run_tests() {
    echo "Running tests to verify setup..."
    if python3 -m pytest supervisor_agent/tests/ -v --tb=short -x; then
        echo -e "${GREEN}✅ All tests passed!${NC}"
    else
        echo -e "${YELLOW}⚠️  Some tests failed. This might be expected if external dependencies aren't configured.${NC}"
    fi
}

# Main setup process
main() {
    echo "Starting setup process..."
    echo ""
    
    check_venv
    check_python
    check_claude_cli
    install_dependencies
    setup_env
    
    echo ""
    echo "🔧 Optional: Docker Setup"
    echo "========================"
    
    if check_docker; then
        echo ""
        read -p "Would you like to start the development environment with Docker? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Starting development environment..."
            docker-compose up -d
            echo ""
            echo "Waiting for services to start..."
            sleep 10
            
            # Check if services are running
            if curl -f http://localhost:8000/api/v1/healthz &>/dev/null; then
                echo -e "${GREEN}✅ API server is running at http://localhost:8000${NC}"
                echo -e "${GREEN}✅ API docs available at http://localhost:8000/docs${NC}"
            else
                echo -e "${YELLOW}⚠️  API server may still be starting up${NC}"
            fi
        fi
    fi
    
    echo ""
    echo "🧪 Testing Setup"
    echo "==============="
    
    read -p "Would you like to run tests to verify the setup? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        run_tests
    fi
    
    echo ""
    echo -e "${GREEN}🎉 Setup completed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Edit .env file with your API keys and configuration"
    echo "2. For Docker: run 'make docker-up' to start all services"
    echo "3. For manual setup: run 'make run' for API, 'make run-worker' for worker"
    echo "4. Visit http://localhost:8000/docs for API documentation"
    echo ""
    echo "Quick commands:"
    echo "  make help          # Show all available commands"
    echo "  make docker-up     # Start with Docker"
    echo "  make test          # Run tests"
    echo "  make health-check  # Check if everything is running"
}

# Run main function
main "$@"