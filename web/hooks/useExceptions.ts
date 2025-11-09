/**
 * React hooks for exception management
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Exception,
  ExceptionListResponse,
  ExceptionAnalytics,
  ExceptionFilterOptions,
  BatchResolutionRequest,
  ExceptionUpdateRequest,
  getSeverityColor,
  getStatusColor,
  getConfidenceColor
} from '@/lib/exception-types'
import { exceptionApi, ExceptionAPIError } from '@/lib/exception-api'

// Main exception management hook
export function useExceptions(initialFilters?: ExceptionFilterOptions) {
  const [exceptions, setExceptions] = useState<Exception[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState<ExceptionFilterOptions>(initialFilters || {})
  const [pagination, setPagination] = useState({ skip: 0, limit: 50 })
  const [selectedExceptions, setSelectedExceptions] = useState<string[]>([])

  const loadExceptions = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await exceptionApi.getExceptions(filters, pagination.skip, pagination.limit)
      setExceptions(response.exceptions)
      setTotal(response.total)
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Failed to load exceptions'
      setError(message)
      console.error('Failed to load exceptions:', err)
    } finally {
      setLoading(false)
    }
  }, [filters, pagination])

  useEffect(() => {
    loadExceptions()
  }, [loadExceptions])

  const updateFilters = useCallback((newFilters: Partial<ExceptionFilterOptions>) => {
    setFilters(prev => ({ ...prev, ...newFilters }))
    setPagination(prev => ({ ...prev, skip: 0 })) // Reset to first page
  }, [])

  const clearFilters = useCallback(() => {
    setFilters({})
    setPagination(prev => ({ ...prev, skip: 0 }))
  }, [])

  const selectException = useCallback((exceptionId: string, selected: boolean) => {
    setSelectedExceptions(prev =>
      selected
        ? [...prev, exceptionId]
        : prev.filter(id => id !== exceptionId)
    )
  }, [])

  const selectAllExceptions = useCallback((selected: boolean) => {
    setSelectedExceptions(selected ? exceptions.map(ex => ex.id) : [])
  }, [exceptions])

  const refreshExceptions = useCallback(() => {
    loadExceptions()
  }, [loadExceptions])

  return {
    exceptions,
    loading,
    error,
    total,
    filters,
    pagination,
    selectedExceptions,
    updateFilters,
    clearFilters,
    selectException,
    selectAllExceptions,
    refreshExceptions,
    setPagination,
    hasSelected: selectedExceptions.length > 0,
    allSelected: exceptions.length > 0 && selectedExceptions.length === exceptions.length,
  }
}

// Single exception hook
export function useException(exceptionId: string) {
  const [exception, setException] = useState<Exception | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadException = useCallback(async () => {
    if (!exceptionId) return

    try {
      setLoading(true)
      setError(null)
      const data = await exceptionApi.getException(exceptionId)
      setException(data)
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Failed to load exception'
      setError(message)
      console.error('Failed to load exception:', err)
    } finally {
      setLoading(false)
    }
  }, [exceptionId])

  useEffect(() => {
    loadException()
  }, [loadException])

  const updateException = useCallback(async (update: ExceptionUpdateRequest) => {
    if (!exceptionId) return

    try {
      setLoading(true)
      const updated = await exceptionApi.updateException(exceptionId, update)
      setException(updated)
      return updated
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Failed to update exception'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [exceptionId])

  const assignException = useCallback(async (assignedTo: string) => {
    if (!exceptionId) return

    try {
      setLoading(true)
      const updated = await exceptionApi.assignException(exceptionId, assignedTo)
      setException(updated)
      return updated
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Failed to assign exception'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [exceptionId])

  const resolveException = useCallback(async (resolutionMethod: string, notes?: string) => {
    if (!exceptionId) return

    try {
      setLoading(true)
      const resolved = await exceptionApi.resolveException(exceptionId, resolutionMethod, notes)
      setException(resolved)
      return resolved
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Failed to resolve exception'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [exceptionId])

  const escalateException = useCallback(async (reason: string) => {
    if (!exceptionId) return

    try {
      setLoading(true)
      const escalated = await exceptionApi.escalateException(exceptionId, reason)
      setException(escalated)
      return escalated
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Failed to escalate exception'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [exceptionId])

  const closeException = useCallback(async (notes?: string) => {
    if (!exceptionId) return

    try {
      setLoading(true)
      const closed = await exceptionApi.closeException(exceptionId, notes)
      setException(closed)
      return closed
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Failed to close exception'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [exceptionId])

  return {
    exception,
    loading,
    error,
    updateException,
    assignException,
    resolveException,
    escalateException,
    closeException,
    refresh: loadException,
  }
}

// Exception analytics hook
export function useExceptionAnalytics(dateRange?: { start: string; end: string }) {
  const [analytics, setAnalytics] = useState<ExceptionAnalytics | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadAnalytics = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await exceptionApi.getAnalytics(dateRange)
      setAnalytics(data)
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Failed to load analytics'
      setError(message)
      console.error('Failed to load analytics:', err)
    } finally {
      setLoading(false)
    }
  }, [dateRange])

  useEffect(() => {
    loadAnalytics()
  }, [loadAnalytics])

  return {
    analytics,
    loading,
    error,
    refresh: loadAnalytics,
  }
}

// Batch operations hook
export function useBatchOperations() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const batchResolve = useCallback(async (request: BatchResolutionRequest) => {
    try {
      setLoading(true)
      setError(null)
      const result = await exceptionApi.batchResolve(request)
      return result
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Failed to batch resolve'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const batchAssign = useCallback(async (exceptionIds: string[], assignedTo: string) => {
    try {
      setLoading(true)
      setError(null)
      const result = await exceptionApi.batchAssign(exceptionIds, assignedTo)
      return result
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Failed to batch assign'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const batchClose = useCallback(async (exceptionIds: string[], notes?: string) => {
    try {
      setLoading(true)
      setError(null)
      const result = await exceptionApi.batchClose(exceptionIds, notes)
      return result
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Failed to batch close'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return {
    batchResolve,
    batchAssign,
    batchClose,
    loading,
    error,
  }
}

// Exception suggestions hook
export function useExceptionSuggestions(exceptionId: string) {
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSuggestions = useCallback(async () => {
    if (!exceptionId) return

    try {
      setLoading(true)
      setError(null)
      const data = await exceptionApi.getResolutionSuggestions(exceptionId)
      setSuggestions(data)
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Failed to load suggestions'
      setError(message)
      console.error('Failed to load suggestions:', err)
    } finally {
      setLoading(false)
    }
  }, [exceptionId])

  useEffect(() => {
    loadSuggestions()
  }, [loadSuggestions])

  return {
    suggestions,
    loading,
    error,
    refresh: loadSuggestions,
  }
}

// Real-time updates hook
export function useRealTimeExceptions() {
  const [updates, setUpdates] = useState<any[]>([])
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const unsubscribe = exceptionApi.subscribeToExceptionUpdates((event) => {
      setUpdates(prev => [event, ...prev.slice(0, 99)]) // Keep last 100 updates
      setConnected(true)
    })

    return () => {
      unsubscribe()
      setConnected(false)
    }
  }, [])

  const clearUpdates = useCallback(() => {
    setUpdates([])
  }, [])

  return {
    updates,
    connected,
    clearUpdates,
  }
}

// Exception search hook
export function useExceptionSearch() {
  const [results, setResults] = useState<Exception[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  const search = useCallback(async (searchQuery: string, limit: number = 10) => {
    if (!searchQuery.trim()) {
      setResults([])
      return
    }

    try {
      setLoading(true)
      setError(null)
      setQuery(searchQuery)
      const data = await exceptionApi.searchExceptions(searchQuery, limit)
      setResults(data)
    } catch (err) {
      const message = err instanceof ExceptionAPIError ? err.message : 'Search failed'
      setError(message)
      console.error('Search failed:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const clearSearch = useCallback(() => {
    setResults([])
    setQuery('')
    setError(null)
  }, [])

  return {
    results,
    loading,
    error,
    query,
    search,
    clearSearch,
  }
}

// Utility hook for exception display
export function useExceptionDisplay(exception: Exception | null) {
  return useMemo(() => {
    if (!exception) return null

    return {
      severityColor: getSeverityColor(exception.severity),
      statusColor: getStatusColor(exception.status),
      confidenceColor: getConfidenceColor(exception.overall_confidence),
      isResolved: exception.status === 'resolved' || exception.status === 'closed',
      needsAction: exception.status === 'open' || exception.status === 'in_progress',
      isOverdue: exception.status === 'open' && new Date(exception.created_at) < new Date(Date.now() - 24 * 60 * 60 * 1000),
      assignedToMe: exception.assigned_to === 'current_user', // Replace with actual user logic
    }
  }, [exception])
}

// Export all hooks
export {
  useExceptions as default,
}