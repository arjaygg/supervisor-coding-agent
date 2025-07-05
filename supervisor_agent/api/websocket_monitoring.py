# supervisor_agent/api/websocket_monitoring.py
from fastapi import WebSocket


class MonitoringWebSocketHandler:
    async def stream_real_time_metrics(self, websocket: WebSocket):
        """Streams real-time metrics. Placeholder."""
        await websocket.accept()
        await websocket.send_json({"metrics": {}})
        await websocket.close()

    async def broadcast_performance_alerts(self, alert: dict):
        """Broadcasts performance alerts. Placeholder."""
        pass

    async def stream_bottleneck_updates(self, websocket: WebSocket):
        """Streams bottleneck updates. Placeholder."""
        await websocket.accept()
        await websocket.send_json({"bottlenecks": []})
        await websocket.close()
