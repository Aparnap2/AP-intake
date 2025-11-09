"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  TrendingUp,
  TrendingDown,
  Target,
  RefreshCw,
  Download,
  AlertCircle,
  Info,
  Zap
} from "lucide-react"

interface SLOData {
  id: string
  name: string
  description: string
  sli_type: string
  target_percentage: number
  target_value: number
  target_unit: string
  status: "healthy" | "warning" | "critical"
  latest_measurement: {
    period_start: string
    period_end: string
    achieved_percentage: number | null
    actual_value: number | null
    error_budget_consumed: number | null
    good_events_count: number
    total_events_count: number
  } | null
  recent_alerts: Array<{
    id: string
    type: string
    severity: string
    title: string
    created_at: string
  }>
  alert_count: number
}

interface DashboardData {
  time_range: {
    start_date: string
    end_date: string
    days: number
  }
  slos: SLOData[]
  summary: {
    total_slos: number
    healthy_slos: number
    warning_slos: number
    critical_slos: number
  }
  alerts: Array<{
    id: string
    slo_name: string
    type: string
    severity: string
    title: string
    message: string
    created_at: string
  }>
}

const SLODashboard = () => {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTimeRange, setSelectedTimeRange] = useState(30)
  const [refreshing, setRefreshing] = useState(false)
  const [selectedTab, setSelectedTab] = useState("overview")

  const timeRanges = [
    { value: 7, label: "Last 7 days" },
    { value: 30, label: "Last 30 days" },
    { value: 90, label: "Last 90 days" },
  ]

  useEffect(() => {
    fetchDashboardData()
  }, [selectedTimeRange])

  const fetchDashboardData = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await fetch(`/api/v1/metrics/slos/dashboard?time_range_days=${selectedTimeRange}`)

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
      setError(err instanceof Error ? err.message : "Failed to load dashboard data")
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await fetchDashboardData()
    } finally {
      setRefreshing(false)
    }
  }

  const getStatusColor = (status: string) => {
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
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "healthy":
        return <CheckCircle2 className="w-4 h-4" />
      case "warning":
        return <AlertTriangle className="w-4 h-4" />
      case "critical":
        return <AlertCircle className="w-4 h-4" />
      default:
        return <Info className="w-4 h-4" />
    }
  }

  const getErrorBudgetColor = (consumed: number | null, target: number) => {
    if (!consumed) return "bg-gray-300"

    const percentage = (consumed / target) * 100
    if (percentage >= 95) return "bg-red-500"
    if (percentage >= 80) return "bg-yellow-500"
    if (percentage >= 50) return "bg-blue-500"
    return "bg-green-500"
  }

  const formatTimeAgo = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return `${diffDays}d ago`
  }

  const formatValue = (value: number | null, unit: string) => {
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
  }

  if (loading && !dashboardData) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center space-x-2">
            <RefreshCw className="w-6 h-6 animate-spin" />
            <span>Loading SLO Dashboard...</span>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Failed to load SLO dashboard: {error}
            <Button variant="outline" size="sm" className="ml-2" onClick={fetchDashboardData}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  if (!dashboardData) {
    return null
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Service Level Objectives</h1>
          <p className="text-slate-600">
            Monitor system performance against SLO targets and error budgets
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedTimeRange}
            onChange={(e) => setSelectedTimeRange(Number(e.target.value))}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {timeRanges.map((range) => (
              <option key={range.value} value={range.value}>
                {range.label}
              </option>
            ))}
          </select>

          <Button variant="outline" onClick={handleRefresh} disabled={refreshing}>
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Button variant="outline">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total SLOs</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{dashboardData.summary.total_slos}</div>
            <p className="text-xs text-muted-foreground">Monitored objectives</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Healthy</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{dashboardData.summary.healthy_slos}</div>
            <p className="text-xs text-muted-foreground">
              {((dashboardData.summary.healthy_slos / dashboardData.summary.total_slos) * 100).toFixed(1)}% of total
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Warning</CardTitle>
            <AlertTriangle className="h-4 w-4 text-yellow-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{dashboardData.summary.warning_slos}</div>
            <p className="text-xs text-muted-foreground">
              {((dashboardData.summary.warning_slos / dashboardData.summary.total_slos) * 100).toFixed(1)}% need attention
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Critical</CardTitle>
            <AlertCircle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{dashboardData.summary.critical_slos}</div>
            <p className="text-xs text-muted-foreground">
              {((dashboardData.summary.critical_slos / dashboardData.summary.total_slos) * 100).toFixed(1)}% need immediate action
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Dashboard Tabs */}
      <Tabs value={selectedTab} onValueChange={setSelectedTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <Target className="w-4 h-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="performance" className="flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Performance
          </TabsTrigger>
          <TabsTrigger value="alerts" className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Alerts
            {dashboardData.alerts.length > 0 && (
              <Badge variant="destructive" className="ml-1 px-1 py-0 text-xs">
                {dashboardData.alerts.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="trends" className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            Trends
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {dashboardData.slos.map((slo) => (
              <Card key={slo.id} className="relative">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(slo.status)}
                      <CardTitle className="text-lg">{slo.name}</CardTitle>
                    </div>
                    <Badge className={getStatusColor(slo.status)}>
                      {slo.status.toUpperCase()}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">{slo.description}</p>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Current Performance */}
                  {slo.latest_measurement ? (
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">Current Performance</span>
                        <span className="text-sm font-bold">
                          {slo.latest_measurement.achieved_percentage?.toFixed(1) || 0}%
                        </span>
                      </div>
                      <Progress
                        value={slo.latest_measurement.achieved_percentage || 0}
                        className="h-2"
                      />
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground">No recent measurements</div>
                  )}

                  {/* Error Budget */}
                  {slo.latest_measurement?.error_budget_consumed !== null && (
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">Error Budget Consumed</span>
                        <span className="text-sm font-bold">
                          {slo.latest_measurement.error_budget_consumed.toFixed(1)}%
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all duration-300 ${getErrorBudgetColor(
                            slo.latest_measurement.error_budget_consumed,
                            100
                          )}`}
                          style={{ width: `${slo.latest_measurement.error_budget_consumed}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Target Info */}
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Target:</span>
                      <div className="font-medium">
                        {formatValue(slo.target_value, slo.target_unit)}
                      </div>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Sample Size:</span>
                      <div className="font-medium">
                        {slo.latest_measurement?.total_events_count || 0} events
                      </div>
                    </div>
                  </div>

                  {/* Recent Alerts */}
                  {slo.recent_alerts.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-sm font-medium">Recent Alerts</span>
                      <div className="space-y-1">
                        {slo.recent_alerts.slice(0, 2).map((alert) => (
                          <div key={alert.id} className="flex items-center gap-2 text-xs">
                            <Badge
                              variant={alert.severity === "critical" ? "destructive" : "secondary"}
                              className="text-xs"
                            >
                              {alert.severity}
                            </Badge>
                            <span className="truncate">{alert.title}</span>
                            <span className="text-muted-foreground whitespace-nowrap">
                              {formatTimeAgo(alert.created_at)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Performance Tab */}
        <TabsContent value="performance" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {dashboardData.slos.map((slo) => (
              <Card key={slo.id}>
                <CardHeader>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(slo.status)}
                    <CardTitle className="text-lg">{slo.name}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {slo.latest_measurement ? (
                    <>
                      <div className="text-center">
                        <div className="text-3xl font-bold">
                          {slo.latest_measurement.achieved_percentage?.toFixed(1) || 0}%
                        </div>
                        <p className="text-sm text-muted-foreground">Achieved</p>
                      </div>

                      <div className="text-center">
                        <div className="text-xl font-semibold">
                          {formatValue(slo.latest_measurement.actual_value, slo.target_unit)}
                        </div>
                        <p className="text-sm text-muted-foreground">Actual vs {formatValue(slo.target_value, slo.target_unit)} Target</p>
                      </div>

                      <div className="text-center">
                        <div className="text-lg font-medium">
                          {slo.latest_measurement.good_events_count} / {slo.latest_measurement.total_events_count}
                        </div>
                        <p className="text-sm text-muted-foreground">Good / Total Events</p>
                      </div>
                    </>
                  ) : (
                    <div className="text-center text-muted-foreground">
                      No performance data available
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Alerts Tab */}
        <TabsContent value="alerts" className="space-y-6">
          {dashboardData.alerts.length > 0 ? (
            <div className="space-y-4">
              {dashboardData.alerts.map((alert) => (
                <Card key={alert.id}>
                  <CardContent className="pt-6">
                    <div className="flex items-start gap-4">
                      <div className="flex-shrink-0">
                        {alert.severity === "critical" ? (
                          <AlertCircle className="w-5 h-5 text-red-600" />
                        ) : (
                          <AlertTriangle className="w-5 h-5 text-yellow-600" />
                        )}
                      </div>
                      <div className="flex-1 space-y-2">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold">{alert.title}</h4>
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={alert.severity === "critical" ? "destructive" : "secondary"}
                            >
                              {alert.severity}
                            </Badge>
                            <span className="text-sm text-muted-foreground">
                              {formatTimeAgo(alert.created_at)}
                            </span>
                          </div>
                        </div>
                        <p className="text-sm text-muted-foreground">{alert.message}</p>
                        <div className="text-xs text-muted-foreground">
                          SLO: {alert.slo_name} • Type: {alert.type}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center text-muted-foreground">
                  <CheckCircle2 className="w-12 h-12 mx-auto mb-4 text-green-500" />
                  <p>No active alerts</p>
                  <p className="text-sm">All SLOs are performing within acceptable ranges</p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Trends Tab */}
        <TabsContent value="trends" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Performance Trends</CardTitle>
              <p className="text-sm text-muted-foreground">
                Historical performance analysis and trend identification
              </p>
            </CardHeader>
            <CardContent>
              <div className="h-64 flex items-center justify-center text-slate-500">
                <div className="text-center">
                  <TrendingUp className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                  <p>Trend analysis charts will be displayed here</p>
                  <p className="text-sm">Historical SLO performance over time</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default SLODashboard