"use client";

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Play,
  Square,
  RotateCcw,
  AlertTriangle,
  CheckCircle,
  Clock,
  Zap,
  BookOpen,
  Terminal,
  Activity,
  Pause,
  Eye,
  MessageSquare
} from 'lucide-react';

interface Runbook {
  id: string;
  name: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  category: string;
  triggers: string[];
  total_steps: number;
  requires_approval: boolean;
  max_execution_time_minutes: number;
  metadata: Record<string, any>;
}

interface RunbookExecution {
  id: string;
  runbook_id: string;
  runbook_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'paused';
  current_step: string | null;
  total_steps: number;
  completed_steps: number;
  failed_steps: number;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
  triggered_by: string;
  metadata: Record<string, any>;
}

interface StepExecution {
  id: string;
  step_id: string;
  step_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  action_type: 'command' | 'api_call' | 'script' | 'manual';
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  result: any;
  error_message: string | null;
  retry_count: number;
  max_retries: number;
  dependencies: string[];
  parallel: boolean;
  metadata: Record<string, any>;
}

export default function RunbookExecutor() {
  const [runbooks, setRunbooks] = useState<Runbook[]>([]);
  const [executions, setExecutions] = useState<RunbookExecution[]>([]);
  const [selectedExecution, setSelectedExecution] = useState<RunbookExecution | null>(null);
  const [stepExecutions, setStepExecutions] = useState<StepExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [executeDialogOpen, setExecuteDialogOpen] = useState(false);
  const [selectedRunbook, setSelectedRunbook] = useState<Runbook | null>(null);
  const [triggerContext, setTriggerContext] = useState('');
  const [cancellingExecution, setCancellingExecution] = useState<string | null>(null);

  useEffect(() => {
    fetchRunbooks();
    fetchExecutions();

    // Set up auto-refresh for running executions
    const interval = setInterval(() => {
      fetchExecutions();
    }, 5000); // Refresh every 5 seconds

    return () => clearInterval(interval);
  }, []);

  const fetchRunbooks = async () => {
    try {
      const response = await fetch('/api/v1/observability/runbooks');
      if (!response.ok) throw new Error('Failed to fetch runbooks');
      const data = await response.json();
      setRunbooks(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load runbooks');
    }
  };

  const fetchExecutions = async () => {
    try {
      const response = await fetch('/api/v1/observability/runbooks/executions?limit=20');
      if (!response.ok) throw new Error('Failed to fetch executions');
      const data = await response.json();
      setExecutions(data.executions);
      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load executions');
      setLoading(false);
    }
  };

  const fetchExecutionDetails = async (executionId: string) => {
    try {
      const response = await fetch(`/api/v1/observability/runbooks/executions/${executionId}`);
      if (!response.ok) throw new Error('Failed to fetch execution details');
      const data = await response.json();
      setSelectedExecution(data.execution);
      setStepExecutions(data.step_executions);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load execution details');
    }
  };

  const executeRunbook = async (runbookId: string, context: Record<string, any>) => {
    try {
      const response = await fetch(`/api/v1/observability/runbooks/${runbookId}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trigger_context: context })
      });

      if (!response.ok) throw new Error('Failed to execute runbook');

      const data = await response.json();
      setExecuteDialogOpen(false);
      setTriggerContext('');
      setSelectedRunbook(null);

      // Refresh executions
      fetchExecutions();

      // Show success message
      alert(`Runbook execution started: ${data.execution_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to execute runbook');
    }
  };

  const cancelExecution = async (executionId: string) => {
    try {
      setCancellingExecution(executionId);
      const reason = 'Cancelled by user via dashboard';
      const response = await fetch(`/api/v1/observability/runbooks/executions/${executionId}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason })
      });

      if (!response.ok) throw new Error('Failed to cancel execution');

      // Refresh executions
      fetchExecutions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel execution');
    } finally {
      setCancellingExecution(null);
    }
  };

  const executeEmergencyDrill = async (drillType: string) => {
    try {
      const response = await fetch('/api/v1/observability/emergency-drill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          drill_type,
          execution_context: { initiated_via: 'dashboard' }
        })
      });

      if (!response.ok) throw new Error('Failed to execute emergency drill');

      const data = await response.json();
      alert(`Emergency drill started: ${data.execution_id}`);
      fetchExecutions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to execute emergency drill');
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'destructive';
      case 'high': return 'destructive';
      case 'medium': return 'secondary';
      case 'low': return 'default';
      default: return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'running': return <Activity className="h-4 w-4 text-blue-500" />;
      case 'failed': return <AlertTriangle className="h-4 w-4 text-red-500" />;
      case 'cancelled': return <Square className="h-4 w-4 text-gray-500" />;
      case 'paused': return <Pause className="h-4 w-4 text-yellow-500" />;
      default: return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStepIcon = (actionType: string) => {
    switch (actionType) {
      case 'command': return <Terminal className="h-4 w-4" />;
      case 'api_call': return <Activity className="h-4 w-4" />;
      case 'script': return <BookOpen className="h-4 w-4" />;
      case 'manual': return <MessageSquare className="h-4 w-4" />;
      default: return <Clock className="h-4 w-4" />;
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const emergencyDrills = [
    { id: 'export_rollback', name: 'Export Rollback', description: 'Test staged export rollback procedures' },
    { id: 'dlq_recovery', name: 'DLQ Recovery', description: 'Test dead letter queue recovery' },
    { id: 'invoice_recovery', name: 'Invoice Recovery', description: 'Test failed invoice recovery procedures' },
    { id: 'performance_degradation', name: 'Performance Degradation', description: 'Test performance issue response' },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Runbook Executor</h1>
          <p className="text-muted-foreground">
            Execute and monitor automated recovery procedures
          </p>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="runbooks" className="space-y-4">
        <TabsList>
          <TabsTrigger value="runbooks">Available Runbooks</TabsTrigger>
          <TabsTrigger value="executions">Active Executions</TabsTrigger>
          <TabsTrigger value="emergency-drills">Emergency Drills</TabsTrigger>
          <TabsTrigger value="history">Execution History</TabsTrigger>
        </TabsList>

        <TabsContent value="runbooks" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {runbooks.map((runbook) => (
              <Card key={runbook.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{runbook.name}</CardTitle>
                    <Badge variant={getSeverityColor(runbook.severity)}>
                      {runbook.severity}
                    </Badge>
                  </div>
                  <CardDescription>{runbook.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span>Category:</span>
                      <Badge variant="outline">{runbook.category}</Badge>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span>Steps:</span>
                      <span>{runbook.total_steps}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span>Max Duration:</span>
                      <span>{runbook.max_execution_time_minutes}m</span>
                    </div>
                    {runbook.requires_approval && (
                      <div className="flex items-center gap-2 text-sm text-yellow-600">
                        <AlertTriangle className="h-4 w-4" />
                        <span>Requires approval</span>
                      </div>
                    )}
                    <div className="flex gap-2">
                      <Dialog open={executeDialogOpen && selectedRunbook?.id === runbook.id} onOpenChange={(open) => {
                        setExecuteDialogOpen(open);
                        if (!open) setSelectedRunbook(null);
                      }}>
                        <DialogTrigger asChild>
                          <Button
                            size="sm"
                            onClick={() => setSelectedRunbook(runbook)}
                            className="flex-1"
                          >
                            <Play className="h-4 w-4 mr-2" />
                            Execute
                          </Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>Execute Runbook: {runbook.name}</DialogTitle>
                            <DialogDescription>
                              This will start the automated execution of the runbook. Please provide any additional context for the execution.
                            </DialogDescription>
                          </DialogHeader>
                          <div className="space-y-4">
                            <div>
                              <Label htmlFor="context">Execution Context (JSON)</Label>
                              <Textarea
                                id="context"
                                placeholder='{"reason": "Manual execution", "scope": "production"}'
                                value={triggerContext}
                                onChange={(e) => setTriggerContext(e.target.value)}
                                rows={4}
                              />
                            </div>
                          </div>
                          <DialogFooter>
                            <Button variant="outline" onClick={() => {
                              setExecuteDialogOpen(false);
                              setSelectedRunbook(null);
                              setTriggerContext('');
                            }}>
                              Cancel
                            </Button>
                            <Button
                              onClick={() => {
                                let context = {};
                                try {
                                  context = triggerContext ? JSON.parse(triggerContext) : {};
                                } catch (e) {
                                  context = { note: triggerContext };
                                }
                                executeRunbook(runbook.id, context);
                              }}
                            >
                              Execute Runbook
                            </Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="executions" className="space-y-4">
          <div className="grid gap-4">
            {executions
              .filter(execution => execution.status === 'running' || execution.status === 'pending')
              .map((execution) => (
                <Card key={execution.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(execution.status)}
                        <CardTitle className="text-lg">{execution.runbook_name}</CardTitle>
                        <Badge variant="outline">{execution.status}</Badge>
                      </div>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => cancelExecution(execution.id)}
                        disabled={cancellingExecution === execution.id}
                      >
                        {cancellingExecution === execution.id ? (
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        ) : (
                          <Square className="h-4 w-4 mr-2" />
                        )}
                        Cancel
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="text-muted-foreground">Progress:</span>
                          <div className="flex items-center gap-2 mt-1">
                            <Progress
                              value={(execution.completed_steps / execution.total_steps) * 100}
                              className="flex-1"
                            />
                            <span className="font-medium">
                              {execution.completed_steps}/{execution.total_steps}
                            </span>
                          </div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Current Step:</span>
                          <p className="font-medium truncate">
                            {execution.current_step || 'Initializing...'}
                          </p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Duration:</span>
                          <p className="font-medium">
                            {formatDuration(execution.duration_seconds)}
                          </p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Triggered By:</span>
                          <p className="font-medium truncate">
                            {execution.triggered_by}
                          </p>
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => fetchExecutionDetails(execution.id)}
                        >
                          <Eye className="h-4 w-4 mr-2" />
                          View Details
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
          </div>

          {executions.filter(execution => execution.status === 'running' || execution.status === 'pending').length === 0 && (
            <Card>
              <CardContent className="flex items-center justify-center h-32">
                <div className="text-center text-muted-foreground">
                  <Activity className="h-8 w-8 mx-auto mb-2" />
                  <p>No active executions</p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="emergency-drills" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Emergency Drills</CardTitle>
              <CardDescription>
                Execute 2-minute emergency drills to test response procedures
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                {emergencyDrills.map((drill) => (
                  <Card key={drill.id}>
                    <CardHeader>
                      <CardTitle className="text-lg flex items-center gap-2">
                        <Zap className="h-5 w-5 text-orange-500" />
                        {drill.name}
                      </CardTitle>
                      <CardDescription>{drill.description}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Button
                        onClick={() => executeEmergencyDrill(drill.id)}
                        className="w-full"
                        variant="outline"
                      >
                        <Play className="h-4 w-4 mr-2" />
                        Start Drill
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
          <div className="grid gap-4">
            {executions.map((execution) => (
              <Card key={execution.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(execution.status)}
                      <CardTitle className="text-lg">{execution.runbook_name}</CardTitle>
                      <Badge variant="outline">{execution.status}</Badge>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => fetchExecutionDetails(execution.id)}
                      >
                        <Eye className="h-4 w-4 mr-2" />
                        View Details
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Started:</span>
                      <p className="font-medium">
                        {new Date(execution.started_at).toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Duration:</span>
                      <p className="font-medium">
                        {formatDuration(execution.duration_seconds)}
                      </p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Progress:</span>
                      <p className="font-medium">
                        {execution.completed_steps}/{execution.total_steps}
                      </p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Status:</span>
                      <p className="font-medium capitalize">{execution.status}</p>
                    </div>
                  </div>
                  {execution.error_message && (
                    <Alert className="mt-3">
                      <AlertTriangle className="h-4 w-4" />
                      <AlertTitle>Execution Error</AlertTitle>
                      <AlertDescription>{execution.error_message}</AlertDescription>
                    </Alert>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>

          {executions.length === 0 && (
            <Card>
              <CardContent className="flex items-center justify-center h-32">
                <div className="text-center text-muted-foreground">
                  <BookOpen className="h-8 w-8 mx-auto mb-2" />
                  <p>No execution history</p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* Execution Details Modal */}
      {selectedExecution && (
        <Dialog open={!!selectedExecution} onOpenChange={() => setSelectedExecution(null)}>
          <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                {getStatusIcon(selectedExecution.status)}
                {selectedExecution.runbook_name}
                <Badge variant="outline">{selectedExecution.status}</Badge>
              </DialogTitle>
              <DialogDescription>
                Execution details and step-by-step progress
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              {/* Execution Summary */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <Label>Execution ID</Label>
                  <p className="text-sm font-mono">{selectedExecution.id.slice(0, 8)}...</p>
                </div>
                <div>
                  <Label>Started</Label>
                  <p className="text-sm">{new Date(selectedExecution.started_at).toLocaleString()}</p>
                </div>
                <div>
                  <Label>Duration</Label>
                  <p className="text-sm">{formatDuration(selectedExecution.duration_seconds)}</p>
                </div>
                <div>
                  <Label>Triggered By</Label>
                  <p className="text-sm">{selectedExecution.triggered_by}</p>
                </div>
              </div>

              {/* Progress */}
              <div>
                <Label>Progress</Label>
                <div className="flex items-center gap-2 mt-1">
                  <Progress
                    value={(selectedExecution.completed_steps / selectedExecution.total_steps) * 100}
                    className="flex-1"
                  />
                  <span className="text-sm font-medium">
                    {selectedExecution.completed_steps}/{selectedExecution.total_steps}
                  </span>
                </div>
                <div className="flex justify-between text-sm text-muted-foreground mt-1">
                  <span>{selectedExecution.completed_steps} completed</span>
                  <span>{selectedExecution.failed_steps} failed</span>
                  <span>{selectedExecution.total_steps - selectedExecution.completed_steps - selectedExecution.failed_steps} remaining</span>
                </div>
              </div>

              {/* Step Details */}
              <div>
                <Label>Step Execution Details</Label>
                <div className="mt-2 space-y-2">
                  {stepExecutions.map((step) => (
                    <div key={step.id} className="border rounded p-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {getStepIcon(step.action_type)}
                          <span className="font-medium">{step.step_name}</span>
                          <Badge variant="outline" className="text-xs">
                            {step.action_type}
                          </Badge>
                          <Badge
                            variant={
                              step.status === 'completed' ? 'default' :
                              step.status === 'failed' ? 'destructive' :
                              step.status === 'running' ? 'secondary' : 'outline'
                            }
                          >
                            {step.status}
                          </Badge>
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {step.duration_seconds ? formatDuration(step.duration_seconds) : 'N/A'}
                        </div>
                      </div>

                      {step.error_message && (
                        <Alert className="mt-2" variant="destructive">
                          <AlertTriangle className="h-4 w-4" />
                          <AlertDescription>{step.error_message}</AlertDescription>
                        </Alert>
                      )}

                      {step.result && (
                        <div className="mt-2">
                          <Label className="text-xs">Result</Label>
                          <pre className="text-xs bg-muted p-2 rounded mt-1 overflow-x-auto">
                            {JSON.stringify(step.result, null, 2)}
                          </pre>
                        </div>
                      )}

                      {step.retry_count > 0 && (
                        <div className="mt-2 text-sm text-yellow-600">
                          Retries: {step.retry_count}/{step.max_retries}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setSelectedExecution(null)}>
                Close
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}