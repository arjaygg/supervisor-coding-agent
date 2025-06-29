/**
 * Plugin Management Dashboard Component
 * 
 * Comprehensive interface for managing the plugin system including loading,
 * activating, configuring, and monitoring plugins as part of Phase 1.3.
 * 
 * Features:
 * - Plugin lifecycle management (load, activate, deactivate, unload)
 * - Real-time status monitoring and health checks
 * - Configuration management with validation
 * - Event system integration and history
 * - Performance metrics and analytics
 * - Notification testing and management
 */

import React, { useState, useEffect, useCallback } from 'react';
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { 
  RefreshCw,
  Play,
  Pause,
  Trash2,
  Settings,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Activity,
  Zap,
  MessageSquare,
  Eye,
  Download
} from 'lucide-react';

interface Plugin {
  name: string;
  version: string;
  description: string;
  author: string;
  plugin_type: string;
  status: string;
  dependencies: string[];
  permissions: string[];
  tags: string[];
  load_time?: string;
  last_activity?: string;
  error_count: number;
  performance_metrics: Record<string, any>;
}

interface PluginConfiguration {
  enabled: boolean;
  auto_start: boolean;
  configuration: Record<string, any>;
  permissions: string[];
  resource_limits: Record<string, any>;
  retry_policy: Record<string, any>;
}

interface PluginEvent {
  event_id: string;
  event_type: string;
  source_plugin?: string;
  target_plugin?: string;
  timestamp: string;
  data: Record<string, any>;
  metadata: Record<string, any>;
}

interface HealthResult {
  plugin_name: string;
  healthy: boolean;
  data?: any;
  error?: string;
  checked_at: string;
}

const PluginManagementDashboard: React.FC = () => {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [selectedPlugin, setSelectedPlugin] = useState<Plugin | null>(null);
  const [pluginConfig, setPluginConfig] = useState<PluginConfiguration | null>(null);
  const [events, setEvents] = useState<PluginEvent[]>([]);
  const [healthResults, setHealthResults] = useState<Record<string, HealthResult>>({});
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [configDialogOpen, setConfigDialogOpen] = useState<boolean>(false);
  const [notificationDialogOpen, setNotificationDialogOpen] = useState<boolean>(false);
  
  // Notification form state
  const [notificationForm, setNotificationForm] = useState({
    plugin_name: '',
    recipient: '',
    subject: '',
    message: '',
    priority: 'normal'
  });

  // Fetch plugins
  const fetchPlugins = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const params = new URLSearchParams();
      if (filterType !== 'all') params.append('plugin_type', filterType);
      if (filterStatus !== 'all') params.append('status', filterStatus);
      
      const response = await fetch(`/api/v1/plugins?${params}`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch plugins: ${response.statusText}`);
      }

      const data: Plugin[] = await response.json();
      setPlugins(data);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to fetch plugins');
      console.error('Plugin fetch error:', error);
    } finally {
      setIsLoading(false);
    }
  }, [filterType, filterStatus]);

  // Fetch plugin configuration
  const fetchPluginConfiguration = async (pluginName: string) => {
    try {
      const response = await fetch(`/api/v1/plugins/${pluginName}/configuration`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch configuration: ${response.statusText}`);
      }

      const data = await response.json();
      setPluginConfig(data);
    } catch (error) {
      console.error('Failed to fetch plugin configuration:', error);
    }
  };

  // Fetch events
  const fetchEvents = async (eventType?: string) => {
    try {
      const params = new URLSearchParams({ limit: '50' });
      if (eventType) params.append('event_type', eventType);
      
      const response = await fetch(`/api/v1/plugins/events/history?${params}`);
      
      if (response.ok) {
        const data = await response.json();
        setEvents(data.events || []);
      }
    } catch (error) {
      console.error('Failed to fetch events:', error);
    }
  };

  // Check health of all plugins
  const checkAllHealth = async () => {
    try {
      const response = await fetch('/api/v1/plugins/health/all');
      
      if (response.ok) {
        const data = await response.json();
        setHealthResults(data.results || {});
      }
    } catch (error) {
      console.error('Failed to check plugin health:', error);
    }
  };

  // Plugin actions
  const activatePlugin = async (pluginName: string) => {
    try {
      const response = await fetch(`/api/v1/plugins/${pluginName}/activate`, {
        method: 'POST'
      });
      
      if (response.ok) {
        await fetchPlugins();
      } else {
        throw new Error(`Failed to activate plugin: ${response.statusText}`);
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to activate plugin');
    }
  };

  const deactivatePlugin = async (pluginName: string) => {
    try {
      const response = await fetch(`/api/v1/plugins/${pluginName}/deactivate`, {
        method: 'POST'
      });
      
      if (response.ok) {
        await fetchPlugins();
      } else {
        throw new Error(`Failed to deactivate plugin: ${response.statusText}`);
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to deactivate plugin');
    }
  };

  const unloadPlugin = async (pluginName: string) => {
    try {
      const response = await fetch(`/api/v1/plugins/${pluginName}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        await fetchPlugins();
      } else {
        throw new Error(`Failed to unload plugin: ${response.statusText}`);
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to unload plugin');
    }
  };

  // Update plugin configuration
  const updatePluginConfiguration = async () => {
    if (!selectedPlugin || !pluginConfig) return;
    
    try {
      const response = await fetch(`/api/v1/plugins/${selectedPlugin.name}/configuration`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(pluginConfig)
      });
      
      if (response.ok) {
        setConfigDialogOpen(false);
        setPluginConfig(null);
        await fetchPlugins();
      } else {
        throw new Error('Failed to update configuration');
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to update configuration');
    }
  };

  // Send notification
  const sendNotification = async () => {
    try {
      const response = await fetch('/api/v1/plugins/notifications/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(notificationForm)
      });
      
      if (response.ok) {
        setNotificationDialogOpen(false);
        setNotificationForm({
          plugin_name: '',
          recipient: '',
          subject: '',
          message: '',
          priority: 'normal'
        });
      } else {
        throw new Error('Failed to send notification');
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to send notification');
    }
  };

  // Effects
  useEffect(() => {
    fetchPlugins();
  }, [fetchPlugins]);

  useEffect(() => {
    fetchEvents();
    checkAllHealth();
    
    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      checkAllHealth();
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);

  // Render status badge
  const renderStatusBadge = (status: string) => {
    const statusColors = {
      active: 'default',
      inactive: 'secondary',
      loaded: 'outline',
      error: 'destructive',
      unloaded: 'secondary'
    };
    
    return (
      <Badge variant={statusColors[status as keyof typeof statusColors] || 'outline'}>
        {status}
      </Badge>
    );
  };

  // Render health indicator
  const renderHealthIndicator = (pluginName: string) => {
    const health = healthResults[pluginName];
    if (!health) return <XCircle className="h-4 w-4 text-gray-400" />;
    
    return health.healthy ? (
      <CheckCircle className="h-4 w-4 text-green-500" />
    ) : (
      <XCircle className="h-4 w-4 text-red-500" />
    );
  };

  // Render plugin card
  const renderPluginCard = (plugin: Plugin) => (
    <Card key={plugin.name} className="w-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div>
          <CardTitle className="text-lg">{plugin.name}</CardTitle>
          <CardDescription>{plugin.description}</CardDescription>
        </div>
        <div className="flex items-center space-x-2">
          {renderHealthIndicator(plugin.name)}
          {renderStatusBadge(plugin.status)}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Version:</span>
            <span>{plugin.version}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Type:</span>
            <Badge variant="outline">{plugin.plugin_type}</Badge>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Author:</span>
            <span>{plugin.author}</span>
          </div>
          {plugin.error_count > 0 && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Errors:</span>
              <Badge variant="destructive">{plugin.error_count}</Badge>
            </div>
          )}
          
          {/* Plugin Actions */}
          <div className="flex space-x-2 pt-2">
            {plugin.status === 'loaded' && (
              <Button 
                size="sm" 
                onClick={() => activatePlugin(plugin.name)}
                disabled={isLoading}
              >
                <Play className="h-3 w-3 mr-1" />
                Activate
              </Button>
            )}
            {plugin.status === 'active' && (
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => deactivatePlugin(plugin.name)}
                disabled={isLoading}
              >
                <Pause className="h-3 w-3 mr-1" />
                Deactivate
              </Button>
            )}
            <Button 
              size="sm" 
              variant="outline"
              onClick={() => {
                setSelectedPlugin(plugin);
                fetchPluginConfiguration(plugin.name);
                setConfigDialogOpen(true);
              }}
            >
              <Settings className="h-3 w-3 mr-1" />
              Config
            </Button>
            <Button 
              size="sm" 
              variant="destructive"
              onClick={() => unloadPlugin(plugin.name)}
              disabled={isLoading}
            >
              <Trash2 className="h-3 w-3 mr-1" />
              Unload
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold">Plugin Management</h2>
          <p className="text-muted-foreground">
            Manage and monitor system plugins
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button onClick={fetchPlugins} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={checkAllHealth}>
            <Activity className="h-4 w-4 mr-2" />
            Health Check
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center space-x-4">
        <Select value={filterType} onValueChange={setFilterType}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Filter by type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="task_processor">Task Processor</SelectItem>
            <SelectItem value="data_source">Data Source</SelectItem>
            <SelectItem value="notification">Notification</SelectItem>
            <SelectItem value="analytics">Analytics</SelectItem>
            <SelectItem value="integration">Integration</SelectItem>
          </SelectContent>
        </Select>

        <Select value={filterStatus} onValueChange={setFilterStatus}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
            <SelectItem value="loaded">Loaded</SelectItem>
            <SelectItem value="error">Error</SelectItem>
          </SelectContent>
        </Select>

        <Dialog open={notificationDialogOpen} onOpenChange={setNotificationDialogOpen}>
          <DialogTrigger asChild>
            <Button variant="outline">
              <MessageSquare className="h-4 w-4 mr-2" />
              Test Notification
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle>Send Test Notification</DialogTitle>
              <DialogDescription>
                Send a test notification through a notification plugin
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label htmlFor="plugin_name">Plugin</Label>
                <Select 
                  value={notificationForm.plugin_name} 
                  onValueChange={(value) => setNotificationForm({...notificationForm, plugin_name: value})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select notification plugin" />
                  </SelectTrigger>
                  <SelectContent>
                    {plugins
                      .filter(p => p.plugin_type === 'notification' && p.status === 'active')
                      .map(p => (
                        <SelectItem key={p.name} value={p.name}>{p.name}</SelectItem>
                      ))
                    }
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="recipient">Recipient</Label>
                <Input
                  id="recipient"
                  value={notificationForm.recipient}
                  onChange={(e) => setNotificationForm({...notificationForm, recipient: e.target.value})}
                  placeholder="Channel or user"
                />
              </div>
              <div>
                <Label htmlFor="subject">Subject</Label>
                <Input
                  id="subject"
                  value={notificationForm.subject}
                  onChange={(e) => setNotificationForm({...notificationForm, subject: e.target.value})}
                  placeholder="Notification subject"
                />
              </div>
              <div>
                <Label htmlFor="message">Message</Label>
                <Textarea
                  id="message"
                  value={notificationForm.message}
                  onChange={(e) => setNotificationForm({...notificationForm, message: e.target.value})}
                  placeholder="Notification message"
                />
              </div>
              <div>
                <Label htmlFor="priority">Priority</Label>
                <Select 
                  value={notificationForm.priority} 
                  onValueChange={(value) => setNotificationForm({...notificationForm, priority: value})}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="normal">Normal</SelectItem>
                    <SelectItem value="warning">Warning</SelectItem>
                    <SelectItem value="critical">Critical</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={sendNotification} className="w-full">
                Send Notification
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Main Content */}
      <Tabs defaultValue="plugins" className="space-y-4">
        <TabsList>
          <TabsTrigger value="plugins">Plugins</TabsTrigger>
          <TabsTrigger value="events">Events</TabsTrigger>
          <TabsTrigger value="health">Health Status</TabsTrigger>
        </TabsList>

        {/* Plugins Tab */}
        <TabsContent value="plugins" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {plugins.map(renderPluginCard)}
          </div>
          
          {plugins.length === 0 && !isLoading && (
            <div className="text-center py-8">
              <p className="text-muted-foreground">No plugins found matching the current filters.</p>
            </div>
          )}
        </TabsContent>

        {/* Events Tab */}
        <TabsContent value="events" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Plugin Events</CardTitle>
              <CardDescription>Recent plugin system events</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {events.map((event, index) => (
                  <div key={event.event_id || index} className="border rounded p-3">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center space-x-2">
                        <Badge variant="outline">{event.event_type}</Badge>
                        {event.source_plugin && (
                          <Badge variant="secondary">{event.source_plugin}</Badge>
                        )}
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {new Date(event.timestamp).toLocaleString()}
                      </span>
                    </div>
                    {Object.keys(event.data).length > 0 && (
                      <div className="text-sm">
                        <strong>Data:</strong> {JSON.stringify(event.data, null, 2)}
                      </div>
                    )}
                  </div>
                ))}
                {events.length === 0 && (
                  <p className="text-center text-muted-foreground py-4">
                    No events found
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Health Status Tab */}
        <TabsContent value="health" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Object.entries(healthResults).map(([pluginName, health]) => (
              <Card key={pluginName}>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-lg">{pluginName}</CardTitle>
                  {renderHealthIndicator(pluginName)}
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Status:</span>
                      <Badge variant={health.healthy ? "default" : "destructive"}>
                        {health.healthy ? "Healthy" : "Unhealthy"}
                      </Badge>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-muted-foreground">Checked:</span>
                      <span className="text-sm">
                        {new Date(health.checked_at).toLocaleTimeString()}
                      </span>
                    </div>
                    {health.error && (
                      <div className="text-sm text-red-600">
                        <strong>Error:</strong> {health.error}
                      </div>
                    )}
                    {health.data && (
                      <details className="text-sm">
                        <summary className="cursor-pointer">Health Data</summary>
                        <pre className="mt-2 text-xs bg-gray-100 p-2 rounded">
                          {JSON.stringify(health.data, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      {/* Configuration Dialog */}
      <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
        <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Configure {selectedPlugin?.name}
            </DialogTitle>
            <DialogDescription>
              Update plugin configuration and settings
            </DialogDescription>
          </DialogHeader>
          {pluginConfig && (
            <div className="space-y-4">
              <div className="flex items-center space-x-2">
                <Switch
                  checked={pluginConfig.enabled}
                  onCheckedChange={(checked) => 
                    setPluginConfig({...pluginConfig, enabled: checked})
                  }
                />
                <Label>Enabled</Label>
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  checked={pluginConfig.auto_start}
                  onCheckedChange={(checked) => 
                    setPluginConfig({...pluginConfig, auto_start: checked})
                  }
                />
                <Label>Auto Start</Label>
              </div>
              <div>
                <Label>Configuration (JSON)</Label>
                <Textarea
                  value={JSON.stringify(pluginConfig.configuration, null, 2)}
                  onChange={(e) => {
                    try {
                      const parsed = JSON.parse(e.target.value);
                      setPluginConfig({...pluginConfig, configuration: parsed});
                    } catch (error) {
                      // Invalid JSON, ignore
                    }
                  }}
                  rows={10}
                />
              </div>
              <Button onClick={updatePluginConfiguration} className="w-full">
                Update Configuration
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PluginManagementDashboard;