import { useState, useEffect, useCallback } from 'react';
import { useToast } from '@/hooks/use-toast';

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
  worker_name?: string;
  execution_time?: number;
  manual_intervention: boolean;
  intervention_reason?: string;
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

interface ListEntriesParams {
  status?: string;
  category?: string;
  priority?: string;
  task_name?: string;
  invoice_id?: string;
  queue_name?: string;
  worker_name?: string;
  idempotency_key?: string;
  created_after?: string;
  created_before?: string;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: string;
}

interface ListEntriesResponse {
  entries: DLQEntry[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    pages: number;
  };
  filters: any;
}

interface RedriveRequest {
  dlq_ids: string[];
  force?: boolean;
  modify_args?: any;
  priority?: string;
}

interface RedriveResponse {
  success_count: number;
  failed_count: number;
  skipped_count: number;
  results: Array<{
    dlq_id: string;
    success: boolean;
    message: string;
  }>;
}

interface DLQHealth {
  status: string;
  health_score: number;
  circuit_breakers: any;
  open_circuit_breakers: string[];
  recent_stats: DLQStats;
  timestamp: string;
}

interface RedriveRecommendations {
  should_redrive: boolean;
  reason: string;
  suggested_action: string;
  estimated_success_rate: number;
  recommended_modifications: any;
}

export function useDLQ() {
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const apiRequest = useCallback(async (
    endpoint: string,
    options: RequestInit = {}
  ) => {
    const baseUrl = '/api/v1/dlq';
    const url = `${baseUrl}${endpoint}`;

    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Unknown error' }));
      throw new Error(error.message || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }, []);

  const listEntries = useCallback(async (params: ListEntriesParams = {}): Promise<ListEntriesResponse> => {
    setLoading(true);
    try {
      const queryParams = new URLSearchParams();

      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          queryParams.append(key, String(value));
        }
      });

      const endpoint = `/entries${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;
      return await apiRequest(endpoint);
    } catch (error) {
      console.error('Failed to list DLQ entries:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to list DLQ entries',
        variant: 'destructive',
      });
      throw error;
    } finally {
      setLoading(false);
    }
  }, [apiRequest, toast]);

  const getEntry = useCallback(async (id: string): Promise<DLQEntry> => {
    setLoading(true);
    try {
      return await apiRequest(`/entries/${id}`);
    } catch (error) {
      console.error('Failed to get DLQ entry:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to get DLQ entry',
        variant: 'destructive',
      });
      throw error;
    } finally {
      setLoading(false);
    }
  }, [apiRequest, toast]);

  const getEntryByTaskId = useCallback(async (taskId: string): Promise<DLQEntry> => {
    setLoading(true);
    try {
      return await apiRequest(`/entries/task/${taskId}`);
    } catch (error) {
      console.error('Failed to get DLQ entry by task ID:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to get DLQ entry by task ID',
        variant: 'destructive',
      });
      throw error;
    } finally {
      setLoading(false);
    }
  }, [apiRequest, toast]);

  const redriveEntry = useCallback(async (
    id: string,
    options: {
      force?: boolean;
      modify_args?: any;
      priority_override?: string;
    } = {}
  ): Promise<{ success: boolean; message: string }> => {
    setLoading(true);
    try {
      const queryParams = new URLSearchParams();

      if (options.force !== undefined) {
        queryParams.append('force', String(options.force));
      }
      if (options.priority_override) {
        queryParams.append('priority_override', options.priority_override);
      }

      const endpoint = `/entries/${id}/redrive${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;

      const requestOptions: RequestInit = {};
      if (options.modify_args) {
        requestOptions.method = 'POST';
        requestOptions.body = JSON.stringify(options.modify_args);
      } else {
        requestOptions.method = 'POST';
      }

      return await apiRequest(endpoint, requestOptions);
    } catch (error) {
      console.error('Failed to redrive DLQ entry:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to redrive DLQ entry',
        variant: 'destructive',
      });
      throw error;
    } finally {
      setLoading(false);
    }
  }, [apiRequest, toast]);

  const redriveEntries = useCallback(async (request: RedriveRequest): Promise<RedriveResponse> => {
    setLoading(true);
    try {
      return await apiRequest('/bulk-redrive', {
        method: 'POST',
        body: JSON.stringify(request),
      });
    } catch (error) {
      console.error('Failed to redrive DLQ entries:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to redrive DLQ entries',
        variant: 'destructive',
      });
      throw error;
    } finally {
      setLoading(false);
    }
  }, [apiRequest, toast]);

  const getStats = useCallback(async (days: number = 30): Promise<DLQStats> => {
    setLoading(true);
    try {
      return await apiRequest(`/stats?days=${days}`);
    } catch (error) {
      console.error('Failed to get DLQ stats:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to get DLQ stats',
        variant: 'destructive',
      });
      throw error;
    } finally {
      setLoading(false);
    }
  }, [apiRequest, toast]);

  const getHealth = useCallback(async (): Promise<DLQHealth> => {
    setLoading(true);
    try {
      return await apiRequest('/health');
    } catch (error) {
      console.error('Failed to get DLQ health:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to get DLQ health',
        variant: 'destructive',
      });
      throw error;
    } finally {
      setLoading(false);
    }
  }, [apiRequest, toast]);

  const getRedriveRecommendations = useCallback(async (id: string): Promise<{
    dlq_id: string;
    task_name: string;
    error_category: string;
    retry_count: number;
    max_retries: number;
    should_redrive: boolean;
    recommendations: RedriveRecommendations;
    last_retry_at?: string;
    next_retry_at?: string;
  }> => {
    setLoading(true);
    try {
      return await apiRequest(`/entries/${id}/recommendations`);
    } catch (error) {
      console.error('Failed to get redrive recommendations:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to get redrive recommendations',
        variant: 'destructive',
      });
      throw error;
    } finally {
      setLoading(false);
    }
  }, [apiRequest, toast]);

  const deleteEntry = useCallback(async (id: string): Promise<{ success: boolean; message: string }> => {
    setLoading(true);
    try {
      const response = await apiRequest(`/entries/${id}`, {
        method: 'DELETE',
      });
      return response;
    } catch (error) {
      console.error('Failed to delete DLQ entry:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to delete DLQ entry',
        variant: 'destructive',
      });
      throw error;
    } finally {
      setLoading(false);
    }
  }, [apiRequest, toast]);

  const cleanupOldEntries = useCallback(async (
    days: number = 90,
    status?: string
  ): Promise<{ success: boolean; message: string; deleted_count: number }> => {
    setLoading(true);
    try {
      const queryParams = new URLSearchParams();
      queryParams.append('days', String(days));
      if (status) {
        queryParams.append('status', status);
      }

      const response = await apiRequest(`/cleanup?${queryParams.toString()}`, {
        method: 'POST',
      });
      return response;
    } catch (error) {
      console.error('Failed to cleanup old DLQ entries:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to cleanup old DLQ entries',
        variant: 'destructive',
      });
      throw error;
    } finally {
      setLoading(false);
    }
  }, [apiRequest, toast]);

  // Auto-refresh stats
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [stats, setStats] = useState<DLQStats | null>(null);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        getStats().then(setStats).catch(console.error);
      }, 30000); // Refresh every 30 seconds

      return () => clearInterval(interval);
    }
  }, [autoRefresh, getStats]);

  // Initial stats load
  useEffect(() => {
    getStats().then(setStats).catch(console.error);
  }, [getStats]);

  return {
    loading,
    stats,
    autoRefresh,
    setAutoRefresh,
    listEntries,
    getEntry,
    getEntryByTaskId,
    redriveEntry,
    redriveEntries,
    getStats,
    getHealth,
    getRedriveRecommendations,
    deleteEntry,
    cleanupOldEntries,
  };
}