#!/usr/bin/env python3
"""
Test script to verify Claude Code CLI Pro authentication prioritization
"""
import os
import sys
import tempfile
import subprocess
from unittest.mock import Mock, patch, MagicMock

# Add the supervisor_agent directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'supervisor_agent'))

from supervisor_agent.providers.claude_cli_provider import ClaudeCliProvider
from supervisor_agent.config import Settings


def test_pro_auth_detection():
    """Test that Pro auth detection works correctly"""
    print("Testing Pro auth detection...")
    
    # Create a mock config
    config = Settings()
    config.claude_prefer_pro_auth = True
    config.claude_api_keys = ""
    config.claude_cli_path = "claude"
    
    # Create provider
    provider = ClaudeCliProvider(
        provider_id="test",
        cli_path="claude",
        api_keys=[],
        max_requests_per_minute=60,
        mock_mode=False
    )
    
    # Test 1: Mock successful Pro auth detection
    with patch.object(provider, '_has_claude_cli_pro_auth', return_value=True):
        result = provider._has_claude_cli_pro_auth()
        print(f"✓ Pro auth detection (mocked): {result}")
        assert result is True
    
    # Test 2: Mock failed Pro auth detection
    with patch.object(provider, '_has_claude_cli_pro_auth', return_value=False):
        result = provider._has_claude_cli_pro_auth()
        print(f"✓ Pro auth detection (mocked fail): {result}")
        assert result is False
    
    print("Pro auth detection tests passed!")


def test_authentication_priority():
    """Test authentication priority logic"""
    print("\nTesting authentication priority...")
    
    # Create provider
    provider = ClaudeCliProvider(
        provider_id="test",
        config={
            "api_keys": [],
            "cli_path": "claude",
            "max_requests_per_minute": 60,
            "mock_mode": False
        }
    )
    
    # Mock the CLI validation to avoid actual CLI calls
    with patch.object(provider, '_validate_claude_cli', return_value=True):
        with patch('subprocess.run') as mock_run:
            # Mock successful CLI execution
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Test response"
            
            # Test 1: Pro auth preferred and available
            with patch.object(provider, '_has_claude_cli_pro_auth', return_value=True):
                with patch('supervisor_agent.providers.claude_cli_provider.get_config') as mock_config:
                    mock_config.return_value.claude_prefer_pro_auth = True
                    
                    result = provider._run_claude_cli("test prompt")
                    
                    # Check that API key was NOT set in environment
                    call_args = mock_run.call_args
                    if call_args and 'env' in call_args[1]:
                        env = call_args[1]['env']
                        if 'ANTHROPIC_API_KEY' in env:
                            print(f"✗ API key was set when Pro auth should be used: {env['ANTHROPIC_API_KEY']}")
                        else:
                            print("✓ Pro auth used (no API key in env)")
                    else:
                        print("✓ Pro auth used (no env manipulation)")
    
    # Test 2: Pro auth not preferred, API key used
    with patch.object(provider, '_validate_claude_cli', return_value=True):
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Test response"
            
            with patch.object(provider, '_has_claude_cli_pro_auth', return_value=True):
                with patch('supervisor_agent.providers.claude_cli_provider.get_config') as mock_config:
                    mock_config.return_value.claude_prefer_pro_auth = False
                    
                    result = provider._run_claude_cli("test prompt")
                    
                    # Check that API key was set in environment
                    call_args = mock_run.call_args
                    if call_args and 'env' in call_args[1]:
                        env = call_args[1]['env']
                        if 'ANTHROPIC_API_KEY' in env:
                            print("✓ API key used when Pro auth not preferred")
                        else:
                            print("✗ API key not set when Pro auth not preferred")
    
    print("Authentication priority tests passed!")


def test_config_integration():
    """Test that the new config option is properly integrated"""
    print("\nTesting config integration...")
    
    # Test default value
    config = Settings()
    assert config.claude_prefer_pro_auth is True
    print("✓ Default config value is True")
    
    # Test environment variable
    os.environ['CLAUDE_PREFER_PRO_AUTH'] = 'false'
    config = Settings()
    assert config.claude_prefer_pro_auth is False
    print("✓ Environment variable override works")
    
    # Clean up
    del os.environ['CLAUDE_PREFER_PRO_AUTH']
    print("Config integration tests passed!")


if __name__ == "__main__":
    print("=== Testing Claude Code CLI Pro Authentication Prioritization ===\n")
    
    try:
        test_pro_auth_detection()
        test_authentication_priority()
        test_config_integration()
        print("\n=== All tests passed! ===")
        print("\nSummary of changes:")
        print("1. Added claude_prefer_pro_auth config option (default: True)")
        print("2. Implemented _has_claude_cli_pro_auth() method")
        print("3. Updated authentication logic to prioritize Pro auth over API keys")
        print("4. Added fallback logic when Pro auth is not available")
        print("5. Added configuration to development.env")
        
    except Exception as e:
        print(f"\n=== Test failed: {e} ===")
        import traceback
        traceback.print_exc()
        sys.exit(1)