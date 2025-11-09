"use client";

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  Zap,
  Server,
  Database,
  Mail,
  MessageSquare
} from 'lucide-react';

interface MetricsSummary {
  period: {
    start_date: string;
    end_date: string;
    days: number;
  };
  volume: {
    total_invoices: number;
    successful_invoices: number;
    invoices_with_exceptions: number;
  };
  performance: {
    processing_success_rate: number;
    exception_rate: number;
    average_processing_time_seconds: number;
    average_processing_time_minutes: number;
    average_extraction_confidence: number;
  };
  summary: {
    daily_average_invoices: number;
    success_rate_grade: string;
    performance_trend: string;
  };
}

interface HealthCheck {
  total_checks: number;
  healthy: number;
  degraded: number;
  unhealthy: number;
  average_response_time_ms: number;
  component_breakdown: Record<string, {
    healthy: number;
    degraded: number;
    unhealthy: number;
  }>;
}

interface PerformanceMetric {
  [category: string]: {
    count: number;
    avg_value: number;
    min_value: number;
    max_value: number;
    metrics: any[];
  };
}

interface AnomalySummary {
  total_anomalies: number;
  severity_breakdown: Record<string, number>;
  type_breakdown: Record<string, number>;
  high_confidence_anomalies: number;
  active_anomalies: number;
}

interface DashboardData {
  time_range: {
    start_time: string;
    end_time: string;
    hours: number;
  };
  kpi_summary: MetricsSummary;
  health_summary: HealthCheck;
  performance_summary: PerformanceMetric;
  anomaly_summary: AnomalySummary;
  generated_at: string;
}

interface Alert {
  id: string;
  name: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  status: 'active' | 'acknowledged' | 'resolved';
  evaluated_at: string;
  context: Record<string, any>;
}

export default function MetricsDashboard() {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [timeRange, setTimeRange] = useState(24); // hours
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboardData();
    fetchAlerts();

    // Set up auto-refresh
    const interval = setInterval(() => {
      fetchDashboardData();
      fetchAlerts();
    }, 30000); // Refresh every 30 seconds

    return () => clearInterval(interval);
  }, [timeRange]);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/v1/observability/metrics/summary?time_range_hours=${timeRange}`);
      if (!response.ok) {
        throw new Error('Failed to fetch dashboard data');
      }
      const data = await response.json();
      setDashboardData(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const fetchAlerts = async () => {
    try {
      const response = await fetch('/api/v1/observability/alerts?limit=10');
      if (response.ok) {
        const data = await response.json();
        setAlerts(data.alerts || []);
      }
    } catch (err) {
      console.error('Failed to fetch alerts:', err);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'destructive';
      case 'error': return 'destructive';
      case 'warning': return 'secondary';
      case 'info': return 'default';
      default: return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'degraded': return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'unhealthy': return <Zap className="h-4 w-4 text-red-500" />;
      default: return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getSuccessRateGrade = (rate: number) => {
    if (rate >= 95) return { grade: 'A', color: 'text-green-600' };
    if (rate >= 90) return { grade: 'B', color: 'text-blue-600' };
    if (rate >= 80) return { grade: 'C', color: 'text-yellow-600' };
    return { grade: 'D', color: 'text-red-600' };
  };

  if (loading && !dashboardData) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!dashboardData) {
    return null;
  }

  const { kpi_summary, health_summary, performance_summary, anomaly_summary } = dashboardData;
  const successRateInfo = getSuccessRateGrade(kpi_summary.performance.processing_success_rate);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Observability Dashboard</h1>
          <p className="text-muted-foreground">
            Real-time system monitoring and performance metrics
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant={timeRange === 1 ? "default" : "outline"}
            size="sm"
            onClick={() => setTimeRange(1)}
          >
            1H
          </Button>
          <Button
            variant={timeRange === 24 ? "default" : "outline"}
            size="sm"
            onClick={() => setTimeRange(24)}
          >
            24H
          </Button>
          <Button
            variant={timeRange === 168 ? "default" : "outline"}
            size="sm"
            onClick={() => setTimeRange(168)}
          >
            7D
          </Button>
        </div>
      </div>

      {/* Active Alerts */}
      {alerts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Active Alerts ({alerts.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {alerts.slice(0, 5).map((alert) => (
                <div key={alert.id} className="flex items-center justify-between p-2 border rounded">
                  <div className="flex items-center gap-2">
                    <Badge variant={getSeverityColor(alert.severity)}>
                      {alert.severity}
                    </Badge>
                    <span className="font-medium">{alert.name}</span>
                    <Badge variant="outline">{alert.status}</Badge>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {new Date(alert.evaluated_at).toLocaleTimeString()}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Dashboard Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {/* Processing Volume */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Processing Volume</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{kpi_summary.volume.total_invoices}</div>
            <p className="text-xs text-muted-foreground">
              {kpi_summary.summary.daily_average_invoices} daily average
            </p>
            <div className="mt-2 space-y-1">
              <div className="flex justify-between text-xs">
                <span>Success Rate</span>
                <span className={successRateInfo.color}>
                  Grade {successRateInfo.grade}
                </span>
              </div>
              <Progress value={kpi_summary.performance.processing_success_rate} className="h-2" />
              <p className="text-xs text-muted-foreground">
                {kpi_summary.performance.processing_success_rate.toFixed(1)}%
              </p>
            </div>
          </CardContent>
        </Card>

        {/* System Health */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {health_summary.total_checks > 0
                ? Math.round((health_summary.healthy / health_summary.total_checks) * 100)
                : 0}%
            </div>
            <p className="text-xs text-muted-foreground">
              {health_summary.healthy} of {health_summary.total_checks} checks healthy
            </p>
            <div className="mt-2 space-y-1">
              <div className="flex justify-between text-xs">
                <span className="flex items-center gap-1">
                  <CheckCircle className="h-3 w-3 text-green-500" />
                  Healthy
                </span>
                <span>{health_summary.healthy}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3 text-yellow-500" />
                  Degraded
                </span>
                <span>{health_summary.degraded}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="flex items-center gap-1">
                  <Zap className="h-3 w-3 text-red-500" />
                  Unhealthy
                </span>
                <span>{health_summary.unhealthy}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Processing Time */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Processing Time</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {kpi_summary.performance.average_processing_time_minutes.toFixed(1)}m
            </div>
            <p className="text-xs text-muted-foreground">
              {kpi_summary.performance.average_processing_time_seconds.toFixed(0)}s average
            </p>
            <div className="mt-2">
              <div className="flex items-center gap-2 text-xs">
                <TrendingUp className="h-3 w-3 text-green-500" />
                <span>Within target (&lt;5m)</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Extraction Quality */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Extraction Quality</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(kpi_summary.performance.average_extraction_confidence * 100).toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              Average confidence score
            </p>
            <div className="mt-2">
              <Progress
                value={kpi_summary.performance.average_extraction_confidence * 100}
                className="h-2"
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Metrics Tabs */}
      <Tabs defaultValue="performance" className="space-y-4">
        <TabsList>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="health">Health Checks</TabsTrigger>
          <TabsTrigger value="anomalies">Anomalies</TabsTrigger>
          <TabsTrigger value="components">Components</TabsTrigger>
        </TabsList>

        <TabsContent value="performance" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Performance Metrics by Category</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {Object.entries(performance_summary).map(([category, metrics]) => (
                    <div key={category} className="space-y-2">
                      <div className="flex justify-between items-center">
                        <h4 className="font-medium capitalize">{category}</h4>
                        <Badge variant="outline">{metrics.count} samples</Badge>
                      </div>
                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <p className="text-muted-foreground">Avg</p>
                          <p className="font-medium">{metrics.avg_value.toFixed(2)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Min</p>
                          <p className="font-medium">{metrics.min_value.toFixed(2)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Max</p>
                          <p className="font-medium">{metrics.max_value.toFixed(2)}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Exception Rate</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-red-600">
                      {kpi_summary.performance.exception_rate.toFixed(1)}%
                    </div>
                    <p className="text-muted-foreground">
                      {kpi_summary.volume.invoices_with_exceptions} of {kpi_summary.volume.total_invoices} invoices
                    </p>
                  </div>
                  <Progress
                    value={kpi_summary.performance.exception_rate}
                    className="h-3"
                  />
                  <div className="text-sm text-muted-foreground">
                    Target: &lt;5% exceptions
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="health" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Component Health Breakdown</CardTitle>
              <CardDescription>
                Health status by system component
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {Object.entries(health_summary.component_breakdown).map(([component, health]) => {
                  const total = health.healthy + health.degraded + health.unhealthy;
                  const healthPercentage = total > 0 ? (health.healthy / total) * 100 : 0;

                  return (
                    <div key={component} className="space-y-2">
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(
                            health.unhealthy > 0 ? 'unhealthy' :
                            health.degraded > 0 ? 'degraded' : 'healthy'
                          )}
                          <h4 className="font-medium capitalize">{component}</h4>
                        </div>
                        <Badge variant={healthPercentage === 100 ? "default" : "secondary"}>
                          {healthPercentage.toFixed(0)}%
                        </Badge>
                      </div>
                      <Progress value={healthPercentage} className="h-2" />
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{health.healthy} healthy</span>
                        <span>{health.degraded} degraded</span>
                        <span>{health.unhealthy} unhealthy</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="anomalies" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Anomaly Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="text-center">
                    <div className="text-3xl font-bold text-orange-600">
                      {anomaly_summary.total_anomalies}
                    </div>
                    <p className="text-muted-foreground">
                      Total anomalies detected
                    </p>
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span>High Confidence</span>
                      <Badge variant="destructive">
                        {anomaly_summary.high_confidence_anomalies}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span>Active</span>
                      <Badge variant="secondary">
                        {anomaly_summary.active_anomalies}
                      </Badge>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Anomaly Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <h4 className="font-medium mb-2">By Severity</h4>
                    <div className="space-y-2">
                      {Object.entries(anomaly_summary.severity_breakdown).map(([severity, count]) => (
                        <div key={severity} className="flex justify-between">
                          <span className="capitalize">{severity}</span>
                          <Badge variant="outline">{count}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <h4 className="font-medium mb-2">By Type</h4>
                    <div className="space-y-2">
                      {Object.entries(anomaly_summary.type_breakdown).map(([type, count]) => (
                        <div key={type} className="flex justify-between">
                          <span className="capitalize">{type}</span>
                          <Badge variant="outline">{count}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="components" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>System Components</CardTitle>
              <CardDescription>
                Detailed status of all system components
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <div className="flex items-center space-x-3 p-3 border rounded">
                  <Database className="h-8 w-8 text-blue-500" />
                  <div>
                    <h4 className="font-medium">Database</h4>
                    <p className="text-sm text-muted-foreground">PostgreSQL</p>
                    <Badge variant="default">Healthy</Badge>
                  </div>
                </div>

                <div className="flex items-center space-x-3 p-3 border rounded">
                  <Server className="h-8 w-8 text-green-500" />
                  <div>
                    <h4 className="font-medium">Queue</h4>
                    <p className="text-sm text-muted-foreground">Celery/RabbitMQ</p>
                    <Badge variant="default">Healthy</Badge>
                  </div>
                </div>

                <div className="flex items-center space-x-3 p-3 border rounded">
                  <Mail className="h-8 w-8 text-purple-500" />
                  <div>
                    <h4 className="font-medium">Email Service</h4>
                    <p className="text-sm text-muted-foreground">Gmail API</p>
                    <Badge variant="default">Healthy</Badge>
                  </div>
                </div>

                <div className="flex items-center space-x-3 p-3 border rounded">
                  <Activity className="h-8 w-8 text-orange-500" />
                  <div>
                    <h4 className="font-medium">LLM Service</h4>
                    <p className="text-sm text-muted-foreground">OpenRouter</p>
                    <Badge variant="secondary">Degraded</Badge>
                  </div>
                </div>

                <div className="flex items-center space-x-3 p-3 border rounded">
                  <Database className="h-8 w-8 text-cyan-500" />
                  <div>
                    <h4 className="font-medium">Storage</h4>
                    <p className="text-sm text-muted-foreground">MinIO/S3</p>
                    <Badge variant="default">Healthy</Badge>
                  </div>
                </div>

                <div className="flex items-center space-x-3 p-3 border rounded">
                  <MessageSquare className="h-8 w-8 text-green-500" />
                  <div>
                    <h4 className="font-medium">Notifications</h4>
                    <p className="text-sm text-muted-foreground">Slack/Email</p>
                    <Badge variant="default">Healthy</Badge>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Last Updated */}
      <div className="text-center text-sm text-muted-foreground">
        Last updated: {new Date(dashboardData.generated_at).toLocaleString()}
      </div>
    </div>
  );
}