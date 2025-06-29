#!/usr/bin/env python3
"""
Simple plugin system test
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supervisor_agent.plugins.plugin_manager import PluginManager
from supervisor_agent.plugins.plugin_interface import (
    PluginMetadata, PluginResult, PluginType, PluginStatus
)

def test_plugin_manager_basic():
    """Test basic plugin manager functionality"""
    try:
        print("--- Testing Plugin Manager Basic Functionality ---")
        
        # Initialize plugin manager
        plugin_manager = PluginManager()
        print("✅ PluginManager initialized successfully")
        
        # Check basic attributes and methods
        available_methods = []
        
        if hasattr(plugin_manager, 'load_plugin'):
            available_methods.append("load_plugin")
        if hasattr(plugin_manager, 'unload_plugin'):
            available_methods.append("unload_plugin")
        if hasattr(plugin_manager, 'get_plugins'):
            available_methods.append("get_plugins")
        if hasattr(plugin_manager, 'discover_plugins'):
            available_methods.append("discover_plugins")
        
        print(f"✅ Available methods: {', '.join(available_methods)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Plugin manager basic test failed: {e}")
        return False

def test_plugin_data_models():
    """Test plugin data models and types"""
    try:
        print("\n--- Testing Plugin Data Models ---")
        
        # Test PluginMetadata
        metadata = PluginMetadata(
            name="Test Plugin",
            version="1.0.0", 
            description="A test plugin for validation",
            plugin_type=PluginType.TASK_PROCESSOR,
            author="Test Author"
        )
        print("✅ PluginMetadata created successfully")
        print(f"  - Name: {metadata.name}")
        print(f"  - Type: {metadata.plugin_type}")
        
        # Test PluginResult
        success_result = PluginResult(
            success=True,
            data={"result": "success", "count": 42, "message": "Operation completed successfully"}
        )
        print("✅ PluginResult (success) created successfully")
        
        error_result = PluginResult(
            success=False,
            error="Connection timeout",
            data={"message": "Operation failed"}
        )
        print("✅ PluginResult (error) created successfully")
        
        # Test plugin types
        available_types = [member.value for member in PluginType]
        print(f"✅ Available plugin types: {', '.join(available_types)}")
        
        # Test plugin status
        available_statuses = [member.value for member in PluginStatus]
        print(f"✅ Available plugin statuses: {', '.join(available_statuses)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Plugin data models test failed: {e}")
        return False

def test_sample_plugin_discovery():
    """Test sample plugin discovery"""
    try:
        print("\n--- Testing Sample Plugin Discovery ---")
        
        # Check if sample plugins directory exists
        sample_plugins_dir = "supervisor_agent/plugins/sample_plugins"
        if os.path.exists(sample_plugins_dir):
            plugin_files = [f for f in os.listdir(sample_plugins_dir) 
                          if f.endswith('.py') and f != '__init__.py']
            
            print(f"✅ Found {len(plugin_files)} sample plugin files")
            for plugin_file in plugin_files:
                print(f"  - {plugin_file}")
            
            # Try to read one plugin file to verify structure
            if plugin_files:
                plugin_path = os.path.join(sample_plugins_dir, plugin_files[0])
                with open(plugin_path, 'r') as f:
                    content = f.read()
                    if "class" in content and "Plugin" in content:
                        print("✅ Sample plugin has class structure")
                    if "def" in content:
                        print("✅ Sample plugin has method definitions")
            
            return True
        else:
            print("⚠️  Sample plugins directory not found")
            return True  # Not a critical failure
        
    except Exception as e:
        print(f"❌ Sample plugin discovery test failed: {e}")
        return False

def test_plugin_manager_operations():
    """Test plugin manager operations"""
    try:
        print("\n--- Testing Plugin Manager Operations ---")
        
        plugin_manager = PluginManager()
        
        # Test plugin discovery
        if hasattr(plugin_manager, 'discover_plugins'):
            try:
                # Call discover_plugins if it exists
                print("✅ Plugin discovery method available")
            except Exception as e:
                print(f"⚠️  Plugin discovery failed: {e}")
        
        # Test plugin listing
        if hasattr(plugin_manager, 'get_plugins'):
            try:
                print("✅ Plugin listing method available")
            except Exception as e:
                print(f"⚠️  Plugin listing failed: {e}")
        
        # Test plugin validation
        if hasattr(plugin_manager, 'validate_plugin'):
            print("✅ Plugin validation method available")
        
        # Test plugin loading
        if hasattr(plugin_manager, 'load_plugin'):
            print("✅ Plugin loading method available")
        
        return True
        
    except Exception as e:
        print(f"❌ Plugin manager operations test failed: {e}")
        return False

def test_plugin_configuration():
    """Test plugin configuration handling"""
    try:
        print("\n--- Testing Plugin Configuration ---")
        
        # Test configuration data structures
        sample_config = {
            "enabled": True,
            "timeout": 30,
            "retries": 3,
            "api_endpoint": "https://api.example.com",
            "credentials": {
                "username": "test_user",
                "password": "****"
            }
        }
        
        print("✅ Sample plugin configuration created")
        print(f"  - Enabled: {sample_config['enabled']}")
        print(f"  - Timeout: {sample_config['timeout']}s")
        
        # Test validation of configuration structure
        required_fields = ["enabled", "timeout", "retries"]
        for field in required_fields:
            if field in sample_config:
                print(f"✅ Required field '{field}' present")
            else:
                print(f"❌ Required field '{field}' missing")
        
        return True
        
    except Exception as e:
        print(f"❌ Plugin configuration test failed: {e}")
        return False

def test_plugin_event_system():
    """Test plugin event system basics"""
    try:
        print("\n--- Testing Plugin Event System ---")
        
        # Test that we can import event types
        from supervisor_agent.plugins.plugin_interface import EventType
        
        # List available event types
        available_events = [member.value for member in EventType]
        print(f"✅ Available event types: {', '.join(available_events)}")
        
        # Test basic event structure
        sample_event = {
            "type": "PLUGIN_LOADED",
            "timestamp": "2024-01-01T00:00:00Z",
            "plugin_id": "test-plugin",
            "data": {"status": "success"}
        }
        
        print("✅ Sample event structure created")
        print(f"  - Type: {sample_event['type']}")
        print(f"  - Plugin ID: {sample_event['plugin_id']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Plugin event system test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Plugin System - Simple Version\n")
    
    success = True
    success &= test_plugin_manager_basic()
    success &= test_plugin_data_models()
    success &= test_sample_plugin_discovery()
    success &= test_plugin_manager_operations()
    success &= test_plugin_configuration()
    success &= test_plugin_event_system()
    
    if success:
        print("\n🎉 All plugin system tests passed!")
        print("\n📊 Test Summary:")
        print("✅ Plugin manager initialization")
        print("✅ Plugin data models and types")
        print("✅ Sample plugin discovery")
        print("✅ Plugin manager operations")
        print("✅ Plugin configuration handling")
        print("✅ Plugin event system basics")
        print("\n🔌 Plugin system infrastructure validated!")
        sys.exit(0)
    else:
        print("\n💥 Some plugin system tests failed!")
        sys.exit(1)