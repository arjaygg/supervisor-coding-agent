#!/bin/bash

# Supervisor Coding Agent - Development Setup Script
# Sets up a complete development environment

set -e

echo "🔧 Supervisor Coding Agent - Development Setup"
echo "=============================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
DB_NAME="supervisor_agent"
DB_USER="supervisor"
DB_PASS="supervisor_pass"
REDIS_URL="redis://localhost:6379/0"

# Check prerequisites
check_prerequisites() {
    echo -e "${BLUE}Checking prerequisites...${NC}"
    
    # Check Python
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
        echo -e "${RED}❌ Python 3.11+ required${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Python 3.11+${NC}"
    
    # Check Docker
    if ! command -v docker &>/dev/null || ! command -v docker-compose &>/dev/null; then
        echo -e "${RED}❌ Docker and Docker Compose required${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker and Docker Compose${NC}"
    
    # Check if in virtual environment
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        echo -e "${YELLOW}⚠️  Not in virtual environment${NC}"
        echo "Creating virtual environment..."
        python3 -m venv venv
        echo "Please activate it with: source venv/bin/activate"
        echo "Then run this script again."
        exit 1
    fi
    echo -e "${GREEN}✅ Virtual environment active${NC}"
}

# Install dependencies
install_dependencies() {
    echo -e "${BLUE}Installing Python dependencies...${NC}"
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Install development dependencies
    echo "Installing development tools..."
    pip install black isort flake8 mypy pytest-cov
    
    echo -e "${GREEN}✅ Dependencies installed${NC}"
}

# Setup environment
setup_environment() {
    echo -e "${BLUE}Setting up environment configuration...${NC}"
    
    if [[ ! -f ".env" ]]; then
        cp .env.sample .env
        echo -e "${GREEN}✅ Created .env from template${NC}"
    else
        echo -e "${GREEN}✅ .env already exists${NC}"
    fi
    
    # Update .env with development settings
    cat >> .env << EOF

# Development overrides
APP_DEBUG=true
LOG_LEVEL=DEBUG
CLAUDE_CLI_PATH=claude

# Development database URLs
DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}
REDIS_URL=${REDIS_URL}
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}
EOF
    
    echo -e "${GREEN}✅ Environment configured for development${NC}"
}

# Setup databases
setup_databases() {
    echo -e "${BLUE}Setting up databases...${NC}"
    
    # Start database services
    echo "Starting PostgreSQL and Redis..."
    docker-compose up -d postgres redis
    
    # Wait for databases
    echo "Waiting for databases to be ready..."
    for i in {1..30}; do
        if docker-compose exec -T postgres pg_isready -U ${DB_USER} >/dev/null 2>&1; then
            break
        fi
        echo -n "."
        sleep 1
    done
    echo ""
    
    if docker-compose exec -T postgres pg_isready -U ${DB_USER} >/dev/null 2>&1; then
        echo -e "${GREEN}✅ PostgreSQL ready${NC}"
    else
        echo -e "${RED}❌ PostgreSQL failed to start${NC}"
        exit 1
    fi
    
    # Check Redis
    if docker-compose exec -T redis redis-cli ping >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Redis ready${NC}"
    else
        echo -e "${RED}❌ Redis failed to start${NC}"
        exit 1
    fi
    
    # Initialize database
    echo "Initializing database schema..."
    export DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"
    
    # Run Alembic migrations
    if alembic upgrade head; then
        echo -e "${GREEN}✅ Database schema initialized${NC}"
    else
        echo -e "${YELLOW}⚠️  Database migration failed, but continuing...${NC}"
    fi
}

# Setup pre-commit hooks
setup_git_hooks() {
    echo -e "${BLUE}Setting up Git hooks...${NC}"
    
    # Create pre-commit hook
    mkdir -p .git/hooks
    cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Pre-commit hook for code quality

echo "Running pre-commit checks..."

# Run linting
echo "Checking code style with black..."
if ! black --check supervisor_agent/; then
    echo "❌ Code style issues found. Run: make format"
    exit 1
fi

# Run imports
echo "Checking import order..."
if ! isort --check-only supervisor_agent/; then
    echo "❌ Import order issues found. Run: make format"
    exit 1
fi

# Run quick tests
echo "Running quick tests..."
if ! pytest supervisor_agent/tests/ -x --tb=short -q; then
    echo "❌ Tests failed"
    exit 1
fi

echo "✅ Pre-commit checks passed"
EOF
    
    chmod +x .git/hooks/pre-commit
    echo -e "${GREEN}✅ Git hooks configured${NC}"
}

# Run tests
run_tests() {
    echo -e "${BLUE}Running tests to verify setup...${NC}"
    
    # Set test environment variables
    export DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"
    export REDIS_URL="${REDIS_URL}"
    
    if python -m pytest supervisor_agent/tests/ -v --tb=short; then
        echo -e "${GREEN}✅ All tests passed!${NC}"
    else
        echo -e "${YELLOW}⚠️  Some tests failed${NC}"
    fi
}

# Create sample data
create_sample_data() {
    echo -e "${BLUE}Creating sample data...${NC}"
    
    python3 << 'EOF'
import sys
import os
sys.path.append(os.getcwd())

from supervisor_agent.db.database import SessionLocal
from supervisor_agent.db import models
from supervisor_agent.db.crud import AgentCRUD
from supervisor_agent.api.schemas import AgentCreate
from datetime import datetime, timedelta

try:
    db = SessionLocal()
    agent_crud = AgentCRUD(db)
    
    # Create sample agents
    sample_agents = [
        {
            "id": "claude-agent-dev-1",
            "api_key": "sk-ant-dev-key-1",
            "quota_limit": 1000,
            "quota_reset_at": datetime.utcnow() + timedelta(hours=24)
        },
        {
            "id": "claude-agent-dev-2", 
            "api_key": "sk-ant-dev-key-2",
            "quota_limit": 1000,
            "quota_reset_at": datetime.utcnow() + timedelta(hours=24)
        }
    ]
    
    for agent_data in sample_agents:
        try:
            agent = AgentCreate(**agent_data)
            existing = agent_crud.get_agent(agent_data["id"])
            if not existing:
                agent_crud.create_agent(agent)
                print(f"✅ Created sample agent: {agent_data['id']}")
            else:
                print(f"✅ Agent already exists: {agent_data['id']}")
        except Exception as e:
            print(f"⚠️  Could not create agent {agent_data['id']}: {e}")
    
    db.close()
    print("✅ Sample data setup completed")
    
except Exception as e:
    print(f"❌ Failed to create sample data: {e}")
EOF
}

# Main setup function
main() {
    echo "Starting development environment setup..."
    echo ""
    
    check_prerequisites
    install_dependencies
    setup_environment
    setup_databases
    setup_git_hooks
    
    echo ""
    echo -e "${BLUE}Optional: Sample Data Setup${NC}"
    read -p "Would you like to create sample data for development? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        create_sample_data
    fi
    
    echo ""
    echo -e "${BLUE}Testing Setup${NC}"
    read -p "Would you like to run tests to verify the setup? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        run_tests
    fi
    
    echo ""
    echo -e "${GREEN}🎉 Development environment setup complete!${NC}"
    echo ""
    echo "Your development environment is ready. Here's what you can do:"
    echo ""
    echo -e "${BLUE}Start developing:${NC}"
    echo "  make run           # Start API server"
    echo "  make run-worker    # Start Celery worker (in another terminal)"
    echo "  make run-beat      # Start Celery scheduler (in another terminal)"
    echo ""
    echo -e "${BLUE}Or use Docker:${NC}"
    echo "  make docker-up     # Start all services"
    echo "  make docker-logs   # View logs"
    echo ""
    echo -e "${BLUE}Development commands:${NC}"
    echo "  make test          # Run tests with coverage"
    echo "  make lint          # Check code quality"
    echo "  make format        # Format code"
    echo "  make help          # Show all commands"
    echo ""
    echo -e "${BLUE}Access points:${NC}"
    echo "  API: http://localhost:8000"
    echo "  Docs: http://localhost:8000/docs"
    echo "  Health: http://localhost:8000/api/v1/healthz"
    echo ""
    echo -e "${YELLOW}📝 Next steps:${NC}"
    echo "1. Edit .env with your actual Claude API keys"
    echo "2. Install Claude CLI if you haven't already"
    echo "3. Start coding! 🚀"
}

# Run main function
main "$@"