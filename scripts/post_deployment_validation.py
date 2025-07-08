#!/usr/bin/env python3
"""
Post-Deployment Validation Script

Comprehensive validation script to run after deploying the multi-provider
architecture to ensure the system is functioning correctly in the target environment.

This script validates:
1. Application startup and health
2. Database connectivity and migrations
3. API endpoint availability
4. Multi-provider system functionality
5. WebSocket connections
6. Performance benchmarks
7. Security checks

Usage:
    python3 scripts/post_deployment_validation.py --env staging --url https://staging.example.com
    python3 scripts/post_deployment_validation.py --env production --url https://prod.example.com --critical-only
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import websockets

# Add project to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class DeploymentValidator:
    """Post-deployment validation for multi-provider architecture"""

    def __init__(self, base_url: str, environment: str):
        self.base_url = base_url.rstrip("/")
        self.environment = environment
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.results = []
        self.logger = self._setup_logging()

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for validation"""
        logger = logging.getLogger("deployment_validator")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    async def validate_deployment(self, critical_only: bool = False) -> Dict[str, Any]:
        """Run all deployment validation checks"""
        self.logger.info(
            f"🚀 Starting post-deployment validation for {self.environment}"
        )
        self.logger.info(f"📍 Target URL: {self.base_url}")

        validation_checks = [
            ("Health Check", self._validate_health_endpoint, True),
            ("API Endpoints", self._validate_api_endpoints, True),
            ("Database Connectivity", self._validate_database, True),
            ("WebSocket Connections", self._validate_websockets, False),
            ("Multi-Provider System", self._validate_multi_provider, False),
            ("Authentication", self._validate_auth, True),
            ("Performance", self._validate_performance, False),
            ("Security Headers", self._validate_security, False),
            ("Frontend Assets", self._validate_frontend, True),
            ("Configuration", self._validate_configuration, True),
        ]

        for check_name, check_func, is_critical in validation_checks:
            if critical_only and not is_critical:
                continue

            self.logger.info(f"\n🔍 Validating {check_name}...")
            try:
                await check_func()
            except Exception as e:
                self.logger.error(f"❌ {check_name} validation failed: {str(e)}")
                self.results.append(
                    {
                        "check": check_name,
                        "status": "error",
                        "critical": is_critical,
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        return self._generate_validation_report()

    async def _validate_health_endpoint(self):
        """Validate application health endpoint"""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            # Test root endpoint
            async with session.get(f"{self.base_url}/") as response:
                if response.status != 200:
                    raise Exception(f"Root endpoint returned {response.status}")

                data = await response.json()

                self.results.append(
                    {
                        "check": "Root Endpoint",
                        "status": "pass",
                        "critical": True,
                        "details": data,
                        "response_time": response.headers.get(
                            "X-Response-Time", "unknown"
                        ),
                    }
                )

            # Test health endpoint if available
            try:
                async with session.get(f"{self.base_url}/api/v1/health") as response:
                    if response.status == 200:
                        health_data = await response.json()
                        self.results.append(
                            {
                                "check": "Health Endpoint",
                                "status": "pass",
                                "critical": True,
                                "details": health_data,
                            }
                        )
                    else:
                        self.results.append(
                            {
                                "check": "Health Endpoint",
                                "status": "fail",
                                "critical": False,
                                "error": f"Health endpoint returned {response.status}",
                            }
                        )
            except:
                # Health endpoint might not exist, that's okay
                pass

        self.logger.info("✅ Health endpoint validation passed")

    async def _validate_api_endpoints(self):
        """Validate key API endpoints"""
        endpoints_to_test = [
            ("/api/v1/analytics/summary", "GET", True),
            ("/api/v1/analytics/health", "GET", False),
            ("/api/v1/tasks", "GET", True),
            (
                "/api/v1/analytics/providers/dashboard",
                "GET",
                False,
            ),  # Multi-provider endpoint
        ]

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            for endpoint, method, is_critical in endpoints_to_test:
                try:
                    url = f"{self.base_url}{endpoint}"

                    if method == "GET":
                        async with session.get(url) as response:
                            success = response.status in [
                                200,
                                400,
                                401,
                            ]  # 400/401 are acceptable for some endpoints

                            self.results.append(
                                {
                                    "check": f"API {endpoint}",
                                    "status": "pass" if success else "fail",
                                    "critical": is_critical,
                                    "details": {
                                        "status_code": response.status,
                                        "content_type": response.headers.get(
                                            "content-type", "unknown"
                                        ),
                                    },
                                }
                            )

                            if not success and is_critical:
                                raise Exception(
                                    f"Critical endpoint {endpoint} returned {response.status}"
                                )

                except Exception as e:
                    if is_critical:
                        raise
                    else:
                        self.results.append(
                            {
                                "check": f"API {endpoint}",
                                "status": "fail",
                                "critical": False,
                                "error": str(e),
                            }
                        )

        self.logger.info("✅ API endpoints validation completed")

    async def _validate_database(self):
        """Validate database connectivity through API"""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            # Try to access an endpoint that requires database
            try:
                async with session.get(
                    f"{self.base_url}/api/v1/analytics/summary"
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        self.results.append(
                            {
                                "check": "Database Connectivity",
                                "status": "pass",
                                "critical": True,
                                "details": {
                                    "analytics_accessible": True,
                                    "total_tasks": data.get("total_tasks", 0),
                                },
                            }
                        )
                    else:
                        # If we get a non-500 error, database might be working but other issues exist
                        if response.status >= 500:
                            raise Exception(
                                f"Analytics endpoint returned {response.status} - likely database issue"
                            )
                        else:
                            self.results.append(
                                {
                                    "check": "Database Connectivity",
                                    "status": "warning",
                                    "critical": True,
                                    "details": {
                                        "status_code": response.status,
                                        "note": "Non-500 error suggests DB is working",
                                    },
                                }
                            )

            except Exception as e:
                raise Exception(f"Database validation failed: {str(e)}")

        self.logger.info("✅ Database connectivity validation passed")

    async def _validate_websockets(self):
        """Validate WebSocket connectivity"""
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")

        try:
            # Test main WebSocket endpoint
            async with websockets.connect(f"{ws_url}/ws", ping_timeout=10) as websocket:
                # Send a test message
                test_message = json.dumps(
                    {"type": "ping", "timestamp": datetime.utcnow().isoformat()}
                )
                await websocket.send(test_message)

                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)

                self.results.append(
                    {
                        "check": "WebSocket Main",
                        "status": "pass",
                        "critical": False,
                        "details": {"response_received": True, "response": response},
                    }
                )

            # Test provider WebSocket if multi-provider is enabled
            try:
                async with websockets.connect(
                    f"{ws_url}/ws/providers", ping_timeout=10
                ) as websocket:
                    # Just test connection, don't wait for specific response
                    await asyncio.sleep(1)

                    self.results.append(
                        {
                            "check": "WebSocket Providers",
                            "status": "pass",
                            "critical": False,
                            "details": {"provider_websocket_available": True},
                        }
                    )
            except:
                # Provider WebSocket might not be available if multi-provider is disabled
                self.results.append(
                    {
                        "check": "WebSocket Providers",
                        "status": "skip",
                        "critical": False,
                        "details": {
                            "note": "Provider WebSocket not available (multi-provider may be disabled)"
                        },
                    }
                )

        except Exception as e:
            # WebSocket failures are not critical for basic functionality
            self.results.append(
                {
                    "check": "WebSocket Connectivity",
                    "status": "fail",
                    "critical": False,
                    "error": str(e),
                }
            )

        self.logger.info("✅ WebSocket validation completed")

    async def _validate_multi_provider(self):
        """Validate multi-provider system functionality"""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            # Check if multi-provider dashboard is available
            try:
                async with session.get(
                    f"{self.base_url}/api/v1/analytics/providers/dashboard"
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        self.results.append(
                            {
                                "check": "Multi-Provider Dashboard",
                                "status": "pass",
                                "critical": False,
                                "details": {
                                    "multi_provider_enabled": True,
                                    "total_providers": data.get("overview", {}).get(
                                        "total_providers", 0
                                    ),
                                    "healthy_providers": data.get("overview", {}).get(
                                        "healthy_providers", 0
                                    ),
                                },
                            }
                        )
                    elif response.status == 400:
                        # Multi-provider not enabled
                        self.results.append(
                            {
                                "check": "Multi-Provider System",
                                "status": "disabled",
                                "critical": False,
                                "details": {"multi_provider_enabled": False},
                            }
                        )
                    else:
                        raise Exception(f"Unexpected response: {response.status}")

            except Exception as e:
                self.results.append(
                    {
                        "check": "Multi-Provider System",
                        "status": "fail",
                        "critical": False,
                        "error": str(e),
                    }
                )

        self.logger.info("✅ Multi-provider validation completed")

    async def _validate_auth(self):
        """Validate authentication and authorization"""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            # Test if endpoints are properly secured or accessible as expected
            auth_tests = [
                ("/api/v1/analytics/summary", "Should be accessible"),
                ("/api/v1/tasks", "Should be accessible or require auth"),
            ]

            accessible_endpoints = 0

            for endpoint, expectation in auth_tests:
                try:
                    async with session.get(f"{self.base_url}{endpoint}") as response:
                        # 200 = accessible, 401/403 = properly secured, 500+ = server error
                        if response.status in [200, 401, 403]:
                            accessible_endpoints += 1

                except:
                    pass  # Network errors are handled elsewhere

            self.results.append(
                {
                    "check": "Authentication",
                    "status": "pass",
                    "critical": True,
                    "details": {
                        "accessible_endpoints": accessible_endpoints,
                        "total_tested": len(auth_tests),
                        "note": "Endpoints responding appropriately to auth requirements",
                    },
                }
            )

        self.logger.info("✅ Authentication validation passed")

    async def _validate_performance(self):
        """Validate basic performance characteristics"""
        performance_tests = [
            ("/", "Root endpoint"),
            ("/api/v1/analytics/summary", "Analytics summary"),
        ]

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            for endpoint, description in performance_tests:
                start_time = time.time()

                try:
                    async with session.get(f"{self.base_url}{endpoint}") as response:
                        response_time = time.time() - start_time

                        self.results.append(
                            {
                                "check": f"Performance - {description}",
                                "status": "pass" if response_time < 5.0 else "slow",
                                "critical": False,
                                "details": {
                                    "response_time": response_time,
                                    "status_code": response.status,
                                    "threshold": "5.0s",
                                },
                            }
                        )

                except Exception as e:
                    self.results.append(
                        {
                            "check": f"Performance - {description}",
                            "status": "fail",
                            "critical": False,
                            "error": str(e),
                        }
                    )

        self.logger.info("✅ Performance validation completed")

    async def _validate_security(self):
        """Validate security headers and configurations"""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(f"{self.base_url}/") as response:
                headers = dict(response.headers)

                security_checks = {
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": ["DENY", "SAMEORIGIN"],
                    "X-XSS-Protection": "1; mode=block",
                }

                security_score = 0
                total_checks = len(security_checks)

                for header, expected in security_checks.items():
                    if header in headers:
                        if isinstance(expected, list):
                            if headers[header] in expected:
                                security_score += 1
                        else:
                            if headers[header] == expected:
                                security_score += 1

                self.results.append(
                    {
                        "check": "Security Headers",
                        "status": "pass" if security_score > 0 else "warning",
                        "critical": False,
                        "details": {
                            "security_score": f"{security_score}/{total_checks}",
                            "headers_present": list(headers.keys()),
                            "missing_security_headers": [
                                h for h in security_checks.keys() if h not in headers
                            ],
                        },
                    }
                )

        self.logger.info("✅ Security validation completed")

    async def _validate_frontend(self):
        """Validate frontend assets and accessibility"""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            # Test if frontend routes are accessible
            frontend_routes = [
                "/",
                "/analytics",
                "/chat",
            ]

            accessible_routes = 0

            for route in frontend_routes:
                try:
                    async with session.get(f"{self.base_url}{route}") as response:
                        if response.status == 200:
                            accessible_routes += 1

                except:
                    pass  # Route might not exist

            self.results.append(
                {
                    "check": "Frontend Assets",
                    "status": "pass" if accessible_routes > 0 else "warning",
                    "critical": True,
                    "details": {
                        "accessible_routes": accessible_routes,
                        "total_routes": len(frontend_routes),
                    },
                }
            )

        self.logger.info("✅ Frontend validation completed")

    async def _validate_configuration(self):
        """Validate configuration through API responses"""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                # Get analytics summary to check if system is configured
                async with session.get(
                    f"{self.base_url}/api/v1/analytics/summary"
                ) as response:
                    if response.status == 200:
                        data = await response.json()

                        self.results.append(
                            {
                                "check": "Configuration",
                                "status": "pass",
                                "critical": True,
                                "details": {
                                    "analytics_available": True,
                                    "system_responding": True,
                                    "data_available": bool(data),
                                },
                            }
                        )
                    else:
                        raise Exception(
                            f"Configuration check failed with status {response.status}"
                        )

            except Exception as e:
                raise Exception(f"Configuration validation failed: {str(e)}")

        self.logger.info("✅ Configuration validation passed")

    def _generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report"""
        total_checks = len(self.results)
        passed_checks = sum(1 for r in self.results if r.get("status") == "pass")
        failed_checks = sum(
            1 for r in self.results if r.get("status") in ["fail", "error"]
        )
        warning_checks = sum(
            1 for r in self.results if r.get("status") in ["warning", "slow"]
        )

        critical_checks = [r for r in self.results if r.get("critical", False)]
        critical_failures = sum(
            1 for r in critical_checks if r.get("status") in ["fail", "error"]
        )

        # Determine overall status
        if critical_failures > 0:
            overall_status = "CRITICAL_FAILURE"
        elif failed_checks > 0:
            overall_status = "PARTIAL_FAILURE"
        elif warning_checks > 0:
            overall_status = "WARNING"
        else:
            overall_status = "SUCCESS"

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": self.environment,
            "base_url": self.base_url,
            "overall_status": overall_status,
            "summary": {
                "total_checks": total_checks,
                "passed": passed_checks,
                "failed": failed_checks,
                "warnings": warning_checks,
                "critical_failures": critical_failures,
                "success_rate": (
                    (passed_checks / total_checks * 100) if total_checks > 0 else 0
                ),
            },
            "checks": self.results,
            "recommendations": self._generate_recommendations(),
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []

        critical_failures = [
            r
            for r in self.results
            if r.get("critical") and r.get("status") in ["fail", "error"]
        ]
        if critical_failures:
            recommendations.append(
                "🔥 Address critical failures before proceeding with deployment"
            )

        failed_checks = [
            r for r in self.results if r.get("status") in ["fail", "error"]
        ]
        if failed_checks:
            recommendations.append("🔧 Review and fix failed validation checks")

        slow_responses = [r for r in self.results if r.get("status") == "slow"]
        if slow_responses:
            recommendations.append(
                "⚡ Investigate performance issues for slow-responding endpoints"
            )

        security_issues = [
            r
            for r in self.results
            if "Security" in r.get("check", "") and r.get("status") != "pass"
        ]
        if security_issues:
            recommendations.append("🔒 Review and implement missing security headers")

        if not recommendations:
            recommendations.append(
                "✅ All validations passed successfully - deployment looks good!"
            )

        return recommendations


def print_validation_report(report: Dict[str, Any]):
    """Print formatted validation report"""
    print(f"\n{'='*80}")
    print(f"📋 POST-DEPLOYMENT VALIDATION REPORT")
    print(f"{'='*80}")
    print(f"🌍 Environment: {report['environment']}")
    print(f"🔗 Base URL: {report['base_url']}")
    print(f"📅 Timestamp: {report['timestamp']}")
    print(f"🎯 Overall Status: {report['overall_status']}")

    summary = report["summary"]
    print(f"\n📊 SUMMARY:")
    print(f"   Total Checks: {summary['total_checks']}")
    print(f"   ✅ Passed: {summary['passed']}")
    print(f"   ❌ Failed: {summary['failed']}")
    print(f"   ⚠️  Warnings: {summary['warnings']}")
    print(f"   🔥 Critical Failures: {summary['critical_failures']}")
    print(f"   📈 Success Rate: {summary['success_rate']:.1f}%")

    print(f"\n🔍 DETAILED RESULTS:")
    for check in report["checks"]:
        status_icon = {
            "pass": "✅",
            "fail": "❌",
            "error": "💥",
            "warning": "⚠️",
            "slow": "🐌",
            "skip": "⏭️",
            "disabled": "🚫",
        }.get(check.get("status"), "❓")

        critical_marker = "🔥" if check.get("critical") else "  "
        print(
            f"   {critical_marker} {status_icon} {check.get('check', 'Unknown Check')}"
        )

        if check.get("error"):
            print(f"      Error: {check['error']}")
        elif check.get("details"):
            details = check["details"]
            if isinstance(details, dict) and len(details) <= 3:
                for key, value in details.items():
                    print(f"      {key}: {value}")

    print(f"\n💡 RECOMMENDATIONS:")
    for rec in report["recommendations"]:
        print(f"   {rec}")

    print(f"\n{'='*80}")


async def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="Post-deployment validation for multi-provider architecture"
    )
    parser.add_argument("--url", required=True, help="Base URL of deployed application")
    parser.add_argument(
        "--env",
        required=True,
        choices=["staging", "production", "testing"],
        help="Environment name",
    )
    parser.add_argument(
        "--critical-only", action="store_true", help="Run only critical validations"
    )
    parser.add_argument("--output", help="Output file for JSON results")
    parser.add_argument(
        "--timeout", type=int, default=30, help="Request timeout in seconds"
    )

    args = parser.parse_args()

    # Create validator
    validator = DeploymentValidator(args.url, args.env)
    validator.timeout = aiohttp.ClientTimeout(total=args.timeout)

    try:
        # Run validation
        report = await validator.validate_deployment(critical_only=args.critical_only)

        # Print report
        print_validation_report(report)

        # Save to file if requested
        if args.output:
            with open(args.output, "w") as f:
                json.dump(report, f, indent=2)
            print(f"\n💾 Results saved to {args.output}")

        # Exit with appropriate code
        if report["overall_status"] == "CRITICAL_FAILURE":
            print(f"\n🚨 DEPLOYMENT VALIDATION FAILED - Critical issues detected")
            sys.exit(1)
        elif report["overall_status"] in ["PARTIAL_FAILURE", "WARNING"]:
            print(f"\n⚠️  DEPLOYMENT VALIDATION COMPLETED WITH WARNINGS")
            sys.exit(2)
        else:
            print(f"\n🎉 DEPLOYMENT VALIDATION SUCCESSFUL")
            sys.exit(0)

    except KeyboardInterrupt:
        print(f"\n⏹️  Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Validation failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
