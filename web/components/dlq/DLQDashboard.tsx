import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useToast } from '@/hooks/use-toast';
import { useDLQ } from '@/hooks/useDLQ';
import {
  AlertTriangle,
  RefreshCw,
  PlayCircle,
  Trash2,
  Filter,
  CheckCircle,
  XCircle,
  Clock,
  Activity,
  Zap,
  AlertCircle,
} from 'lucide-react';

interface DLQEntry {
  id: string;
  task_id: string;
  task_name: string;
  error_type: string;
  error_message: string;
  error_category: string;
  retry_count: number;
  max_retries: number;
  dlq_status: string;
  priority: string;
  created_at: string;
  last_retry_at?: string;
  next_retry_at?: string;
  redrive_history?: any[];
  invoice_id?: string;
  queue_name?: string;
}

interface DLQStats {
  total_entries: number;
  pending_entries: number;
  processing_entries: number;
  completed_entries: number;
  failed_permanently: number;
  archived_entries: number;
  processing_errors: number;
  validation_errors: number;
  network_errors: number;
  database_errors: number;
  timeout_errors: number;
  business_rule_errors: number;
  system_errors: number;
  unknown_errors: number;
  critical_entries: number;
  high_entries: number;
  normal_entries: number;
  low_entries: number;
  avg_age_hours: number;
  oldest_entry_age_hours: number;
}

export function DLQDashboard() {
  const [entries, setEntries] = useState<DLQEntry[]>([]);
  const [stats, setStats] = useState<DLQStats | null>(null);
  const [selectedEntries, setSelectedEntries] = useState<string[]>([]);
  const [filters, setFilters] = useState({
    status: '',
    category: '',
    priority: '',
    task_name: '',
    queue_name: '',
  });
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 50,
    total: 0,
  });
  const [loading, setLoading] = useState(true);
  const [redriveModalOpen, setRedriveModalOpen] = useState(false);
  const [errorDetailsOpen, setErrorDetailsOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<DLQEntry | null>(null);
  const { toast } = useToast();

  const dlq = useDLQ();

  // Load data
  useEffect(() => {
    loadDLQData();
    loadDLQStats();
  }, [filters, pagination.page, pagination.pageSize]);

  const loadDLQData = async () => {
    try {
      setLoading(true);
      const response = await dlq.listEntries({
        ...filters,
        page: pagination.page,
        page_size: pagination.pageSize,
      });
      setEntries(response.entries);
      setPagination(prev => ({ ...prev, total: response.pagination.total }));
    } catch (error) {
      console.error('Failed to load DLQ entries:', error);
      toast({
        title: 'Error',
        description: 'Failed to load DLQ entries',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const loadDLQStats = async () => {
    try {
      const statsData = await dlq.getStats();
      setStats(statsData);
    } catch (error) {
      console.error('Failed to load DLQ stats:', error);
    }
  };

  const handleRedrive = async (entryIds: string[], force = false) => {
    try {
      const response = await dlq.redriveEntries({
        dlq_ids: entryIds,
        force,
      });

      toast({
        title: 'Redrive Complete',
        description: `${response.success_count} successful, ${response.failed_count} failed, ${response.skipped_count} skipped`,
      });

      // Reload data
      loadDLQData();
      loadDLQStats();
      setSelectedEntries([]);
      setRedriveModalOpen(false);
    } catch (error) {
      toast({
        title: 'Redrive Failed',
        description: 'Failed to redrive selected entries',
        variant: 'destructive',
      });
    }
  };

  const handleDelete = async (entryId: string) => {
    try {
      await dlq.deleteEntry(entryId);
      toast({
        title: 'Entry Deleted',
        description: 'DLQ entry deleted successfully',
      });
      loadDLQData();
      loadDLQStats();
    } catch (error) {
      toast({
        title: 'Delete Failed',
        description: 'Failed to delete DLQ entry',
        variant: 'destructive',
      });
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'processing': return 'bg-blue-100 text-blue-800';
      case 'completed': return 'bg-green-100 text-green-800';
      case 'failed_permanently': return 'bg-red-100 text-red-800';
      case 'archived': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'bg-red-100 text-red-800';
      case 'high': return 'bg-orange-100 text-orange-800';
      case 'normal': return 'bg-blue-100 text-blue-800';
      case 'low': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'processing_error': return <AlertTriangle className="h-4 w-4" />;
      case 'validation_error': return <XCircle className="h-4 w-4" />;
      case 'network_error': return <Activity className="h-4 w-4" />;
      case 'database_error': return <AlertCircle className="h-4 w-4" />;
      case 'timeout_error': return <Clock className="h-4 w-4" />;
      default: return <AlertTriangle className="h-4 w-4" />;
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatDuration = (hours: number) => {
    if (hours < 1) return `${Math.round(hours * 60)}m`;
    if (hours < 24) return `${Math.round(hours)}h`;
    return `${Math.round(hours / 24)}d`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dead Letter Queue</h1>
          <p className="text-muted-foreground">
            Monitor and manage failed Celery tasks
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            onClick={() => {
              loadDLQData();
              loadDLQStats();
            }}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            onClick={() => setRedriveModalOpen(true)}
            disabled={selectedEntries.length === 0}
          >
            <PlayCircle className="h-4 w-4 mr-2" />
            Redrive Selected ({selectedEntries.length})
          </Button>
        </div>
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Entries</CardTitle>
              <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_entries}</div>
              <p className="text-xs text-muted-foreground">
                {stats.pending_entries} pending
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Critical Priority</CardTitle>
              <Zap className="h-4 w-4 text-red-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{stats.critical_entries}</div>
              <p className="text-xs text-muted-foreground">
                Requires immediate attention
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
              <CheckCircle className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {stats.total_entries > 0
                  ? Math.round((stats.completed_entries / stats.total_entries) * 100)
                  : 0}%
              </div>
              <p className="text-xs text-muted-foreground">
                {stats.completed_entries} completed
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Oldest Entry</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatDuration(stats.oldest_entry_age_hours)}
              </div>
              <p className="text-xs text-muted-foreground">
                Average: {formatDuration(stats.avg_age_hours)}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Error Category Breakdown */}
      {stats && (
        <Card>
          <CardHeader>
            <CardTitle>Error Categories</CardTitle>
            <CardDescription>
              Breakdown of errors by category
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <div className="flex items-center space-x-2">
                {getCategoryIcon('processing_error')}
                <div className="flex-1">
                  <div className="text-sm font-medium">Processing</div>
                  <div className="text-xs text-muted-foreground">
                    {stats.processing_errors} errors
                  </div>
                </div>
                {stats.total_entries > 0 && (
                  <Progress
                    value={(stats.processing_errors / stats.total_entries) * 100}
                    className="w-16"
                  />
                )}
              </div>
              <div className="flex items-center space-x-2">
                {getCategoryIcon('validation_error')}
                <div className="flex-1">
                  <div className="text-sm font-medium">Validation</div>
                  <div className="text-xs text-muted-foreground">
                    {stats.validation_errors} errors
                  </div>
                </div>
                {stats.total_entries > 0 && (
                  <Progress
                    value={(stats.validation_errors / stats.total_entries) * 100}
                    className="w-16"
                  />
                )}
              </div>
              <div className="flex items-center space-x-2">
                {getCategoryIcon('network_error')}
                <div className="flex-1">
                  <div className="text-sm font-medium">Network</div>
                  <div className="text-xs text-muted-foreground">
                    {stats.network_errors} errors
                  </div>
                </div>
                {stats.total_entries > 0 && (
                  <Progress
                    value={(stats.network_errors / stats.total_entries) * 100}
                    className="w-16"
                  />
                )}
              </div>
              <div className="flex items-center space-x-2">
                {getCategoryIcon('database_error')}
                <div className="flex-1">
                  <div className="text-sm font-medium">Database</div>
                  <div className="text-xs text-muted-foreground">
                    {stats.database_errors} errors
                  </div>
                </div>
                {stats.total_entries > 0 && (
                  <Progress
                    value={(stats.database_errors / stats.total_entries) * 100}
                    className="w-16"
                  />
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-5">
            <Select
              value={filters.status}
              onValueChange={(value) => setFilters(prev => ({ ...prev, status: value }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Statuses</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="processing">Processing</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="failed_permanently">Failed Permanently</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={filters.category}
              onValueChange={(value) => setFilters(prev => ({ ...prev, category: value }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Categories</SelectItem>
                <SelectItem value="processing_error">Processing Error</SelectItem>
                <SelectItem value="validation_error">Validation Error</SelectItem>
                <SelectItem value="network_error">Network Error</SelectItem>
                <SelectItem value="database_error">Database Error</SelectItem>
                <SelectItem value="timeout_error">Timeout Error</SelectItem>
                <SelectItem value="business_rule_error">Business Rule Error</SelectItem>
                <SelectItem value="system_error">System Error</SelectItem>
              </SelectContent>
            </Select>

            <Select
              value={filters.priority}
              onValueChange={(value) => setFilters(prev => ({ ...prev, priority: value }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Priority" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">All Priorities</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="normal">Normal</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>

            <Input
              placeholder="Task name..."
              value={filters.task_name}
              onChange={(e) => setFilters(prev => ({ ...prev, task_name: e.target.value }))}
            />

            <Input
              placeholder="Queue name..."
              value={filters.queue_name}
              onChange={(e) => setFilters(prev => ({ ...prev, queue_name: e.target.value }))}
            />
          </div>
        </CardContent>
      </Card>

      {/* DLQ Entries Table */}
      <Card>
        <CardHeader>
          <CardTitle>DLQ Entries</CardTitle>
          <CardDescription>
            {pagination.total} total entries
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[600px]">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[50px]">
                    <input
                      type="checkbox"
                      checked={selectedEntries.length === entries.length}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedEntries(entries.map(entry => entry.id));
                        } else {
                          setSelectedEntries([]);
                        }
                      }}
                    />
                  </TableHead>
                  <TableHead>Task</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Retries</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Next Retry</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={selectedEntries.includes(entry.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedEntries(prev => [...prev, entry.id]);
                          } else {
                            setSelectedEntries(prev => prev.filter(id => id !== entry.id));
                          }
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <div>
                        <div className="font-medium text-sm">{entry.task_name}</div>
                        <div className="text-xs text-muted-foreground">
                          {entry.task_id.substring(0, 8)}...
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge className={getStatusColor(entry.dlq_status)}>
                        {entry.dlq_status.replace('_', ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={getPriorityColor(entry.priority)}>
                        {entry.priority}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-1">
                        {getCategoryIcon(entry.error_category)}
                        <span className="text-sm">
                          {entry.error_category.replace('_', ' ')}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        {entry.retry_count}/{entry.max_retries}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        {formatDate(entry.created_at)}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        {entry.next_retry_at ? formatDate(entry.next_retry_at) : '-'}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSelectedEntry(entry);
                            setErrorDetailsOpen(true);
                          }}
                        >
                          Details
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRedrive([entry.id])}
                          disabled={entry.dlq_status === 'processing'}
                        >
                          <PlayCircle className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDelete(entry.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollArea>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <div className="text-sm text-muted-foreground">
              Showing {((pagination.page - 1) * pagination.pageSize) + 1} to{' '}
              {Math.min(pagination.page * pagination.pageSize, pagination.total)} of{' '}
              {pagination.total} entries
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
                disabled={pagination.page === 1}
              >
                Previous
              </Button>
              <span className="text-sm">
                Page {pagination.page} of {Math.ceil(pagination.total / pagination.pageSize)}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
                disabled={pagination.page >= Math.ceil(pagination.total / pagination.pageSize)}
              >
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Redrive Confirmation Modal */}
      <Dialog open={redriveModalOpen} onOpenChange={setRedriveModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Redrive DLQ Entries</DialogTitle>
            <DialogDescription>
              Are you sure you want to redrive {selectedEntries.length} selected entries?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRedriveModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => handleRedrive(selectedEntries)}>
              Redrive
            </Button>
            <Button
              variant="destructive"
              onClick={() => handleRedrive(selectedEntries, true)}
            >
              Force Redrive
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Error Details Modal */}
      <Dialog open={errorDetailsOpen} onOpenChange={setErrorDetailsOpen}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>DLQ Entry Details</DialogTitle>
          </DialogHeader>
          {selectedEntry && (
            <Tabs defaultValue="overview" className="w-full">
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="error">Error Details</TabsTrigger>
                <TabsTrigger value="history">History</TabsTrigger>
              </TabsList>
              <TabsContent value="overview" className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="text-sm font-medium">Task ID</label>
                    <p className="text-sm text-muted-foreground">{selectedEntry.task_id}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium">Task Name</label>
                    <p className="text-sm text-muted-foreground">{selectedEntry.task_name}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium">Status</label>
                    <Badge className={getStatusColor(selectedEntry.dlq_status)}>
                      {selectedEntry.dlq_status.replace('_', ' ')}
                    </Badge>
                  </div>
                  <div>
                    <label className="text-sm font-medium">Priority</label>
                    <Badge className={getPriorityColor(selectedEntry.priority)}>
                      {selectedEntry.priority}
                    </Badge>
                  </div>
                  <div>
                    <label className="text-sm font-medium">Error Category</label>
                    <p className="text-sm text-muted-foreground">
                      {selectedEntry.error_category.replace('_', ' ')}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium">Retries</label>
                    <p className="text-sm text-muted-foreground">
                      {selectedEntry.retry_count}/{selectedEntry.max_retries}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium">Created At</label>
                    <p className="text-sm text-muted-foreground">
                      {formatDate(selectedEntry.created_at)}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium">Last Retry</label>
                    <p className="text-sm text-muted-foreground">
                      {selectedEntry.last_retry_at ? formatDate(selectedEntry.last_retry_at) : 'Never'}
                    </p>
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="error" className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Error Type</label>
                  <p className="text-sm text-muted-foreground">{selectedEntry.error_type}</p>
                </div>
                <div>
                  <label className="text-sm font-medium">Error Message</label>
                  <p className="text-sm text-muted-foreground">{selectedEntry.error_message}</p>
                </div>
                <div>
                  <label className="text-sm font-medium">Stack Trace</label>
                  <ScrollArea className="h-40 w-full rounded-md border">
                    <pre className="text-xs p-2">
                      {selectedEntry.error_stack_trace || 'No stack trace available'}
                    </pre>
                  </ScrollArea>
                </div>
              </TabsContent>
              <TabsContent value="history" className="space-y-4">
                {selectedEntry.redrive_history && selectedEntry.redrive_history.length > 0 ? (
                  <div className="space-y-2">
                    {selectedEntry.redrive_history.map((attempt, index) => (
                      <div key={index} className="border rounded-lg p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">Attempt #{attempt.attempt_number}</span>
                          <Badge variant={attempt.success ? "default" : "destructive"}>
                            {attempt.success ? 'Success' : 'Failed'}
                          </Badge>
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {formatDate(attempt.timestamp)}
                        </div>
                        {attempt.error_message && (
                          <div className="text-xs text-red-600 mt-1">
                            {attempt.error_message}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No redrive attempts recorded</p>
                )}
              </TabsContent>
            </Tabs>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setErrorDetailsOpen(false)}>
              Close
            </Button>
            <Button
              onClick={() => {
                if (selectedEntry) {
                  handleRedrive([selectedEntry.id]);
                  setErrorDetailsOpen(false);
                }
              }}
              disabled={selectedEntry?.dlq_status === 'processing'}
            >
              Redrive Entry
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}