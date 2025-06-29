/**
 * Advanced Analytics Dashboard Component
 * 
 * Provides comprehensive real-time analytics interface with interactive charts,
 * ML predictions, anomaly detection, and export capabilities as specified in Phase 1.2.
 * 
 * Features:
 * - Real-time metrics streaming via WebSocket
 * - Interactive charts with zoom and filter capabilities
 * - ML-powered predictions and anomaly detection
 * - Custom analytics queries and filtering
 * - Data export in multiple formats
 * - Historical trend analysis
 * - Performance insights and recommendations
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  RefreshCw,
  Download,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  Users,
  Server
} from 'lucide-react';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  TimeScale
);

interface MetricData {
  [key: string]: number | string;
  timestamp: string;
}

interface AnalyticsData {
  scope: string;
  timestamp: string;
  metrics: MetricData;
  predictions?: {
    [key: string]: Array<{
      timestamp: string;
      predicted_value: number;
      confidence: number;
      confidence_interval: [number, number];
    }>;
  };
  anomalies?: {
    [key: string]: Array<{
      type: string;
      severity: string;
      timestamp: string;
      value: number;
      expected_value: number;
      confidence: number;
      description: string;
    }>;
  };
}

interface Insight {
  category: string;
  type: string;
  title: string;
  description: string;
  confidence: number;
  impact_score: number;
  recommendations: string[];
  metrics: { [key: string]: number };
}

interface WebSocketMessage {
  type: string;
  timestamp: string;
  data: any;
}

const AdvancedAnalyticsDashboard: React.FC = () => {
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [selectedScope, setSelectedScope] = useState<string>('system');
  const [selectedTimeRange, setSelectedTimeRange] = useState<string>('24h');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [includePredictions, setIncludePredictions] = useState<boolean>(true);
  const [includeAnomalies, setIncludeAnomalies] = useState<boolean>(true);
  
  const wsRef = useRef<WebSocket | null>(null);
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // WebSocket connection management
  const connectWebSocket = useCallback(() => {
    try {
      const wsUrl = `ws://localhost:8000/api/v1/analytics/advanced/stream`;
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        setIsConnected(true);
        console.log('Analytics WebSocket connected');
        
        // Send preferences
        const preferences = {
          type: 'update_preferences',
          preferences: {
            metrics: [selectedScope],
            refresh_interval: 30,
            anomaly_alerts: includeAnomalies
          }
        };
        wsRef.current?.send(JSON.stringify(preferences));
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          
          if (message.type === 'metrics_update') {
            updateMetricsFromWebSocket(message.data);
          } else if (message.type === 'anomaly_alert') {
            handleAnomalyAlert(message.data);
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      wsRef.current.onclose = () => {
        setIsConnected(false);
        console.log('Analytics WebSocket disconnected');
        
        // Attempt to reconnect after 5 seconds
        setTimeout(connectWebSocket, 5000);
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
      };
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      setIsConnected(false);
    }
  }, [selectedScope, includeAnomalies]);

  const updateMetricsFromWebSocket = (data: MetricData) => {
    setAnalyticsData(prev => prev ? {
      ...prev,
      metrics: data,
      timestamp: new Date().toISOString()
    } : null);
  };

  const handleAnomalyAlert = (data: any) => {
    // Show toast notification for critical anomalies
    if (data.critical_anomalies && data.critical_anomalies.length > 0) {
      console.warn('Critical anomalies detected:', data.critical_anomalies);
      // In a real app, this would trigger a toast notification
    }
  };

  // Fetch analytics data
  const fetchAnalyticsData = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams({
        scope: selectedScope,
        include_predictions: includePredictions.toString(),
        include_anomalies: includeAnomalies.toString()
      });

      const response = await fetch(`/api/v1/analytics/advanced/metrics/real-time?${params}`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch analytics data: ${response.statusText}`);
      }

      const data: AnalyticsData = await response.json();
      setAnalyticsData(data);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to fetch analytics data');
      console.error('Analytics fetch error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch insights
  const fetchInsights = async () => {
    try {
      const params = new URLSearchParams({
        timeframe_hours: selectedTimeRange === '1h' ? '1' : 
                        selectedTimeRange === '6h' ? '6' : 
                        selectedTimeRange === '24h' ? '24' : 
                        selectedTimeRange === '7d' ? '168' : '24',
        min_confidence: '0.7',
        categories: 'performance,efficiency,anomalies'
      });

      const response = await fetch(`/api/v1/analytics/advanced/insights?${params}`);
      
      if (response.ok) {
        const data = await response.json();
        setInsights(data.insights || []);
      }
    } catch (error) {
      console.error('Failed to fetch insights:', error);
    }
  };

  // Export data
  const exportData = async (format: 'json' | 'csv' | 'excel') => {
    try {
      const params = new URLSearchParams({
        format,
        time_range: selectedTimeRange,
        metric_types: selectedScope,
        include_metadata: 'true'
      });

      const response = await fetch(`/api/v1/analytics/advanced/export?${params}`);
      
      if (!response.ok) {
        throw new Error('Export failed');
      }

      // Handle different export formats
      if (format === 'json') {
        const data = await response.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        downloadBlob(blob, `analytics_export_${Date.now()}.json`);
      } else {
        const blob = await response.blob();
        const extension = format === 'csv' ? 'csv' : 'xlsx';
        downloadBlob(blob, `analytics_export_${Date.now()}.${extension}`);
      }
    } catch (error) {
      console.error('Export failed:', error);
      setError('Failed to export data');
    }
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Chart configuration
  const createChartData = (metrics: MetricData) => {
    const labels = Object.keys(metrics).filter(key => key !== 'timestamp');
    const values = labels.map(label => typeof metrics[label] === 'number' ? metrics[label] : 0);

    return {
      labels,
      datasets: [
        {
          label: 'Current Values',
          data: values,
          backgroundColor: 'rgba(59, 130, 246, 0.5)',
          borderColor: 'rgba(59, 130, 246, 1)',
          borderWidth: 2,
          fill: false,
        },
      ],
    };
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: `${selectedScope.charAt(0).toUpperCase() + selectedScope.slice(1)} Metrics`,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
      },
    },
  };

  // Effects
  useEffect(() => {
    fetchAnalyticsData();
    fetchInsights();
    
    // Set up auto-refresh
    refreshIntervalRef.current = setInterval(() => {
      if (!isConnected) {
        fetchAnalyticsData();
      }
      fetchInsights();
    }, 30000);

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [selectedScope, selectedTimeRange, includePredictions, includeAnomalies]);

  useEffect(() => {
    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connectWebSocket]);

  // Render severity badge
  const renderSeverityBadge = (severity: string) => {
    const colors = {
      critical: 'destructive',
      warning: 'secondary',
      info: 'outline'
    };
    
    return (
      <Badge variant={colors[severity as keyof typeof colors] || 'outline'}>
        {severity}
      </Badge>
    );
  };

  // Render metric card
  const renderMetricCard = (title: string, value: string | number, icon: React.ReactNode, trend?: string) => (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {trend && (
          <p className="text-xs text-muted-foreground">
            {trend}
          </p>
        )}
      </CardContent>
    </Card>
  );

  return (
    <div className="space-y-6">
      {/* Header Controls */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold">Advanced Analytics</h2>
          <p className="text-muted-foreground">
            Real-time insights with ML predictions and anomaly detection
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Badge variant={isConnected ? "default" : "secondary"}>
            {isConnected ? "Live" : "Polling"}
          </Badge>
          <Button onClick={fetchAnalyticsData} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4">
        <Select value={selectedScope} onValueChange={setSelectedScope}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Select scope" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="system">System Metrics</SelectItem>
            <SelectItem value="tasks">Task Metrics</SelectItem>
            <SelectItem value="users">User Metrics</SelectItem>
            <SelectItem value="custom">Custom Metrics</SelectItem>
          </SelectContent>
        </Select>

        <Select value={selectedTimeRange} onValueChange={setSelectedTimeRange}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Select time range" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="1h">Last Hour</SelectItem>
            <SelectItem value="6h">Last 6 Hours</SelectItem>
            <SelectItem value="24h">Last 24 Hours</SelectItem>
            <SelectItem value="7d">Last 7 Days</SelectItem>
          </SelectContent>
        </Select>

        <div className="flex items-center space-x-2">
          <Button
            variant={includePredictions ? "default" : "outline"}
            size="sm"
            onClick={() => setIncludePredictions(!includePredictions)}
          >
            <TrendingUp className="h-4 w-4 mr-1" />
            Predictions
          </Button>
          <Button
            variant={includeAnomalies ? "default" : "outline"}
            size="sm"
            onClick={() => setIncludeAnomalies(!includeAnomalies)}
          >
            <AlertTriangle className="h-4 w-4 mr-1" />
            Anomalies
          </Button>
        </div>

        <Select onValueChange={(value) => exportData(value as 'json' | 'csv' | 'excel')}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Export data..." />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="json">Export as JSON</SelectItem>
            <SelectItem value="csv">Export as CSV</SelectItem>
            <SelectItem value="excel">Export as Excel</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Main Content */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="charts">Charts</TabsTrigger>
          <TabsTrigger value="predictions">Predictions</TabsTrigger>
          <TabsTrigger value="anomalies">Anomalies</TabsTrigger>
          <TabsTrigger value="insights">Insights</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          {analyticsData && (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {selectedScope === 'system' && (
                <>
                  {renderMetricCard(
                    "CPU Usage",
                    `${analyticsData.metrics.cpu_percent || 0}%`,
                    <Server className="h-4 w-4 text-muted-foreground" />
                  )}
                  {renderMetricCard(
                    "Memory Usage",
                    `${analyticsData.metrics.memory_percent || 0}%`,
                    <Activity className="h-4 w-4 text-muted-foreground" />
                  )}
                  {renderMetricCard(
                    "Load Average",
                    `${analyticsData.metrics.load_avg_1m || 0}`,
                    <Zap className="h-4 w-4 text-muted-foreground" />
                  )}
                  {renderMetricCard(
                    "Process Count",
                    analyticsData.metrics.process_count || 0,
                    <Users className="h-4 w-4 text-muted-foreground" />
                  )}
                </>
              )}
              
              {selectedScope === 'tasks' && (
                <>
                  {renderMetricCard(
                    "Total Tasks",
                    analyticsData.metrics.total_tasks || 0,
                    <Activity className="h-4 w-4 text-muted-foreground" />
                  )}
                  {renderMetricCard(
                    "Success Rate",
                    `${analyticsData.metrics.success_rate || 0}%`,
                    <TrendingUp className="h-4 w-4 text-muted-foreground" />
                  )}
                  {renderMetricCard(
                    "Queue Depth",
                    analyticsData.metrics.queue_depth || 0,
                    <Server className="h-4 w-4 text-muted-foreground" />
                  )}
                  {renderMetricCard(
                    "Avg Exec Time",
                    `${(analyticsData.metrics.avg_execution_time || 0)} sec`,
                    <Zap className="h-4 w-4 text-muted-foreground" />
                  )}
                </>
              )}
            </div>
          )}
        </TabsContent>

        {/* Charts Tab */}
        <TabsContent value="charts" className="space-y-4">
          {analyticsData && (
            <Card>
              <CardHeader>
                <CardTitle>Real-time Metrics</CardTitle>
                <CardDescription>
                  Current {selectedScope} metrics with live updates
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Bar data={createChartData(analyticsData.metrics)} options={chartOptions} />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Predictions Tab */}
        <TabsContent value="predictions" className="space-y-4">
          {analyticsData?.predictions && Object.keys(analyticsData.predictions).length > 0 ? (
            <div className="grid gap-4">
              {Object.entries(analyticsData.predictions).map(([metric, predictions]) => (
                <Card key={metric}>
                  <CardHeader>
                    <CardTitle>{metric} Predictions</CardTitle>
                    <CardDescription>
                      ML-powered forecasts for the next 6 time periods
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {predictions.map((pred, index) => (
                        <div key={index} className="flex justify-between items-center p-2 border rounded">
                          <span className="text-sm">{new Date(pred.timestamp).toLocaleTimeString()}</span>
                          <span className="font-medium">{pred.predicted_value.toFixed(2)}</span>
                          <Badge variant="outline">{(pred.confidence * 100).toFixed(0)}% conf</Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card>
              <CardContent className="p-6">
                <p className="text-center text-muted-foreground">
                  No predictions available. Enable predictions and refresh data.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Anomalies Tab */}
        <TabsContent value="anomalies" className="space-y-4">
          {analyticsData?.anomalies && Object.keys(analyticsData.anomalies).length > 0 ? (
            <div className="space-y-4">
              {Object.entries(analyticsData.anomalies).map(([metric, anomalies]) => (
                <Card key={metric}>
                  <CardHeader>
                    <CardTitle>{metric} Anomalies</CardTitle>
                    <CardDescription>
                      Detected anomalies with confidence scores
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {anomalies.map((anomaly, index) => (
                        <div key={index} className="border rounded p-3">
                          <div className="flex justify-between items-start mb-2">
                            <div className="flex items-center space-x-2">
                              {renderSeverityBadge(anomaly.severity)}
                              <Badge variant="outline">{anomaly.type}</Badge>
                            </div>
                            <span className="text-sm text-muted-foreground">
                              {new Date(anomaly.timestamp).toLocaleString()}
                            </span>
                          </div>
                          <p className="text-sm mb-2">{anomaly.description}</p>
                          <div className="text-xs text-muted-foreground">
                            Value: {anomaly.value.toFixed(2)} | 
                            Expected: {anomaly.expected_value?.toFixed(2)} | 
                            Confidence: {(anomaly.confidence * 100).toFixed(0)}%
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card>
              <CardContent className="p-6">
                <p className="text-center text-muted-foreground">
                  No anomalies detected. Enable anomaly detection and refresh data.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Insights Tab */}
        <TabsContent value="insights" className="space-y-4">
          {insights.length > 0 ? (
            <div className="space-y-4">
              {insights.map((insight, index) => (
                <Card key={index}>
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <div>
                        <CardTitle className="text-lg">{insight.title}</CardTitle>
                        <CardDescription>{insight.description}</CardDescription>
                      </div>
                      <div className="flex items-center space-x-2">
                        {renderSeverityBadge(insight.type)}
                        <Badge variant="outline">
                          {(insight.confidence * 100).toFixed(0)}% confidence
                        </Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div>
                        <h4 className="text-sm font-medium mb-2">Recommendations:</h4>
                        <ul className="text-sm space-y-1">
                          {insight.recommendations.map((rec, recIndex) => (
                            <li key={recIndex} className="flex items-start">
                              <span className="mr-2">•</span>
                              <span>{rec}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      {Object.keys(insight.metrics).length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium mb-2">Related Metrics:</h4>
                          <div className="flex flex-wrap gap-2">
                            {Object.entries(insight.metrics).map(([key, value]) => (
                              <Badge key={key} variant="outline">
                                {key}: {typeof value === 'number' ? value.toFixed(2) : value}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card>
              <CardContent className="p-6">
                <p className="text-center text-muted-foreground">
                  No insights available for the selected time range.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default AdvancedAnalyticsDashboard;