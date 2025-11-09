"use client"

import { useState, useEffect, useCallback } from "react"

interface SLOMeasurement {
  id: string
  period_start: string
  period_end: string
  measurement_period: string
  actual_value: number
  target_value: number
  achieved_percentage: number
  error_budget_consumed: number
  good_events_count: number
  total_events_count: number
  measurement_metadata?: Record<string, any>
  created_at: string
}

interface SLODefinition {
  id: string
  name: string
  description: string
  sli_type: string
  target_percentage: number
  target_value: number
  target_unit: string
  error_budget_percentage: number
  alerting_threshold_percentage: number
  measurement_period: string
  burn_rate_alert_threshold: number
  is_active: boolean
  slos_owner?: string
  notification_channels?: string[]
  created_at: string
  updated_at: string
}

interface SLOWithMeasurements {
  slo: SLODefinition
  measurements: SLOMeasurement[]
  summary: {
    latest_achieved_percentage: number | null
    average_achieved_percentage: number | null
    min_achieved_percentage: number | null
    max_achieved_percentage: number | null
    latest_error_budget_consumed: number | null
    average_error_budget_consumed: number | null
    measurements_count: number
  }
}

interface SLOAlert {
  id: string
  slo_definition_id: string
  measurement_id?: string
  alert_type: string
  severity: "info" | "warning" | "critical"
  title: string
  message: string
  current_value: number
  target_value: number
  breached_at: string
  acknowledged_at?: string
  acknowledged_by?: string
  resolved_at?: string
  resolution_notes?: string
  notification_sent: boolean
  notification_attempts: number
  last_notification_at?: string
  created_at: string
  updated_at: string
}

interface KPISummary {
  period: {
    start_date: string
    end_date: string
    days: number
  }
  volume: {
    total_invoices: number
    successful_invoices: number
    invoices_with_exceptions: number
  }
  performance: {
    processing_success_rate: number
    exception_rate: number
    average_processing_time_seconds: number
    average_processing_time_minutes: number
    average_extraction_confidence: number
  }
  summary: {
    daily_average_invoices: number
    success_rate_grade: string
    performance_trend: string
  }
}

interface InvoiceTrendData {
  period: string
  total_invoices: number
  successful_invoices: number
  success_rate: number
}

interface ProcessingTrendData {
  period: string
  avg_processing_time_seconds: number
  avg_processing_time_minutes: number
  sample_size: number
}

interface ConfidenceTrendData {
  period: string
  avg_confidence: number
  sample_size: number
}

interface TrendData {
  volume_trends: InvoiceTrendData[]
  processing_trends: ProcessingTrendData[]
  confidence_trends: ConfidenceTrendData[]
  period: {
    start_date: string
    end_date: string
    days: number
    granularity: string
  }
}

export interface UseSLOMetricsReturn {
  // Dashboard data
  dashboardData: any
  loadingDashboard: boolean
  dashboardError: string | null
  refetchDashboard: () => Promise<void>

  // SLO definitions
  sloDefinitions: SLODefinition[]
  loadingDefinitions: boolean
  definitionsError: string | null
  refetchDefinitions: () => Promise<void>

  // SLO measurements
  measurementsBySLO: Record<string, SLOWithMeasurements>
  loadingMeasurements: Record<string, boolean>
  measurementsErrors: Record<string, string | null>
  fetchMeasurements: (sloId: string, days?: number) => Promise<void>

  // Alerts
  alerts: SLOAlert[]
  loadingAlerts: boolean
  alertsError: string | null
  alertCount: number
  refetchAlerts: () => Promise<void>
  acknowledgeAlert: (alertId: string, notes?: string) => Promise<void>
  resolveAlert: (alertId: string, notes?: string) => Promise<void>

  // KPI summary
  kpiSummary: KPISummary | null
  loadingKPI: boolean
  kpiError: string | null
  refetchKPI: () => Promise<void>

  // Trends
  trendData: TrendData | null
  loadingTrends: boolean
  trendsError: string | null
  fetchTrends: (days?: number, granularity?: string) => Promise<void>

  // Utilities
  formatValue: (value: number | null, unit: string) => string
  formatTimeAgo: (timestamp: string) => string
  getStatusColor: (status: string) => string
  calculateTrend: (data: number[]) => "up" | "down" | "stable"
}

export function useSLOMetrics(): UseSLOMetricsReturn {
  const [dashboardData, setDashboardData] = useState<any>(null)
  const [loadingDashboard, setLoadingDashboard] = useState(false)
  const [dashboardError, setDashboardError] = useState<string | null>(null)

  const [sloDefinitions, setSloDefinitions] = useState<SLODefinition[]>([])
  const [loadingDefinitions, setLoadingDefinitions] = useState(false)
  const [definitionsError, setDefinitionsError] = useState<string | null>(null)

  const [measurementsBySLO, setMeasurementsBySLO] = useState<Record<string, SLOWithMeasurements>>({})
  const [loadingMeasurements, setLoadingMeasurements] = useState<Record<string, boolean>>({})
  const [measurementsErrors, setMeasurementsErrors] = useState<Record<string, string | null>>({})

  const [alerts, setAlerts] = useState<SLOAlert[]>([])
  const [loadingAlerts, setLoadingAlerts] = useState(false)
  const [alertsError, setAlertsError] = useState<string | null>(null)

  const [kpiSummary, setKpiSummary] = useState<KPISummary | null>(null)
  const [loadingKPI, setLoadingKPI] = useState(false)
  const [kpiError, setKpiError] = useState<string | null>(null)

  const [trendData, setTrendData] = useState<TrendData | null>(null)
  const [loadingTrends, setLoadingTrends] = useState(false)
  const [trendsError, setTrendsError] = useState<string | null>(null)

  // Utility functions
  const formatValue = useCallback((value: number | null, unit: string): string => {
    if (value === null) return "N/A"

    if (unit === "minutes") {
      return `${value.toFixed(1)}m`
    } else if (unit === "hours") {
      return `${value.toFixed(1)}h`
    } else if (unit === "seconds") {
      return `${value.toFixed(1)}s`
    } else if (unit === "percentage" || unit === "confidence") {
      return `${(value * 100).toFixed(1)}%`
    }
    return value.toFixed(2)
  }, [])

  const formatTimeAgo = useCallback((timestamp: string): string => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return `${diffDays}d ago`
  }, [])

  const getStatusColor = useCallback((status: string): string => {
    switch (status) {
      case "healthy":
        return "text-green-600 bg-green-50 border-green-200"
      case "warning":
        return "text-yellow-600 bg-yellow-50 border-yellow-200"
      case "critical":
        return "text-red-600 bg-red-50 border-red-200"
      default:
        return "text-gray-600 bg-gray-50 border-gray-200"
    }
  }, [])

  const calculateTrend = useCallback((data: number[]): "up" | "down" | "stable" => {
    if (data.length < 2) return "stable"

    const firstHalf = data.slice(0, Math.floor(data.length / 2))
    const secondHalf = data.slice(Math.floor(data.length / 2))

    const firstAvg = firstHalf.reduce((sum, val) => sum + val, 0) / firstHalf.length
    const secondAvg = secondHalf.reduce((sum, val) => sum + val, 0) / secondHalf.length

    const change = ((secondAvg - firstAvg) / firstAvg) * 100

    if (Math.abs(change) < 5) return "stable"
    return change > 0 ? "up" : "down"
  }, [])

  // API fetch functions
  const fetchDashboardData = useCallback(async (timeRangeDays = 30) => {
    try {
      setLoadingDashboard(true)
      setDashboardError(null)

      const response = await fetch(`/api/v1/metrics/slos/dashboard?time_range_days=${timeRangeDays}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch dashboard data: ${response.statusText}`)
      }

      const result = await response.json()

      if (result.success) {
        setDashboardData(result.data)
      } else {
        throw new Error(result.message || "Failed to load dashboard data")
      }
    } catch (err) {
      console.error("Error fetching dashboard data:", err)
      setDashboardError(err instanceof Error ? err.message : "Failed to load dashboard data")
    } finally {
      setLoadingDashboard(false)
    }
  }, [])

  const fetchSLODefinitions = useCallback(async (activeOnly = true) => {
    try {
      setLoadingDefinitions(true)
      setDefinitionsError(null)

      const response = await fetch(`/api/v1/metrics/slos/definitions?active_only=${activeOnly}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch SLO definitions: ${response.statusText}`)
      }

      const result = await response.json()

      if (result.success) {
        setSloDefinitions(result.data.definitions)
      } else {
        throw new Error(result.message || "Failed to load SLO definitions")
      }
    } catch (err) {
      console.error("Error fetching SLO definitions:", err)
      setDefinitionsError(err instanceof Error ? err.message : "Failed to load SLO definitions")
    } finally {
      setLoadingDefinitions(false)
    }
  }, [])

  const fetchMeasurements = useCallback(async (sloId: string, days = 30) => {
    try {
      setLoadingMeasurements(prev => ({ ...prev, [sloId]: true }))
      setMeasurementsErrors(prev => ({ ...prev, [sloId]: null }))

      const response = await fetch(`/api/v1/metrics/slos/${sloId}/measurements?days=${days}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch measurements: ${response.statusText}`)
      }

      const result = await response.json()

      if (result.success) {
        setMeasurementsBySLO(prev => ({
          ...prev,
          [sloId]: result.data
        }))
      } else {
        throw new Error(result.message || "Failed to load measurements")
      }
    } catch (err) {
      console.error(`Error fetching measurements for SLO ${sloId}:`, err)
      setMeasurementsErrors(prev => ({
        ...prev,
        [sloId]: err instanceof Error ? err.message : "Failed to load measurements"
      }))
    } finally {
      setLoadingMeasurements(prev => ({ ...prev, [sloId]: false }))
    }
  }, [])

  const fetchAlerts = useCallback(async (severity?: string, resolved?: boolean, limit = 50) => {
    try {
      setLoadingAlerts(true)
      setAlertsError(null)

      const params = new URLSearchParams({ limit: limit.toString() })
      if (severity) params.append("severity", severity)
      if (resolved !== undefined) params.append("resolved", resolved.toString())

      const response = await fetch(`/api/v1/metrics/alerts?${params}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch alerts: ${response.statusText}`)
      }

      const result = await response.json()

      if (result.success) {
        setAlerts(result.data.alerts)
      } else {
        throw new Error(result.message || "Failed to load alerts")
      }
    } catch (err) {
      console.error("Error fetching alerts:", err)
      setAlertsError(err instanceof Error ? err.message : "Failed to load alerts")
    } finally {
      setLoadingAlerts(false)
    }
  }, [])

  const fetchKPISummary = useCallback(async (days = 7) => {
    try {
      setLoadingKPI(true)
      setKpiError(null)

      const response = await fetch(`/api/v1/metrics/kpis/summary?days=${days}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch KPI summary: ${response.statusText}`)
      }

      const result = await response.json()

      if (result.success) {
        setKpiSummary(result.data)
      } else {
        throw new Error(result.message || "Failed to load KPI summary")
      }
    } catch (err) {
      console.error("Error fetching KPI summary:", err)
      setKpiError(err instanceof Error ? err.message : "Failed to load KPI summary")
    } finally {
      setLoadingKPI(false)
    }
  }, [])

  const fetchTrends = useCallback(async (days = 30, granularity = "daily") => {
    try {
      setLoadingTrends(true)
      setTrendsError(null)

      const response = await fetch(`/api/v1/metrics/metrics/invoice-trends?days=${days}&granularity=${granularity}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch trend data: ${response.statusText}`)
      }

      const result = await response.json()

      if (result.success) {
        setTrendData(result.data)
      } else {
        throw new Error(result.message || "Failed to load trend data")
      }
    } catch (err) {
      console.error("Error fetching trend data:", err)
      setTrendsError(err instanceof Error ? err.message : "Failed to load trend data")
    } finally {
      setLoadingTrends(false)
    }
  }, [])

  const acknowledgeAlert = useCallback(async (alertId: string, notes = "Acknowledged via dashboard") => {
    try {
      const response = await fetch(`/api/v1/metrics/alerts/${alertId}/acknowledge`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ notes }),
      })

      if (!response.ok) {
        throw new Error(`Failed to acknowledge alert: ${response.statusText}`)
      }

      // Refresh alerts after acknowledgment
      await fetchAlerts()
    } catch (err) {
      console.error(`Error acknowledging alert ${alertId}:`, err)
      throw err
    }
  }, [fetchAlerts])

  const resolveAlert = useCallback(async (alertId: string, notes = "Resolved via dashboard") => {
    try {
      const response = await fetch(`/api/v1/metrics/alerts/${alertId}/resolve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ resolution_notes: notes }),
      })

      if (!response.ok) {
        throw new Error(`Failed to resolve alert: ${response.statusText}`)
      }

      // Refresh alerts after resolution
      await fetchAlerts()
    } catch (err) {
      console.error(`Error resolving alert ${alertId}:`, err)
      throw err
    }
  }, [fetchAlerts])

  // Auto-refresh intervals
  useEffect(() => {
    // Initial data fetch
    fetchDashboardData()
    fetchSLODefinitions()
    fetchAlerts(undefined, false) // Get unresolved alerts
    fetchKPISummary()

    // Set up auto-refresh for dashboard (every 5 minutes)
    const dashboardInterval = setInterval(() => {
      fetchDashboardData()
    }, 5 * 60 * 1000)

    // Set up auto-refresh for alerts (every 2 minutes)
    const alertsInterval = setInterval(() => {
      fetchAlerts(undefined, false)
    }, 2 * 60 * 1000)

    // Set up auto-refresh for KPI summary (every 10 minutes)
    const kpiInterval = setInterval(() => {
      fetchKPISummary()
    }, 10 * 60 * 1000)

    return () => {
      clearInterval(dashboardInterval)
      clearInterval(alertsInterval)
      clearInterval(kpiInterval)
    }
  }, [fetchDashboardData, fetchSLODefinitions, fetchAlerts, fetchKPISummary])

  const alertCount = alerts.filter(alert => !alert.resolved_at).length

  return {
    // Dashboard data
    dashboardData,
    loadingDashboard,
    dashboardError,
    refetchDashboard: fetchDashboardData,

    // SLO definitions
    sloDefinitions,
    loadingDefinitions,
    definitionsError,
    refetchDefinitions: fetchSLODefinitions,

    // SLO measurements
    measurementsBySLO,
    loadingMeasurements,
    measurementsErrors,
    fetchMeasurements,

    // Alerts
    alerts,
    loadingAlerts,
    alertsError,
    alertCount,
    refetchAlerts: fetchAlerts,
    acknowledgeAlert,
    resolveAlert,

    // KPI summary
    kpiSummary,
    loadingKPI,
    kpiError,
    refetchKPI: fetchKPISummary,

    // Trends
    trendData,
    loadingTrends,
    trendsError,
    fetchTrends,

    // Utilities
    formatValue,
    formatTimeAgo,
    getStatusColor,
    calculateTrend,
  }
}