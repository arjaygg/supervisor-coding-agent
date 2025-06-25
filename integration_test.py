#!/usr/bin/env python3
"""
Integration Test Script for Multi-Provider Architecture

Quick validation that the multi-provider system is correctly integrated
and all components can be imported and initialized.
"""

import sys
import traceback
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Test that all core components can be imported"""
    print("🔍 Testing imports...")
    
    try:
        from supervisor_agent.core.enhanced_agent_manager import EnhancedAgentManager, enhanced_agent_manager
        print("✅ Enhanced Agent Manager")
        
        from supervisor_agent.core.multi_provider_service import MultiProviderService, multi_provider_service
        print("✅ Multi-Provider Service")
        
        from supervisor_agent.core.provider_coordinator import ProviderCoordinator, ExecutionContext
        print("✅ Provider Coordinator")
        
        from supervisor_agent.core.multi_provider_task_processor import MultiProviderTaskProcessor
        print("✅ Multi-Provider Task Processor")
        
        from supervisor_agent.api.websocket_providers import provider_ws_manager
        print("✅ WebSocket Provider Manager")
        
        from supervisor_agent.providers.claude_cli_provider import ClaudeCliProvider
        print("✅ Claude CLI Provider")
        
        from supervisor_agent.providers.local_mock_provider import LocalMockProvider
        print("✅ Local Mock Provider")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {str(e)}")
        traceback.print_exc()
        return False


def test_configuration():
    """Test configuration loading"""
    print("\n🔧 Testing configuration...")
    
    try:
        from supervisor_agent.config import settings
        
        print(f"✅ Configuration loaded")
        print(f"   - Multi-provider enabled: {settings.multi_provider_enabled}")
        print(f"   - Load balancing strategy: {settings.default_load_balancing_strategy}")
        print(f"   - Provider configs available: {len(settings.get_provider_configs())}")
        
        # Validate configuration
        warnings = settings.validate_configuration()
        if warnings:
            print("⚠️  Configuration warnings:")
            for warning in warnings[:3]:  # Show first 3 warnings
                print(f"   - {warning}")
        else:
            print("✅ No configuration warnings")
            
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {str(e)}")
        return False


def test_enhanced_agent_manager():
    """Test enhanced agent manager initialization"""
    print("\n🤖 Testing Enhanced Agent Manager...")
    
    try:
        from supervisor_agent.core.enhanced_agent_manager import EnhancedAgentManager
        
        # Test initialization with multi-provider disabled
        manager_legacy = EnhancedAgentManager(enable_multi_provider=False)
        print("✅ Legacy-only mode initialization")
        
        # Test initialization with multi-provider enabled
        manager_multi = EnhancedAgentManager(enable_multi_provider=True)
        print("✅ Multi-provider mode initialization")
        
        # Test getting legacy manager
        legacy_mgr = manager_multi.get_legacy_manager()
        print(f"✅ Legacy manager available: {type(legacy_mgr).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ Enhanced Agent Manager test failed: {str(e)}")
        return False


def test_provider_system():
    """Test provider system components"""
    print("\n🏭 Testing Provider System...")
    
    try:
        from supervisor_agent.providers.provider_registry import ProviderRegistry, LoadBalancingStrategy
        from supervisor_agent.providers.local_mock_provider import LocalMockProvider
        
        # Test provider registry
        registry = ProviderRegistry()
        print("✅ Provider Registry created")
        
        # Test mock provider
        mock_provider = LocalMockProvider(
            provider_id="test-mock",
            config={
                "response_delay_min": 0.1,
                "response_delay_max": 0.2,
                "failure_rate": 0.0,
                "deterministic": True
            }
        )
        print("✅ Mock Provider created")
        
        # Test provider capabilities
        capabilities = mock_provider.get_capabilities()
        print(f"✅ Provider capabilities: {len(capabilities.supported_tasks)} tasks")
        
        # Test load balancing strategies
        strategies = list(LoadBalancingStrategy)
        print(f"✅ Load balancing strategies available: {len(strategies)}")
        
        return True
    except Exception as e:
        print(f"❌ Provider system test failed: {str(e)}")
        return False


async def test_async_components():
    """Test async components"""
    print("\n⚡ Testing Async Components...")
    
    try:
        from supervisor_agent.core.enhanced_agent_manager import enhanced_agent_manager
        
        # Test system health check
        health = await enhanced_agent_manager.get_system_health()
        print(f"✅ System health check completed: {health['overall_status']}")
        
        # Test agent availability
        agents = await enhanced_agent_manager.get_available_agents()
        print(f"✅ Agent availability check: {agents['total_capacity']} total capacity")
        
        return True
    except Exception as e:
        print(f"❌ Async components test failed: {str(e)}")
        return False


def test_api_routes():
    """Test that API routes can be imported"""
    print("\n🌐 Testing API Routes...")
    
    try:
        from supervisor_agent.api.routes.providers import router as providers_router
        print("✅ Provider API routes")
        
        from supervisor_agent.api.routes.analytics import router as analytics_router  
        print("✅ Analytics API routes")
        
        from supervisor_agent.api.websocket_providers import router as ws_providers_router
        print("✅ WebSocket Provider routes")
        
        # Count routes
        provider_routes = len([route for route in providers_router.routes])
        analytics_routes = len([route for route in analytics_router.routes])
        ws_routes = len([route for route in ws_providers_router.routes])
        
        print(f"   - Provider routes: {provider_routes}")
        print(f"   - Analytics routes: {analytics_routes}")
        print(f"   - WebSocket routes: {ws_routes}")
        
        return True
    except Exception as e:
        print(f"❌ API routes test failed: {str(e)}")
        return False


async def run_integration_tests():
    """Run all integration tests"""
    print("🚀 Starting Multi-Provider Architecture Integration Tests\n")
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_configuration),
        ("Enhanced Agent Manager", test_enhanced_agent_manager),
        ("Provider System", test_provider_system),
        ("API Routes", test_api_routes),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            if test_func():
                results.append((test_name, True))
            else:
                results.append((test_name, False))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {str(e)}")
            results.append((test_name, False))
    
    # Run async tests
    try:
        if await test_async_components():
            results.append(("Async Components", True))
        else:
            results.append(("Async Components", False))
    except Exception as e:
        print(f"❌ Async Components test crashed: {str(e)}")
        results.append(("Async Components", False))
    
    # Print summary
    print(f"\n{'='*60}")
    print("📊 Integration Test Summary")
    print(f"{'='*60}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:<25} {status}")
    
    print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed! Multi-provider system is ready.")
        return True
    else:
        print("⚠️  Some tests failed. Please review the errors above.")
        return False


if __name__ == "__main__":
    import asyncio
    
    try:
        success = asyncio.run(run_integration_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Tests crashed: {str(e)}")
        traceback.print_exc()
        sys.exit(1)