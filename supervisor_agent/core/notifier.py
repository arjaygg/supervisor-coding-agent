import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from supervisor_agent.config import settings
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class NotificationManager:
    def __init__(self):
        self.slack_client = None
        self.email_enabled = bool(settings.email_smtp_host and settings.email_username)
        self.slack_enabled = bool(settings.slack_bot_token)

        if self.slack_enabled:
            try:
                self.slack_client = WebClient(token=settings.slack_bot_token)
                logger.info("Slack client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Slack client: {str(e)}")
                self.slack_enabled = False

    async def send_quota_exhausted_alert(self, quota_status: Dict[str, Any]):
        message = self._format_quota_exhausted_message(quota_status)
        await self._send_notification(
            subject="🚨 All Claude Agents Hit Quota Limit",
            message=message,
            priority="high",
        )

    async def send_task_failure_alert(
        self, task_id: int, task_type: str, error_message: str, retry_count: int
    ):
        message = self._format_task_failure_message(
            task_id, task_type, error_message, retry_count
        )
        await self._send_notification(
            subject=f"❌ Task {task_id} Failed ({task_type})",
            message=message,
            priority="medium",
        )

    async def send_batch_completion_alert(self, batch_summary: Dict[str, Any]):
        message = self._format_batch_completion_message(batch_summary)
        await self._send_notification(
            subject=f"✅ Task Batch Completed ({batch_summary.get('task_count', 0)} tasks)",
            message=message,
            priority="low",
        )

    async def send_system_health_alert(self, health_status: Dict[str, Any]):
        message = self._format_health_alert_message(health_status)
        await self._send_notification(
            subject="⚠️ System Health Alert", message=message, priority="high"
        )

    async def send_agent_recovery_notification(
        self, agent_id: str, recovery_time: datetime
    ):
        message = f"""
🔄 **Agent Recovery Notification**

Agent `{agent_id}` has recovered and is available for task processing.

**Recovery Details:**
- Recovery Time: {recovery_time.strftime('%Y-%m-%d %H:%M:%S UTC')}
- Status: Active
- Quota: Reset and available

The agent is now ready to process new tasks.
        """.strip()

        await self._send_notification(
            subject=f"🔄 Agent {agent_id} Recovered", message=message, priority="low"
        )

    def _format_quota_exhausted_message(self, quota_status: Dict[str, Any]) -> str:
        message = f"""
🚨 **ALERT: All Claude Agents Have Hit Their Quota Limits**

All {quota_status.get('total_agents', 0)} agents are currently at their quota limits and cannot process new tasks.

**Agent Status:**
"""

        for agent in quota_status.get("agents", []):
            next_reset = agent.get("quota_reset_at", "Unknown")
            message += f"- `{agent['id']}`: {agent['quota_used']}/{agent['quota_limit']} (resets at {next_reset})\n"

        message += f"""
**Impact:** New tasks will be queued until quota resets.

**Next Reset:** Check individual agent reset times above.

**Action Required:** Consider increasing quota limits or adding more agents if this becomes frequent.
        """.strip()

        return message

    def _format_task_failure_message(
        self, task_id: int, task_type: str, error_message: str, retry_count: int
    ) -> str:
        return f"""
❌ **Task Failure Alert**

**Task Details:**
- Task ID: {task_id}
- Task Type: {task_type}
- Retry Count: {retry_count}

**Error Message:**
```
{error_message}
```

**Status:** {'Will retry automatically' if retry_count < settings.max_retries else 'Max retries reached - manual intervention required'}

**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
        """.strip()

    def _format_batch_completion_message(self, batch_summary: Dict[str, Any]) -> str:
        return f"""
✅ **Batch Processing Completed**

**Summary:**
- Tasks Processed: {batch_summary.get('task_count', 0)}
- Successful: {batch_summary.get('successful_count', 0)}
- Failed: {batch_summary.get('failed_count', 0)}
- Processing Time: {batch_summary.get('processing_time_seconds', 0)} seconds
- Agent Used: {batch_summary.get('agent_id', 'Unknown')}

**Task Types:**
"""

        for task_type, count in batch_summary.get("task_types", {}).items():
            return f"- {task_type}: {count}\n"

        return f"""
**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
        """.strip()

    def _format_health_alert_message(self, health_status: Dict[str, Any]) -> str:
        return f"""
⚠️ **System Health Alert**

**Current Status:** {health_status.get('status', 'Unknown')}

**Component Status:**
- Database: {'✅ Connected' if health_status.get('database') else '❌ Disconnected'}
- Redis: {'✅ Connected' if health_status.get('redis') else '❌ Disconnected'}
- Active Agents: {health_status.get('agents_active', 0)}

**Issues Detected:**
"""

        issues = health_status.get("issues", [])
        if issues:
            for issue in issues:
                return f"- {issue}\n"
        else:
            return "- No specific issues detected\n"

        return f"""
**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

**Action Required:** Please check system components and resolve any connectivity issues.
        """.strip()

    async def _send_notification(
        self, subject: str, message: str, priority: str = "medium"
    ):
        tasks = []

        if self.slack_enabled:
            tasks.append(self._send_slack_notification(message, priority))

        if self.email_enabled:
            tasks.append(self._send_email_notification(subject, message, priority))

        if not tasks:
            logger.warning("No notification channels configured")
            return

        # Send notifications concurrently
        import asyncio

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log results
        for i, result in enumerate(results):
            channel = "Slack" if i == 0 and self.slack_enabled else "Email"
            if isinstance(result, Exception):
                logger.error(f"Failed to send {channel} notification: {str(result)}")
            else:
                logger.info(f"Successfully sent {channel} notification")

    async def _send_slack_notification(self, message: str, priority: str):
        if not self.slack_client:
            raise Exception("Slack client not initialized")

        # Add priority emoji
        priority_emojis = {"high": "🚨", "medium": "⚠️", "low": "ℹ️"}

        formatted_message = f"{priority_emojis.get(priority, '')} {message}"

        try:
            response = self.slack_client.chat_postMessage(
                channel=settings.slack_channel, text=formatted_message, parse="mrkdwn"
            )

            if not response["ok"]:
                raise Exception(
                    f"Slack API error: {response.get('error', 'Unknown error')}"
                )

        except SlackApiError as e:
            raise Exception(f"Slack API error: {e.response['error']}")

    async def _send_email_notification(self, subject: str, message: str, priority: str):
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = settings.email_from
            msg["To"] = settings.email_to
            msg["Subject"] = f"[{priority.upper()}] {subject}"

            # Add body
            msg.attach(MIMEText(message, "plain"))

            # Send email
            with smtplib.SMTP(
                settings.email_smtp_host, settings.email_smtp_port
            ) as server:
                server.starttls()
                server.login(settings.email_username, settings.email_password)
                server.send_message(msg)

        except Exception as e:
            raise Exception(f"Email sending failed: {str(e)}")

    def test_notifications(self) -> Dict[str, bool]:
        """Test all notification channels"""
        results = {}

        test_message = f"🧪 Test notification from Supervisor Agent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"

        # Test Slack
        if self.slack_enabled:
            try:
                import asyncio

                asyncio.run(self._send_slack_notification(test_message, "low"))
                results["slack"] = True
            except Exception as e:
                logger.error(f"Slack test failed: {str(e)}")
                results["slack"] = False
        else:
            results["slack"] = None

        # Test Email
        if self.email_enabled:
            try:
                import asyncio

                asyncio.run(
                    self._send_email_notification(
                        "Test Notification", test_message, "low"
                    )
                )
                results["email"] = True
            except Exception as e:
                logger.error(f"Email test failed: {str(e)}")
                results["email"] = False
        else:
            results["email"] = None

        return results


notification_manager = NotificationManager()
