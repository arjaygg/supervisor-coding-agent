#!/usr/bin/env python3
"""
Development Environment Validation

Validates the codebase structure, imports, and key components without requiring
the full application environment. Perfect for development environment testing
before deployment.

Usage:
    python3 tests/dev_environment_validation.py
    python3 tests/dev_environment_validation.py --verbose
"""

import sys
import os
import json
import ast
import importlib.util
from pathlib import Path
from typing import Dict, List, Any, Tuple
import argparse

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class DevEnvironmentValidator:
    """Validates development environment and codebase structure"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.project_root = Path(__file__).parent.parent
        self.results = []
        
    def validate_all(self) -> Dict[str, Any]:
        """Run all development environment validations"""
        print("🔍 Validating Development Environment...")
        print(f"📁 Project Root: {self.project_root}")
        
        validations = [
            ("Code Structure", self._validate_code_structure),
            ("File Imports", self._validate_file_imports),
            ("Configuration Files", self._validate_configuration),
            ("Test Infrastructure", self._validate_test_infrastructure),
            ("API Structure", self._validate_api_structure),
            ("Database Models", self._validate_database_models),
            ("Multi-Provider Components", self._validate_multi_provider),
            ("Frontend Components", self._validate_frontend),
            ("Documentation", self._validate_documentation),
            ("Repository Structure", self._validate_repository)
        ]
        
        for validation_name, validation_func in validations:
            print(f"\n📋 Validating {validation_name}...")
            try:
                validation_func()
                print(f"✅ {validation_name} validation passed")
            except Exception as e:
                print(f"❌ {validation_name} validation failed: {str(e)}")
                self.results.append({
                    "validation": validation_name,
                    "status": "failed",
                    "error": str(e)
                })
        
        return self._generate_report()
    
    def _validate_code_structure(self):
        """Validate core code structure and organization"""
        required_dirs = [
            "supervisor_agent",
            "supervisor_agent/core",
            "supervisor_agent/api",
            "supervisor_agent/db",
            "supervisor_agent/providers",
            "supervisor_agent/tests",
            "frontend",
            "frontend/src",
            ".github/workflows"
        ]
        
        missing_dirs = []
        for required_dir in required_dirs:
            dir_path = self.project_root / required_dir
            if not dir_path.exists():
                missing_dirs.append(required_dir)
        
        if missing_dirs:
            raise Exception(f"Missing required directories: {missing_dirs}")
        
        self.results.append({
            "validation": "Code Structure",
            "status": "passed",
            "details": {"directories_validated": len(required_dirs)}
        })
    
    def _validate_file_imports(self):
        """Validate that Python files have correct syntax and structure"""
        python_files = list(self.project_root.rglob("*.py"))
        
        # Filter out problematic files
        python_files = [f for f in python_files if not any(exclude in str(f) for exclude in [
            "__pycache__", ".git", "venv", "env", "node_modules"
        ])]
        
        syntax_errors = []
        import_errors = []
        
        for py_file in python_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check syntax
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    syntax_errors.append(f"{py_file}: {str(e)}")
                
                # Check for obvious import issues (basic validation)
                lines = content.split('\n')
                for line_num, line in enumerate(lines, 1):
                    line = line.strip()
                    if line.startswith('from') or line.startswith('import'):
                        # Basic import validation
                        if 'from ..' in line and not any(parent in str(py_file) for parent in ['supervisor_agent']):
                            import_errors.append(f"{py_file}:{line_num} - Relative import outside package")
                            
            except Exception as e:
                if self.verbose:
                    print(f"⚠️  Could not validate {py_file}: {str(e)}")
        
        if syntax_errors:
            raise Exception(f"Syntax errors found: {syntax_errors[:3]}...")  # Show first 3
        
        self.results.append({
            "validation": "File Imports",
            "status": "passed",
            "details": {
                "files_validated": len(python_files),
                "syntax_errors": len(syntax_errors),
                "import_warnings": len(import_errors)
            }
        })
    
    def _validate_configuration(self):
        """Validate configuration files and structure"""
        config_files = [
            "supervisor_agent/config.py",
            ".github/workflows/pr-merge-gate.yml",
            "requirements.txt",
            "migrate_to_multi_provider.py",
            "integration_test.py"
        ]
        
        missing_files = []
        for config_file in config_files:
            file_path = self.project_root / config_file
            if not file_path.exists():
                missing_files.append(config_file)
        
        if missing_files:
            raise Exception(f"Missing configuration files: {missing_files}")
        
        # Validate config.py structure
        config_path = self.project_root / "supervisor_agent/config.py"
        with open(config_path, 'r') as f:
            config_content = f.read()
        
        required_config_elements = [
            "multi_provider_enabled",
            "providers_config",
            "default_load_balancing_strategy",
            "provider_health_check_interval"
        ]
        
        missing_config = []
        for element in required_config_elements:
            if element not in config_content:
                missing_config.append(element)
        
        if missing_config:
            raise Exception(f"Missing configuration elements: {missing_config}")
        
        self.results.append({
            "validation": "Configuration Files",
            "status": "passed",
            "details": {"config_files_validated": len(config_files)}
        })
    
    def _validate_test_infrastructure(self):
        """Validate testing infrastructure"""
        test_files = [
            "tests/e2e_smoke_tests.py",
            "tests/dev_environment_validation.py",
            "scripts/post_deployment_validation.py",
            "scripts/cleanup_merged_branches.py"
        ]
        
        missing_test_files = []
        for test_file in test_files:
            file_path = self.project_root / test_file
            if not file_path.exists():
                missing_test_files.append(test_file)
        
        if missing_test_files:
            raise Exception(f"Missing test files: {missing_test_files}")
        
        # Check test directories
        test_dirs = [
            "supervisor_agent/tests",
            "tests",
            "scripts"
        ]
        
        for test_dir in test_dirs:
            dir_path = self.project_root / test_dir
            if not dir_path.exists():
                raise Exception(f"Missing test directory: {test_dir}")
        
        # Count test files in supervisor_agent/tests
        supervisor_tests = list((self.project_root / "supervisor_agent/tests").glob("test_*.py"))
        
        self.results.append({
            "validation": "Test Infrastructure",
            "status": "passed",
            "details": {
                "test_files": len(test_files),
                "supervisor_tests": len(supervisor_tests)
            }
        })
    
    def _validate_api_structure(self):
        """Validate API structure and key components"""
        api_files = [
            "supervisor_agent/api/main.py",
            "supervisor_agent/api/routes/analytics.py",
            "supervisor_agent/api/routes/providers.py",
            "supervisor_agent/api/websocket_providers.py"
        ]
        
        missing_api_files = []
        for api_file in api_files:
            file_path = self.project_root / api_file
            if not file_path.exists():
                missing_api_files.append(api_file)
        
        if missing_api_files:
            raise Exception(f"Missing API files: {missing_api_files}")
        
        # Validate main.py has required imports
        main_py = self.project_root / "supervisor_agent/api/main.py"
        with open(main_py, 'r') as f:
            main_content = f.read()
        
        required_imports = [
            "FastAPI",
            "websocket_providers",
            "providers_router"
        ]
        
        missing_imports = []
        for import_item in required_imports:
            if import_item not in main_content:
                missing_imports.append(import_item)
        
        if missing_imports:
            raise Exception(f"Missing imports in main.py: {missing_imports}")
        
        self.results.append({
            "validation": "API Structure",
            "status": "passed",
            "details": {"api_files_validated": len(api_files)}
        })
    
    def _validate_database_models(self):
        """Validate database model structure"""
        db_files = [
            "supervisor_agent/db/models.py",
            "supervisor_agent/db/crud.py",
            "supervisor_agent/db/database.py"
        ]
        
        missing_db_files = []
        for db_file in db_files:
            file_path = self.project_root / db_file
            if not file_path.exists():
                missing_db_files.append(db_file)
        
        if missing_db_files:
            raise Exception(f"Missing database files: {missing_db_files}")
        
        # Validate models.py has required models
        models_py = self.project_root / "supervisor_agent/db/models.py"
        with open(models_py, 'r') as f:
            models_content = f.read()
        
        required_models = [
            "class Task",
            "class Agent", 
            "class Provider",
            "class ProviderUsage"
        ]
        
        missing_models = []
        for model in required_models:
            if model not in models_content:
                missing_models.append(model)
        
        if missing_models:
            raise Exception(f"Missing database models: {missing_models}")
        
        self.results.append({
            "validation": "Database Models",
            "status": "passed",
            "details": {"db_files_validated": len(db_files)}
        })
    
    def _validate_multi_provider(self):
        """Validate multi-provider system components"""
        provider_files = [
            "supervisor_agent/core/enhanced_agent_manager.py",
            "supervisor_agent/core/multi_provider_service.py",
            "supervisor_agent/core/provider_coordinator.py",
            "supervisor_agent/core/multi_provider_task_processor.py",
            "supervisor_agent/providers/base_provider.py",
            "supervisor_agent/providers/claude_cli_provider.py",
            "supervisor_agent/providers/local_mock_provider.py"
        ]
        
        missing_provider_files = []
        for provider_file in provider_files:
            file_path = self.project_root / provider_file
            if not file_path.exists():
                missing_provider_files.append(provider_file)
        
        if missing_provider_files:
            raise Exception(f"Missing provider files: {missing_provider_files}")
        
        # Validate base_provider.py has the abstract interface
        base_provider = self.project_root / "supervisor_agent/providers/base_provider.py"
        with open(base_provider, 'r') as f:
            base_content = f.read()
        
        required_base_elements = [
            "class AIProvider",
            "ABC",
            "abstractmethod",
            "execute_task",
            "get_capabilities"
        ]
        
        missing_base_elements = []
        for element in required_base_elements:
            if element not in base_content:
                missing_base_elements.append(element)
        
        if missing_base_elements:
            raise Exception(f"Missing base provider elements: {missing_base_elements}")
        
        self.results.append({
            "validation": "Multi-Provider Components",
            "status": "passed",
            "details": {"provider_files_validated": len(provider_files)}
        })
    
    def _validate_frontend(self):
        """Validate frontend structure"""
        frontend_files = [
            "frontend/src/routes/analytics/+page.svelte",
            "frontend/src/lib/components/Chart.svelte",
            "frontend/package.json"
        ]
        
        missing_frontend_files = []
        for frontend_file in frontend_files:
            file_path = self.project_root / frontend_file
            if not file_path.exists():
                missing_frontend_files.append(frontend_file)
        
        if missing_frontend_files:
            raise Exception(f"Missing frontend files: {missing_frontend_files}")
        
        # Check analytics page has multi-provider section
        analytics_page = self.project_root / "frontend/src/routes/analytics/+page.svelte"
        with open(analytics_page, 'r') as f:
            analytics_content = f.read()
        
        required_analytics_elements = [
            "Multi-Provider Analytics",
            "providerDashboard",
            "providerPerformance",
            "multiProviderEnabled"
        ]
        
        missing_analytics_elements = []
        for element in required_analytics_elements:
            if element not in analytics_content:
                missing_analytics_elements.append(element)
        
        if missing_analytics_elements:
            raise Exception(f"Missing analytics elements: {missing_analytics_elements}")
        
        self.results.append({
            "validation": "Frontend Components",
            "status": "passed",
            "details": {"frontend_files_validated": len(frontend_files)}
        })
    
    def _validate_documentation(self):
        """Validate documentation and plans"""
        doc_files = [
            "plans/multi-provider-architecture.md",
            "README.md"
        ]
        
        existing_docs = []
        for doc_file in doc_files:
            file_path = self.project_root / doc_file
            if file_path.exists():
                existing_docs.append(doc_file)
        
        # Check multi-provider plan has completion status
        if "plans/multi-provider-architecture.md" in existing_docs:
            plan_file = self.project_root / "plans/multi-provider-architecture.md"
            with open(plan_file, 'r') as f:
                plan_content = f.read()
            
            if "PROJECT STATUS: COMPLETE" not in plan_content:
                raise Exception("Multi-provider architecture plan not marked as complete")
        
        self.results.append({
            "validation": "Documentation",
            "status": "passed",
            "details": {"documentation_files": len(existing_docs)}
        })
    
    def _validate_repository(self):
        """Validate repository structure and git state"""
        # Check for .github workflows
        workflows_dir = self.project_root / ".github/workflows"
        if not workflows_dir.exists():
            raise Exception("Missing .github/workflows directory")
        
        workflow_files = list(workflows_dir.glob("*.yml"))
        if not workflow_files:
            raise Exception("No workflow files found")
        
        # Check for required workflow
        pr_gate_workflow = workflows_dir / "pr-merge-gate.yml"
        if not pr_gate_workflow.exists():
            raise Exception("Missing PR merge gate workflow")
        
        # Check migration and testing tools
        required_tools = [
            "migrate_to_multi_provider.py",
            "integration_test.py",
            "tests/e2e_smoke_tests.py",
            "scripts/cleanup_merged_branches.py"
        ]
        
        missing_tools = []
        for tool in required_tools:
            tool_path = self.project_root / tool
            if not tool_path.exists():
                missing_tools.append(tool)
        
        if missing_tools:
            raise Exception(f"Missing required tools: {missing_tools}")
        
        self.results.append({
            "validation": "Repository Structure",
            "status": "passed",
            "details": {
                "workflow_files": len(workflow_files),
                "tools_validated": len(required_tools)
            }
        })
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate validation report"""
        total_validations = len([r for r in self.results if "validation" in r])
        passed_validations = len([r for r in self.results if r.get("status") == "passed"])
        failed_validations = len([r for r in self.results if r.get("status") == "failed"])
        
        overall_status = "PASS" if failed_validations == 0 else "FAIL"
        
        return {
            "timestamp": "2025-06-25T13:30:00Z",
            "environment": "development",
            "overall_status": overall_status,
            "summary": {
                "total_validations": total_validations,
                "passed": passed_validations,
                "failed": failed_validations,
                "success_rate": (passed_validations / total_validations * 100) if total_validations > 0 else 0
            },
            "validations": self.results
        }


def print_validation_report(report: Dict[str, Any]):
    """Print formatted validation report"""
    print(f"\n{'='*80}")
    print(f"🔍 DEVELOPMENT ENVIRONMENT VALIDATION REPORT")
    print(f"{'='*80}")
    print(f"📅 Timestamp: {report['timestamp']}")
    print(f"🎯 Overall Status: {report['overall_status']}")
    
    summary = report['summary']
    print(f"\n📊 SUMMARY:")
    print(f"   Total Validations: {summary['total_validations']}")
    print(f"   ✅ Passed: {summary['passed']}")
    print(f"   ❌ Failed: {summary['failed']}")
    print(f"   📈 Success Rate: {summary['success_rate']:.1f}%")
    
    print(f"\n📋 DETAILED RESULTS:")
    for result in report['validations']:
        if result.get('status') == 'passed':
            print(f"   ✅ {result.get('validation', 'Unknown')}")
            if 'details' in result:
                details = result['details']
                detail_str = ", ".join([f"{k}: {v}" for k, v in details.items()])
                print(f"      Details: {detail_str}")
        else:
            print(f"   ❌ {result.get('validation', 'Unknown')}")
            if 'error' in result:
                print(f"      Error: {result['error']}")
    
    print(f"\n{'='*80}")


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Validate development environment")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--output", help="Output file for JSON results")
    
    args = parser.parse_args()
    
    try:
        validator = DevEnvironmentValidator(verbose=args.verbose)
        report = validator.validate_all()
        
        # Print report
        print_validation_report(report)
        
        # Save to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n💾 Results saved to {args.output}")
        
        # Exit with appropriate code
        if report['overall_status'] == "FAIL":
            print(f"\n❌ DEVELOPMENT ENVIRONMENT VALIDATION FAILED")
            sys.exit(1)
        else:
            print(f"\n🎉 DEVELOPMENT ENVIRONMENT VALIDATION PASSED")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print(f"\n⏹️  Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Validation failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()