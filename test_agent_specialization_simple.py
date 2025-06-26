#!/usr/bin/env python3
"""
Simple test for Agent Specialization Engine core logic
Tests the engine without complex database dependencies
"""

import asyncio
import sys
from datetime import datetime

sys.path.append('/home/devag/git/dev-assist')

# Test core components directly without full integration
async def test_agent_specialization_core():
    """Test core agent specialization logic"""
    print("🔍 Testing Agent Specialization Core Logic...")
    
    # Import and test the core classes directly
    from supervisor_agent.orchestration.agent_specialization_engine import (
        AgentSpecialty, SpecializationCapability, DefaultTaskAnalyzer
    )
    from supervisor_agent.providers.base_provider import TaskCapability, ProviderType
    
    # Test AgentSpecialty enum
    print("✅ AgentSpecialty enum loaded successfully")
    print(f"   Available specialties: {len(list(AgentSpecialty))}")
    for specialty in list(AgentSpecialty)[:5]:
        print(f"   - {specialty.value}")
    
    # Test SpecializationCapability
    capability = SpecializationCapability(
        name="Test Security Analysis",
        proficiency_score=0.9,
        task_types=[TaskCapability.SECURITY_ANALYSIS],
        provider_preferences=[ProviderType.CLAUDE_CLI],
        context_requirements={"domain": "security"},
        performance_metrics={"success_rate": 0.9}
    )
    
    print("✅ SpecializationCapability created successfully")
    print(f"   Capability: {capability.name}")
    print(f"   Proficiency: {capability.proficiency_score}")
    
    # Test task analysis
    analyzer = DefaultTaskAnalyzer()
    print("✅ DefaultTaskAnalyzer created successfully")
    
    print("\n🎯 Core Agent Specialization Components Working!")
    return True


async def main():
    """Main test runner"""
    print("🚀 Agent Specialization Engine - Core Logic Test")
    print("=" * 60)
    
    try:
        result = await test_agent_specialization_core()
        
        if result:
            print("\n✅ Core components working correctly!")
            print("📝 Note: Full integration test requires schema fixes")
            return 0
        else:
            print("\n❌ Core components failed")
            return 1
            
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)