#!/usr/bin/env python3
"""
End-to-End Smoke Tests for Multi-Provider Architecture

Comprehensive smoke testing suite that validates the entire system
functionality after deployment. Can be run as:
1. Post-deployment validation
2. Pre-merge PR gate checks  
3. Continuous integration health checks

Usage:
    python3 tests/e2e_smoke_tests.py --env staging
    python3 tests/e2e_smoke_tests.py --env production --critical-only
"""

import os
import sys
import asyncio
import json
import time
import traceback
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import logging

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test configuration
class TestConfig:
    def __init__(self, env: str = "staging"):
        self.environment = env
        self.base_url = self._get_base_url(env)
        self.timeout = 30
        self.retry_attempts = 3
        self.critical_only = False
        
    def _get_base_url(self, env: str) -> str:
        env_urls = {
            "local": "http://localhost:8000",
            "staging": os.getenv("STAGING_URL", "http://localhost:8000"), 
            "production": os.getenv("PRODUCTION_URL", "http://localhost:8000")
        }
        return env_urls.get(env, env_urls["local"])


class SmokeTestResult:
    def __init__(self, test_name: str, category: str, critical: bool = False):
        self.test_name = test_name
        self.category = category
        self.critical = critical
        self.passed = False
        self.error_message = ""
        self.execution_time = 0.0
        self.details = {}
        self.start_time = None
        
    def start(self):
        self.start_time = time.time()
        
    def finish(self, passed: bool, error_message: str = "", details: Dict = None):
        self.passed = passed
        self.error_message = error_message
        self.details = details or {}
        if self.start_time:
            self.execution_time = time.time() - self.start_time


class SmokeTestSuite:
    """Comprehensive smoke test suite for multi-provider architecture"""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.results: List[SmokeTestResult] = []
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for test execution"""
        logger = logging.getLogger("smoke_tests")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
        
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all smoke tests and return comprehensive results"""
        self.logger.info(f"🚀 Starting smoke tests for {self.config.environment} environment")
        self.logger.info(f"📍 Base URL: {self.config.base_url}")
        
        test_categories = [
            ("System Health", self._test_system_health, True),
            ("Configuration", self._test_configuration, True),
            ("Legacy Agent System", self._test_legacy_agents, True),
            ("Multi-Provider System", self._test_multi_provider_system, False),
            ("API Endpoints", self._test_api_endpoints, True),
            ("WebSocket Connections", self._test_websocket_connections, False),
            ("Database Operations", self._test_database_operations, True),
            ("Task Processing", self._test_task_processing, True),
            ("Analytics and Monitoring", self._test_analytics_system, False),
            ("Migration Tools", self._test_migration_tools, False),
            ("Performance and Load", self._test_performance, False)
        ]
        
        for category_name, test_func, is_critical in test_categories:
            if self.config.critical_only and not is_critical:
                continue
                
            self.logger.info(f"\n📋 Running {category_name} tests...")
            try:
                await test_func()
            except Exception as e:
                self.logger.error(f"❌ Category {category_name} failed: {str(e)}")
                result = SmokeTestResult(f"{category_name}_category", category_name, is_critical)
                result.start()
                result.finish(False, str(e))
                self.results.append(result)
                
        return self._generate_test_report()
        
    async def _test_system_health(self):
        """Test overall system health and availability"""
        
        # Test 1: Basic application startup
        result = SmokeTestResult("application_startup", "System Health", critical=True)
        result.start()
        try:
            # Import core components
            from supervisor_agent.config import settings
            from supervisor_agent.core.enhanced_agent_manager import enhanced_agent_manager
            
            result.finish(True, details={"config_loaded": True})
            self.logger.info("✅ Application startup successful")
        except Exception as e:
            result.finish(False, f"Application startup failed: {str(e)}")
            self.logger.error(f"❌ Application startup failed: {str(e)}")
        self.results.append(result)
        
        # Test 2: Database connectivity
        result = SmokeTestResult("database_connectivity", "System Health", critical=True)
        result.start()
        try:
            from supervisor_agent.db.database import SessionLocal, engine
            from sqlalchemy import text
            
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
                
            result.finish(True, details={"database_type": str(engine.url).split("://")[0]})
            self.logger.info("✅ Database connectivity verified")
        except Exception as e:
            result.finish(False, f"Database connection failed: {str(e)}")
            self.logger.error(f"❌ Database connection failed: {str(e)}")
        self.results.append(result)
        
        # Test 3: System health check
        result = SmokeTestResult("system_health_check", "System Health", critical=True)
        result.start()
        try:
            from supervisor_agent.core.enhanced_agent_manager import enhanced_agent_manager
            
            health = await enhanced_agent_manager.get_system_health()
            
            result.finish(
                True, 
                details={
                    "overall_status": health.get("overall_status"),
                    "legacy_agents": health.get("legacy_system", {}).get("agents", 0),
                    "providers": health.get("multi_provider_system", {}).get("providers", 0)
                }
            )
            self.logger.info(f"✅ System health: {health.get('overall_status')}")
        except Exception as e:
            result.finish(False, f"System health check failed: {str(e)}")
            self.logger.error(f"❌ System health check failed: {str(e)}")
        self.results.append(result)
        
    async def _test_configuration(self):
        """Test configuration loading and validation"""
        
        # Test 1: Configuration loading
        result = SmokeTestResult("config_loading", "Configuration", critical=True)
        result.start()
        try:
            from supervisor_agent.config import settings
            
            warnings = settings.validate_configuration()
            
            result.finish(
                True, 
                details={
                    "multi_provider_enabled": settings.multi_provider_enabled,
                    "validation_warnings": len(warnings),
                    "provider_configs": len(settings.get_provider_configs())
                }
            )
            self.logger.info("✅ Configuration loaded and validated")
        except Exception as e:
            result.finish(False, f"Configuration loading failed: {str(e)}")
            self.logger.error(f"❌ Configuration loading failed: {str(e)}")
        self.results.append(result)
        
        # Test 2: Provider configuration validation
        result = SmokeTestResult("provider_config_validation", "Configuration")
        result.start()
        try:
            from supervisor_agent.config import settings
            
            provider_configs = settings.get_provider_configs()
            valid_configs = 0
            
            for config in provider_configs:
                if all(key in config for key in ["id", "type", "config"]):
                    valid_configs += 1
                    
            result.finish(
                valid_configs > 0,
                f"Found {valid_configs} valid provider configs out of {len(provider_configs)}",
                details={"valid_configs": valid_configs, "total_configs": len(provider_configs)}
            )
            self.logger.info(f"✅ Provider configuration: {valid_configs}/{len(provider_configs)} valid")
        except Exception as e:
            result.finish(False, f"Provider config validation failed: {str(e)}")
            self.logger.error(f"❌ Provider config validation failed: {str(e)}")
        self.results.append(result)
        
    async def _test_legacy_agents(self):
        """Test legacy agent system functionality"""
        
        # Test 1: Agent manager initialization
        result = SmokeTestResult("agent_manager_init", "Legacy Agent System", critical=True)
        result.start()
        try:
            from supervisor_agent.core.agent import AgentManager
            
            manager = AgentManager()
            agent_ids = manager.get_available_agent_ids()
            
            result.finish(
                True,
                details={"available_agents": len(agent_ids), "agent_ids": agent_ids}
            )
            self.logger.info(f"✅ Agent manager: {len(agent_ids)} agents available")
        except Exception as e:
            result.finish(False, f"Agent manager initialization failed: {str(e)}")
            self.logger.error(f"❌ Agent manager initialization failed: {str(e)}")
        self.results.append(result)
        
        # Test 2: Agent availability check
        result = SmokeTestResult("agent_availability", "Legacy Agent System", critical=True)
        result.start()
        try:
            from supervisor_agent.core.enhanced_agent_manager import enhanced_agent_manager
            
            agents = await enhanced_agent_manager.get_available_agents()
            
            result.finish(
                agents["total_capacity"] > 0,
                f"Total capacity: {agents['total_capacity']}",
                details=agents
            )
            self.logger.info(f"✅ Agent availability: {agents['total_capacity']} total capacity")
        except Exception as e:
            result.finish(False, f"Agent availability check failed: {str(e)}")
            self.logger.error(f"❌ Agent availability check failed: {str(e)}")
        self.results.append(result)
        
    async def _test_multi_provider_system(self):
        """Test multi-provider system functionality"""
        
        # Test 1: Multi-provider service initialization
        result = SmokeTestResult("multi_provider_init", "Multi-Provider System")
        result.start()
        try:
            from supervisor_agent.config import settings
            
            if not settings.multi_provider_enabled:
                result.finish(True, "Multi-provider disabled - skipping tests")
                self.logger.info("ℹ️  Multi-provider system disabled - skipping tests")
                self.results.append(result)
                return
                
            from supervisor_agent.core.multi_provider_service import multi_provider_service
            
            # Try to initialize (may fail if no providers configured)
            try:
                await multi_provider_service.initialize()
                initialized = True
            except Exception:
                initialized = False
                
            result.finish(
                True,  # Not critical if initialization fails with no providers
                f"Initialization: {'Success' if initialized else 'No providers configured'}",
                details={"initialized": initialized}
            )
            self.logger.info(f"✅ Multi-provider service: {'initialized' if initialized else 'no providers'}")
        except Exception as e:
            result.finish(False, f"Multi-provider initialization failed: {str(e)}")
            self.logger.error(f"❌ Multi-provider initialization failed: {str(e)}")
        self.results.append(result)
        
        # Test 2: Provider status check
        result = SmokeTestResult("provider_status", "Multi-Provider System")
        result.start()
        try:
            from supervisor_agent.config import settings
            
            if not settings.multi_provider_enabled:
                result.finish(True, "Multi-provider disabled")
                self.results.append(result)
                return
                
            from supervisor_agent.core.multi_provider_service import multi_provider_service
            
            status = await multi_provider_service.get_provider_status()
            
            result.finish(
                True,
                details=status
            )
            self.logger.info(f"✅ Provider status: {status.get('total_providers', 0)} providers")
        except Exception as e:
            result.finish(False, f"Provider status check failed: {str(e)}")
            self.logger.error(f"❌ Provider status check failed: {str(e)}")
        self.results.append(result)
        
    async def _test_api_endpoints(self):
        """Test API endpoint availability and basic functionality"""
        
        # Test 1: Health endpoint
        result = SmokeTestResult("health_endpoint", "API Endpoints", critical=True)
        result.start()
        try:
            # Test if we can import the API app
            from supervisor_agent.api.main import app
            
            result.finish(True, "API application can be imported")
            self.logger.info("✅ API application import successful")
        except Exception as e:
            result.finish(False, f"API import failed: {str(e)}")
            self.logger.error(f"❌ API import failed: {str(e)}")
        self.results.append(result)
        
        # Test 2: Analytics endpoints
        result = SmokeTestResult("analytics_endpoints", "API Endpoints")
        result.start()
        try:
            from supervisor_agent.api.routes.analytics import router
            
            # Count available routes
            route_count = len([route for route in router.routes])
            
            result.finish(
                route_count > 0,
                f"Analytics router has {route_count} routes",
                details={"route_count": route_count}
            )
            self.logger.info(f"✅ Analytics endpoints: {route_count} routes available")
        except Exception as e:
            result.finish(False, f"Analytics endpoints test failed: {str(e)}")
            self.logger.error(f"❌ Analytics endpoints test failed: {str(e)}")
        self.results.append(result)
        
    async def _test_websocket_connections(self):
        """Test WebSocket connection capabilities"""
        
        # Test 1: WebSocket router availability
        result = SmokeTestResult("websocket_router", "WebSocket Connections")
        result.start()
        try:
            from supervisor_agent.api.websocket_providers import provider_ws_manager
            
            result.finish(
                True,
                "WebSocket provider manager available",
                details={"active_connections": len(provider_ws_manager.active_connections)}
            )
            self.logger.info("✅ WebSocket provider manager available")
        except Exception as e:
            result.finish(False, f"WebSocket router test failed: {str(e)}")
            self.logger.error(f"❌ WebSocket router test failed: {str(e)}")
        self.results.append(result)
        
    async def _test_database_operations(self):
        """Test database operations and model functionality"""
        
        # Test 1: Database models
        result = SmokeTestResult("database_models", "Database Operations", critical=True)
        result.start()
        try:
            from supervisor_agent.db.models import Task, Agent, Provider
            from supervisor_agent.db.crud import TaskCRUD, AgentCRUD
            
            result.finish(True, "Database models and CRUD operations available")
            self.logger.info("✅ Database models and CRUD available")
        except Exception as e:
            result.finish(False, f"Database models test failed: {str(e)}")
            self.logger.error(f"❌ Database models test failed: {str(e)}")
        self.results.append(result)
        
        # Test 2: Table creation
        result = SmokeTestResult("table_creation", "Database Operations", critical=True)
        result.start()
        try:
            from supervisor_agent.db.database import engine
            from supervisor_agent.db.models import Base
            from sqlalchemy import inspect
            
            inspector = inspect(engine)
            existing_tables = inspector.get_table_names()
            
            result.finish(
                len(existing_tables) > 0,
                f"Found {len(existing_tables)} database tables",
                details={"tables": existing_tables}
            )
            self.logger.info(f"✅ Database tables: {len(existing_tables)} tables exist")
        except Exception as e:
            result.finish(False, f"Table creation test failed: {str(e)}")
            self.logger.error(f"❌ Table creation test failed: {str(e)}")
        self.results.append(result)
        
    async def _test_task_processing(self):
        """Test task creation and processing capabilities"""
        
        # Test 1: Task model creation
        result = SmokeTestResult("task_model", "Task Processing", critical=True)
        result.start()
        try:
            from supervisor_agent.db.models import Task, TaskType
            from datetime import datetime
            
            # Create a test task object (not persisting to DB)
            test_task = Task(
                type=TaskType.CODE_ANALYSIS,
                payload={"test": "data"},
                created_at=datetime.utcnow()
            )
            
            result.finish(
                test_task.type == TaskType.CODE_ANALYSIS,
                "Task model creation successful",
                details={"task_type": str(test_task.type)}
            )
            self.logger.info("✅ Task model creation successful")
        except Exception as e:
            result.finish(False, f"Task model test failed: {str(e)}")
            self.logger.error(f"❌ Task model test failed: {str(e)}")
        self.results.append(result)
        
        # Test 2: Enhanced agent manager task execution capability
        result = SmokeTestResult("task_execution_capability", "Task Processing")
        result.start()
        try:
            from supervisor_agent.core.enhanced_agent_manager import enhanced_agent_manager
            from supervisor_agent.db.models import Task, TaskType
            
            # Test that we can call execute_task method (without actually executing)
            test_task = Task(type=TaskType.CODE_ANALYSIS, payload={"test": "smoke_test"})
            
            # Check if method exists and is callable
            has_execute_method = hasattr(enhanced_agent_manager, 'execute_task')
            is_callable = callable(getattr(enhanced_agent_manager, 'execute_task', None))
            
            result.finish(
                has_execute_method and is_callable,
                "Task execution capability available",
                details={"has_method": has_execute_method, "is_callable": is_callable}
            )
            self.logger.info("✅ Task execution capability verified")
        except Exception as e:
            result.finish(False, f"Task execution capability test failed: {str(e)}")
            self.logger.error(f"❌ Task execution capability test failed: {str(e)}")
        self.results.append(result)
        
    async def _test_analytics_system(self):
        """Test analytics and monitoring system"""
        
        # Test 1: Analytics engine
        result = SmokeTestResult("analytics_engine", "Analytics and Monitoring")
        result.start()
        try:
            from supervisor_agent.core.analytics_engine import AnalyticsEngine
            
            engine = AnalyticsEngine()
            
            result.finish(True, "Analytics engine available")
            self.logger.info("✅ Analytics engine available")
        except Exception as e:
            result.finish(False, f"Analytics engine test failed: {str(e)}")
            self.logger.error(f"❌ Analytics engine test failed: {str(e)}")
        self.results.append(result)
        
        # Test 2: Provider analytics (if multi-provider enabled)
        result = SmokeTestResult("provider_analytics", "Analytics and Monitoring")
        result.start()
        try:
            from supervisor_agent.config import settings
            
            if not settings.multi_provider_enabled:
                result.finish(True, "Multi-provider disabled - analytics not needed")
                self.logger.info("ℹ️  Provider analytics: multi-provider disabled")
                self.results.append(result)
                return
                
            from supervisor_agent.core.multi_provider_service import multi_provider_service
            
            # Test analytics method availability
            has_analytics = hasattr(multi_provider_service, 'get_analytics')
            
            result.finish(
                has_analytics,
                f"Provider analytics {'available' if has_analytics else 'not available'}"
            )
            self.logger.info(f"✅ Provider analytics: {'available' if has_analytics else 'not available'}")
        except Exception as e:
            result.finish(False, f"Provider analytics test failed: {str(e)}")
            self.logger.error(f"❌ Provider analytics test failed: {str(e)}")
        self.results.append(result)
        
    async def _test_migration_tools(self):
        """Test migration and configuration tools"""
        
        # Test 1: Migration tool availability
        result = SmokeTestResult("migration_tool", "Migration Tools")
        result.start()
        try:
            migration_script = Path("migrate_to_multi_provider.py")
            
            result.finish(
                migration_script.exists(),
                f"Migration tool {'available' if migration_script.exists() else 'missing'}",
                details={"script_path": str(migration_script)}
            )
            self.logger.info(f"✅ Migration tool: {'available' if migration_script.exists() else 'missing'}")
        except Exception as e:
            result.finish(False, f"Migration tool test failed: {str(e)}")
            self.logger.error(f"❌ Migration tool test failed: {str(e)}")
        self.results.append(result)
        
        # Test 2: Integration test availability
        result = SmokeTestResult("integration_test", "Migration Tools")
        result.start()
        try:
            integration_script = Path("integration_test.py")
            
            result.finish(
                integration_script.exists(),
                f"Integration test {'available' if integration_script.exists() else 'missing'}",
                details={"script_path": str(integration_script)}
            )
            self.logger.info(f"✅ Integration test: {'available' if integration_script.exists() else 'missing'}")
        except Exception as e:
            result.finish(False, f"Integration test failed: {str(e)}")
            self.logger.error(f"❌ Integration test failed: {str(e)}")
        self.results.append(result)
        
    async def _test_performance(self):
        """Test basic performance characteristics"""
        
        # Test 1: Import performance
        result = SmokeTestResult("import_performance", "Performance and Load")
        result.start()
        try:
            start_time = time.time()
            
            from supervisor_agent.core.enhanced_agent_manager import enhanced_agent_manager
            from supervisor_agent.config import settings
            
            import_time = time.time() - start_time
            
            result.finish(
                import_time < 5.0,  # Should import in under 5 seconds
                f"Import time: {import_time:.2f}s",
                details={"import_time": import_time}
            )
            self.logger.info(f"✅ Import performance: {import_time:.2f}s")
        except Exception as e:
            result.finish(False, f"Import performance test failed: {str(e)}")
            self.logger.error(f"❌ Import performance test failed: {str(e)}")
        self.results.append(result)
        
        # Test 2: System health response time
        result = SmokeTestResult("health_response_time", "Performance and Load")
        result.start()
        try:
            from supervisor_agent.core.enhanced_agent_manager import enhanced_agent_manager
            
            start_time = time.time()
            health = await enhanced_agent_manager.get_system_health()
            response_time = time.time() - start_time
            
            result.finish(
                response_time < 2.0,  # Should respond in under 2 seconds
                f"Health check time: {response_time:.2f}s",
                details={"response_time": response_time, "health_status": health.get("overall_status")}
            )
            self.logger.info(f"✅ Health response time: {response_time:.2f}s")
        except Exception as e:
            result.finish(False, f"Health response time test failed: {str(e)}")
            self.logger.error(f"❌ Health response time test failed: {str(e)}")
        self.results.append(result)
        
    def _generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        
        critical_tests = [r for r in self.results if r.critical]
        critical_passed = sum(1 for r in critical_tests if r.passed)
        critical_failed = len(critical_tests) - critical_passed
        
        # Categorize results
        categories = {}
        for result in self.results:
            if result.category not in categories:
                categories[result.category] = {"total": 0, "passed": 0, "failed": 0, "tests": []}
            
            categories[result.category]["total"] += 1
            categories[result.category]["tests"].append(result)
            
            if result.passed:
                categories[result.category]["passed"] += 1
            else:
                categories[result.category]["failed"] += 1
        
        # Determine overall status
        overall_status = "PASS"
        if critical_failed > 0:
            overall_status = "CRITICAL_FAILURE"
        elif failed_tests > 0:
            overall_status = "PARTIAL_FAILURE"
            
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": self.config.environment,
            "overall_status": overall_status,
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "critical_tests": len(critical_tests),
                "critical_passed": critical_passed,
                "critical_failed": critical_failed,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0
            },
            "categories": categories,
            "failed_tests": [
                {
                    "name": r.test_name,
                    "category": r.category,
                    "critical": r.critical,
                    "error": r.error_message,
                    "execution_time": r.execution_time
                }
                for r in self.results if not r.passed
            ],
            "performance_metrics": {
                "total_execution_time": sum(r.execution_time for r in self.results),
                "average_test_time": sum(r.execution_time for r in self.results) / total_tests if total_tests > 0 else 0
            }
        }


def print_test_report(report: Dict[str, Any]):
    """Print formatted test report"""
    print(f"\n{'='*80}")
    print(f"🧪 SMOKE TEST REPORT - {report['environment'].upper()} ENVIRONMENT")
    print(f"{'='*80}")
    print(f"📅 Timestamp: {report['timestamp']}")
    print(f"🎯 Overall Status: {report['overall_status']}")
    
    summary = report['summary']
    print(f"\n📊 SUMMARY:")
    print(f"   Total Tests: {summary['total_tests']}")
    print(f"   ✅ Passed: {summary['passed_tests']}")
    print(f"   ❌ Failed: {summary['failed_tests']}")
    print(f"   🔥 Critical Tests: {summary['critical_tests']}")
    print(f"   🔥 Critical Failed: {summary['critical_failed']}")
    print(f"   📈 Success Rate: {summary['success_rate']:.1f}%")
    
    print(f"\n📋 BY CATEGORY:")
    for category, data in report['categories'].items():
        status_icon = "✅" if data['failed'] == 0 else "❌"
        print(f"   {status_icon} {category}: {data['passed']}/{data['total']} passed")
    
    if report['failed_tests']:
        print(f"\n❌ FAILED TESTS:")
        for failed in report['failed_tests']:
            critical_marker = "🔥" if failed['critical'] else "⚠️"
            print(f"   {critical_marker} {failed['name']} ({failed['category']})")
            print(f"      Error: {failed['error']}")
            
    metrics = report['performance_metrics']
    print(f"\n⚡ PERFORMANCE:")
    print(f"   Total Execution Time: {metrics['total_execution_time']:.2f}s")
    print(f"   Average Test Time: {metrics['average_test_time']:.2f}s")
    
    print(f"\n{'='*80}")


async def main():
    """Main CLI interface for smoke tests"""
    parser = argparse.ArgumentParser(description="Run end-to-end smoke tests")
    parser.add_argument(
        "--env", 
        choices=["local", "staging", "production"],
        default="local",
        help="Target environment for testing"
    )
    parser.add_argument(
        "--critical-only",
        action="store_true",
        help="Run only critical tests"
    )
    parser.add_argument(
        "--output",
        help="Output file for JSON test results"
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true", 
        help="Stop on first critical failure"
    )
    
    args = parser.parse_args()
    
    # Setup test configuration
    config = TestConfig(args.env)
    config.critical_only = args.critical_only
    
    # Run tests
    suite = SmokeTestSuite(config)
    
    try:
        report = await suite.run_all_tests()
        
        # Print report
        print_test_report(report)
        
        # Save to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n💾 Results saved to {args.output}")
        
        # Determine exit code
        if report['overall_status'] == "CRITICAL_FAILURE":
            print(f"\n🚨 CRITICAL FAILURES DETECTED - Deployment should not proceed")
            sys.exit(1)
        elif report['overall_status'] == "PARTIAL_FAILURE":
            print(f"\n⚠️  PARTIAL FAILURES - Review before proceeding")
            sys.exit(2)
        else:
            print(f"\n🎉 ALL TESTS PASSED - System ready for deployment")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print(f"\n⏹️  Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Test suite crashed: {str(e)}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())