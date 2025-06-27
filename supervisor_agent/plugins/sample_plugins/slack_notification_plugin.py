"""
Slack Notification Plugin

Sample plugin implementation demonstrating the notification interface
for sending messages to Slack channels via webhook or API integration.

This serves as a reference implementation for the plugin architecture
system introduced in Phase 1.3.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

import httpx

from supervisor_agent.plugins.plugin_interface import (
    NotificationInterface, PluginMetadata, PluginResult, PluginType,
    PluginEvent, EventType
)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class SlackNotificationPlugin(NotificationInterface):
    """
    Slack notification plugin for sending messages to Slack channels.
    
    Configuration:
    - webhook_url: Slack incoming webhook URL
    - api_token: Slack Bot API token (alternative to webhook)
    - default_channel: Default channel for notifications
    - username: Bot username for messages
    - icon_emoji: Bot emoji icon
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # Plugin configuration
        self.webhook_url = self.get_configuration_value("webhook_url")
        self.api_token = self.get_configuration_value("api_token")
        self.default_channel = self.get_configuration_value("default_channel", "#general")
        self.username = self.get_configuration_value("username", "Supervisor Agent")
        self.icon_emoji = self.get_configuration_value("icon_emoji", ":robot_face:")
        
        # HTTP client for API calls
        self.http_client: Optional[httpx.AsyncClient] = None
        
        # Performance tracking
        self.sent_count = 0
        self.failed_count = 0
        self.total_response_time = 0.0
    
    @property
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        return PluginMetadata(
            name="slack_notification",
            version="1.0.0",
            description="Send notifications to Slack channels via webhook or API",
            author="Supervisor Agent Team",
            plugin_type=PluginType.NOTIFICATION,
            dependencies=[],
            min_api_version="1.0.0",
            max_api_version="2.0.0",
            configuration_schema={
                "webhook_url": {
                    "type": "string",
                    "description": "Slack incoming webhook URL",
                    "required": False
                },
                "api_token": {
                    "type": "string",
                    "description": "Slack Bot API token",
                    "required": False
                },
                "default_channel": {
                    "type": "string",
                    "description": "Default channel for notifications",
                    "required": False,
                    "default": "#general"
                },
                "username": {
                    "type": "string",
                    "description": "Bot username for messages",
                    "required": False,
                    "default": "Supervisor Agent"
                },
                "icon_emoji": {
                    "type": "string",
                    "description": "Bot emoji icon",
                    "required": False,
                    "default": ":robot_face:"
                }
            },
            permissions=["network:http", "notification:send"],
            tags=["notification", "slack", "messaging"],
            homepage="https://github.com/supervisor-agent/plugins/slack",
            documentation_url="https://docs.supervisor-agent.com/plugins/slack",
            support_contact="support@supervisor-agent.com"
        )
    
    async def initialize(self) -> bool:
        """Initialize the plugin with configuration"""
        try:
            # Validate configuration
            if not self.webhook_url and not self.api_token:
                logger.error("Slack plugin requires either webhook_url or api_token")
                return False
            
            # Initialize HTTP client
            self.http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": "Supervisor-Agent-Slack-Plugin/1.0.0"}
            )
            
            # Set API token header if using API
            if self.api_token:
                self.http_client.headers["Authorization"] = f"Bearer {self.api_token}"
            
            logger.info("Slack notification plugin initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Slack plugin: {str(e)}")
            return False
    
    async def activate(self) -> bool:
        """Activate the plugin for use"""
        try:
            # Test connection by sending a test message to ourselves
            test_result = await self._test_connection()
            if test_result:
                logger.info("Slack notification plugin activated successfully")
                return True
            else:
                logger.error("Slack plugin activation failed - connection test failed")
                return False
                
        except Exception as e:
            logger.error(f"Failed to activate Slack plugin: {str(e)}")
            return False
    
    async def deactivate(self) -> bool:
        """Deactivate the plugin"""
        try:
            logger.info("Slack notification plugin deactivated")
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate Slack plugin: {str(e)}")
            return False
    
    async def cleanup(self) -> bool:
        """Clean up plugin resources"""
        try:
            if self.http_client:
                await self.http_client.aclose()
                self.http_client = None
            
            logger.info("Slack notification plugin cleaned up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup Slack plugin: {str(e)}")
            return False
    
    async def health_check(self) -> PluginResult:
        """Check plugin health status"""
        try:
            if not self.http_client:
                return PluginResult(
                    success=False,
                    error="HTTP client not initialized"
                )
            
            # Test connection
            connection_ok = await self._test_connection()
            
            health_data = {
                "status": "healthy" if connection_ok else "unhealthy",
                "connection": "ok" if connection_ok else "failed",
                "sent_count": self.sent_count,
                "failed_count": self.failed_count,
                "average_response_time": (
                    self.total_response_time / max(self.sent_count, 1)
                ),
                "configuration": {
                    "has_webhook": bool(self.webhook_url),
                    "has_api_token": bool(self.api_token),
                    "default_channel": self.default_channel
                }
            }
            
            return PluginResult(
                success=connection_ok,
                data=health_data
            )
            
        except Exception as e:
            return PluginResult(
                success=False,
                error=str(e)
            )
    
    async def send_notification(self, 
                              recipient: str, 
                              subject: str, 
                              message: str, 
                              priority: str = "normal",
                              metadata: Dict[str, Any] = None) -> PluginResult:
        """Send notification to Slack channel"""
        start_time = time.time()
        
        try:
            # Parse recipient (channel name or user)
            channel = recipient if recipient.startswith('#') or recipient.startswith('@') else f"#{recipient}"
            
            # Build message payload
            payload = {
                "channel": channel,
                "username": self.username,
                "icon_emoji": self.icon_emoji,
                "text": f"*{subject}*\n{message}"
            }
            
            # Add priority formatting
            if priority == "critical":
                payload["text"] = f":warning: *CRITICAL* :warning:\n{payload['text']}"
                payload["color"] = "danger"
            elif priority == "warning":
                payload["text"] = f":warning: *WARNING*\n{payload['text']}"
                payload["color"] = "warning"
            elif priority == "info":
                payload["color"] = "good"
            
            # Add metadata as attachment if provided
            if metadata:
                attachment = {
                    "color": payload.get("color", "good"),
                    "fields": []
                }
                
                for key, value in metadata.items():
                    attachment["fields"].append({
                        "title": key.replace("_", " ").title(),
                        "value": str(value),
                        "short": True
                    })
                
                payload["attachments"] = [attachment]
            
            # Send message
            result = await self._send_message(payload)
            
            # Update metrics
            execution_time = time.time() - start_time
            self.update_metrics(execution_time)
            self.total_response_time += execution_time
            
            if result.success:
                self.sent_count += 1
                logger.info(f"Sent Slack notification to {channel}: {subject}")
            else:
                self.failed_count += 1
                logger.error(f"Failed to send Slack notification: {result.error}")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.failed_count += 1
            logger.error(f"Error sending Slack notification: {str(e)}")
            
            return PluginResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    def get_supported_channels(self) -> List[str]:
        """Return list of supported notification channels"""
        return ["slack"]
    
    async def validate_recipient(self, recipient: str) -> bool:
        """Validate if recipient is reachable"""
        try:
            # For Slack, we can't easily validate without more API calls
            # So we do basic format validation
            return (
                recipient.startswith('#') or  # Channel
                recipient.startswith('@') or  # User mention
                not recipient.startswith('#')  # Assume channel name without #
            )
        except Exception:
            return False
    
    async def _test_connection(self) -> bool:
        """Test connection to Slack"""
        try:
            if self.api_token:
                # Test with API auth.test endpoint
                response = await self.http_client.get("https://slack.com/api/auth.test")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("ok", False)
            elif self.webhook_url:
                # Test webhook with a minimal payload
                test_payload = {
                    "text": "Connection test",
                    "username": self.username,
                    "icon_emoji": self.icon_emoji
                }
                response = await self.http_client.post(
                    self.webhook_url,
                    json=test_payload
                )
                return response.status_code == 200
            
            return False
            
        except Exception as e:
            logger.debug(f"Slack connection test failed: {str(e)}")
            return False
    
    async def _send_message(self, payload: Dict[str, Any]) -> PluginResult:
        """Send message using webhook or API"""
        try:
            if self.webhook_url:
                # Use webhook
                response = await self.http_client.post(
                    self.webhook_url,
                    json=payload
                )
                
                if response.status_code == 200:
                    return PluginResult(
                        success=True,
                        data={"response": "ok", "method": "webhook"}
                    )
                else:
                    return PluginResult(
                        success=False,
                        error=f"Webhook request failed: {response.status_code} {response.text}"
                    )
            
            elif self.api_token:
                # Use API
                response = await self.http_client.post(
                    "https://slack.com/api/chat.postMessage",
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        return PluginResult(
                            success=True,
                            data={"response": data, "method": "api"}
                        )
                    else:
                        return PluginResult(
                            success=False,
                            error=f"API error: {data.get('error', 'Unknown error')}"
                        )
                else:
                    return PluginResult(
                        success=False,
                        error=f"API request failed: {response.status_code}"
                    )
            
            else:
                return PluginResult(
                    success=False,
                    error="No webhook URL or API token configured"
                )
                
        except Exception as e:
            return PluginResult(
                success=False,
                error=str(e)
            )
    
    async def handle_event(self, event: PluginEvent) -> PluginResult:
        """Handle plugin events"""
        try:
            # Handle task completion notifications
            if event.event_type == EventType.TASK_COMPLETED:
                task_data = event.data
                await self.send_notification(
                    recipient=self.default_channel,
                    subject="Task Completed",
                    message=f"Task {task_data.get('task_id', 'unknown')} completed successfully",
                    priority="info",
                    metadata={
                        "task_id": task_data.get("task_id"),
                        "duration": task_data.get("duration"),
                        "status": "completed"
                    }
                )
            
            # Handle task failures
            elif event.event_type == EventType.TASK_FAILED:
                task_data = event.data
                await self.send_notification(
                    recipient=self.default_channel,
                    subject="Task Failed",
                    message=f"Task {task_data.get('task_id', 'unknown')} failed: {task_data.get('error', 'Unknown error')}",
                    priority="warning",
                    metadata={
                        "task_id": task_data.get("task_id"),
                        "error": task_data.get("error"),
                        "status": "failed"
                    }
                )
            
            return await super().handle_event(event)
            
        except Exception as e:
            logger.error(f"Slack plugin event handling failed: {str(e)}")
            return PluginResult(
                success=False,
                error=str(e)
            )