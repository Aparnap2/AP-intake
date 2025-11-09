"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area
} from "recharts"
import {
  TrendingUp,
  TrendingDown,
  BarChart3,
  PieChart as PieChartIcon,
  Activity,
  Users,
  Clock,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Calendar,
  Download,
  RefreshCw,
  Filter,
  Settings,
  Eye,
  Target,
  Zap,
  Award,
  FileText,
  Timer
} from "lucide-react"
import { cn } from "@/lib/utils"
import { getSeverityColor, formatResolutionTime } from "@/lib/exception-types"
import { useExceptionAnalytics } from "@/hooks/useExceptions"

interface ExceptionAnalyticsProps {
  dateRange?: { start: string; end: string }
  onDateRangeChange?: (range: { start: string; end: string }) => void
}

export function ExceptionAnalytics({ dateRange, onDateRangeChange }: ExceptionAnalyticsProps) {
  const { analytics, loading, error, refresh } = useExceptionAnalytics(dateRange)
  const [activeTab, setActiveTab] = useState("overview")
  const [timeRange, setTimeRange] = useState("30d")

  // Mock data for charts (replace with real data)
  const resolutionTrendData = [
    { date: "2024-01-01", resolved: 12, opened: 15 },
    { date: "2024-01-02", resolved: 18, opened: 22 },
    { date: "2024-01-03", resolved: 15, opened: 18 },
    { date: "2024-01-04", resolved: 22, opened: 25 },
    { date: "2024-01-05", resolved: 28, opened: 20 },
    { date: "2024-01-06", resolved: 25, opened: 30 },
    { date: "2024-01-07", resolved: 30, opened: 28 },
  ]

  const reasonBreakdownData = analytics ? Object.entries(analytics.exceptions_by_reason).map(([reason, count]) => ({
    name: reason.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
    value: count,
    color: reason.includes("confidence") ? "#3b82f6" :
           reason.includes("missing") ? "#ef4444" :
           reason.includes("vendor") ? "#f59e0b" :
           reason.includes("amount") ? "#10b981" : "#6b7280"
  })) : []

  const severityBreakdownData = analytics ? Object.entries(analytics.exceptions_by_severity).map(([severity, count]) => ({
    name: severity.charAt(0).toUpperCase() + severity.slice(1),
    value: count,
    color: severity === "critical" ? "#dc2626" :
           severity === "high" ? "#ea580c" :
           severity === "medium" ? "#ca8a04" : "#2563eb"
  })) : []

  const topPerformersData = analytics?.top_resolvers?.map(perf => ({
    name: perf.user_id.split('.').map(n => n[0]).join('').toUpperCase(),
    resolved: perf.resolved_count,
    avgTime: perf.avg_time_hours
  })) || []

  const COLORS = ['#3b82f6', '#ef4444', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']

  const handleDateRangeChange = (range: string) => {
    setTimeRange(range)

    let dateRange = { start: '', end: '' }
    const now = new Date()

    switch (range) {
      case "7d":
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
        dateRange = { start: weekAgo.toISOString(), end: now.toISOString() }
        break
      case "30d":
        const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
        dateRange = { start: monthAgo.toISOString(), end: now.toISOString() }
        break
      case "90d":
        const quarterAgo = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000)
        dateRange = { start: quarterAgo.toISOString(), end: now.toISOString() }
        break
      case "1y":
        const yearAgo = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000)
        dateRange = { start: yearAgo.toISOString(), end: now.toISOString() }
        break
    }

    onDateRangeChange?.(dateRange)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="text-center space-y-4">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-blue-600" />
          <p className="text-slate-600">Loading analytics...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="text-center space-y-4">
          <AlertTriangle className="w-12 h-12 text-red-600 mx-auto" />
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Error loading analytics</h3>
            <p className="text-slate-600">{error}</p>
          </div>
          <Button variant="outline" onClick={refresh}>
            Try Again
          </Button>
        </div>
      </div>
    )
  }

  if (!analytics) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="text-center space-y-4">
          <BarChart3 className="w-12 h-12 text-slate-400 mx-auto" />
          <div>
            <h3 className="text-lg font-semibold text-slate-900">No analytics data available</h3>
            <p className="text-slate-600">Analytics will appear once exceptions are processed.</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Exception Analytics</h1>
          <p className="text-slate-600">Insights and metrics for exception management</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={timeRange} onValueChange={handleDateRangeChange}>
            <SelectTrigger className="w-32">
              <Calendar className="w-4 h-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
              <SelectItem value="1y">Last year</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={refresh}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Total Exceptions</p>
                <div className="text-2xl font-bold">{analytics.total_exceptions}</div>
                <div className="flex items-center gap-1 mt-1">
                  <TrendingUp className="w-3 h-3 text-green-600" />
                  <span className="text-xs text-green-600">+12% from last period</span>
                </div>
              </div>
              <FileText className="w-8 h-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Open Exceptions</p>
                <div className="text-2xl font-bold">{analytics.open_exceptions}</div>
                <div className="flex items-center gap-1 mt-1">
                  <TrendingDown className="w-3 h-3 text-green-600" />
                  <span className="text-xs text-green-600">-8% from last period</span>
                </div>
              </div>
              <AlertCircle className="w-8 h-8 text-orange-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Resolved Today</p>
                <div className="text-2xl font-bold">{analytics.resolved_today}</div>
                <div className="flex items-center gap-1 mt-1">
                  <TrendingUp className="w-3 h-3 text-green-600" />
                  <span className="text-xs text-green-600">+25% from yesterday</span>
                </div>
              </div>
              <CheckCircle2 className="w-8 h-8 text-green-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Avg Resolution Time</p>
                <div className="text-2xl font-bold">
                  {formatResolutionTime(analytics.avg_resolution_time_hours)}
                </div>
                <div className="flex items-center gap-1 mt-1">
                  <TrendingDown className="w-3 h-3 text-green-600" />
                  <span className="text-xs text-green-600">-15% improvement</span>
                </div>
              </div>
              <Timer className="w-8 h-8 text-purple-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts and Analysis */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="trends">Trends</TabsTrigger>
          <TabsTrigger value="breakdown">Breakdown</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="insights">Insights</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Resolution Trend */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="w-5 h-5" />
                  Resolution Trend
                </CardTitle>
                <CardDescription>
                  Daily comparison of exceptions opened vs resolved
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={analytics.resolution_trend}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tickFormatter={(value) => new Date(value).toLocaleDateString()} />
                    <YAxis />
                    <Tooltip
                      labelFormatter={(value) => new Date(value).toLocaleDateString()}
                      formatter={(value, name) => [value, name === 'resolved' ? 'Resolved' : 'Opened']}
                    />
                    <Line
                      type="monotone"
                      dataKey="resolved"
                      stroke="#10b981"
                      strokeWidth={2}
                      dot={{ fill: '#10b981' }}
                    />
                    <Line
                      type="monotone"
                      dataKey="opened"
                      stroke="#f59e0b"
                      strokeWidth={2}
                      dot={{ fill: '#f59e0b' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Reason Breakdown */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <PieChartIcon className="w-5 h-5" />
                  Exception Reasons
                </CardTitle>
                <CardDescription>
                  Distribution of exceptions by reason code
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={reasonBreakdownData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {reasonBreakdownData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Trends Tab */}
        <TabsContent value="trends" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Volume Trend */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5" />
                  Exception Volume Trend
                </CardTitle>
                <CardDescription>
                  Exception volume over time with 7-day moving average
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={analytics.resolution_trend}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tickFormatter={(value) => new Date(value).toLocaleDateString()} />
                    <YAxis />
                    <Tooltip
                      labelFormatter={(value) => new Date(value).toLocaleDateString()}
                    />
                    <Area
                      type="monotone"
                      dataKey="opened"
                      stroke="#3b82f6"
                      fill="#93bbfc"
                      fillOpacity={0.6}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Resolution Rate */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="w-5 h-5" />
                  Resolution Rate
                </CardTitle>
                <CardDescription>
                  Daily resolution rate percentage
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={analytics.resolution_trend.map(item => ({
                    ...item,
                    rate: item.resolved > 0 ? (item.resolved / (item.resolved + item.opened) * 100) : 0
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={(value) => new Date(value).toLocaleDateString()} />
                <YAxis domain={[0, 100]} />
                <Tooltip
                  labelFormatter={(value) => new Date(value).toLocaleDateString()}
                  formatter={(value) => [`${Number(value).toFixed(1)}%`, 'Resolution Rate']}
                />
                <Line
                  type="monotone"
                  dataKey="rate"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ fill: '#10b981' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Weekly Pattern */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="w-5 h-5" />
            Weekly Pattern
          </CardTitle>
          <CardDescription>
            Exception activity by day of week
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-7 gap-2">
            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, index) => (
              <div key={day} className="text-center">
                <div className="text-xs text-slate-600 mb-2">{day}</div>
                <div className={cn(
                  "h-20 rounded flex items-end justify-center text-xs font-medium",
                  index < 5 ? "bg-blue-100" : "bg-slate-100"
                )}>
                  <span className="pb-1">
                    {index < 5 ? Math.floor(Math.random() * 20) + 10 : Math.floor(Math.random() * 5) + 2}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </TabsContent>

    {/* Breakdown Tab */}
    <TabsContent value="breakdown" className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Severity Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5" />
              Severity Breakdown
            </CardTitle>
            <CardDescription>
              Exception distribution by severity level
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {severityBreakdownData.map((item) => (
                <div key={item.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="font-medium">{item.name}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-24 bg-slate-200 rounded-full h-2">
                      <div
                        className="h-2 rounded-full"
                        style={{
                          width: `${(item.value / analytics.total_exceptions) * 100}%`,
                          backgroundColor: item.color
                        }}
                      />
                    </div>
                    <span className="text-sm font-medium w-12 text-right">{item.value}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Top Exception Types */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5" />
              Top Exception Types
            </CardTitle>
            <CardDescription>
              Most frequent exception reasons
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={reasonBreakdownData.slice(0, 5)} layout="horizontal">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis dataKey="name" type="category" width={100} />
                <Tooltip />
                <Bar dataKey="value" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </TabsContent>

    {/* Performance Tab */}
    <TabsContent value="performance" className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Performers */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5" />
              Top Performers
            </CardTitle>
            <CardDescription>
              Team members with highest resolution counts
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {topPerformersData.map((performer, index) => (
                <div key={performer.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold",
                      index === 0 ? "bg-yellow-100 text-yellow-800" :
                      index === 1 ? "bg-gray-100 text-gray-800" :
                      index === 2 ? "bg-orange-100 text-orange-800" :
                      "bg-blue-100 text-blue-800"
                    )}>
                      {index + 1}
                    </div>
                    <div>
                      <div className="font-medium">{performer.name}</div>
                      <div className="text-sm text-slate-600">
                        {formatResolutionTime(performer.avgTime)} avg time
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold">{performer.resolved}</div>
                    <div className="text-sm text-slate-600">resolved</div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Performance Metrics */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Award className="w-5 h-5" />
              Performance Metrics
            </CardTitle>
            <CardDescription>
              Key performance indicators
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">First Response Time</span>
                <span className="text-sm text-slate-600">2.3 hours</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-2">
                <div className="bg-green-500 h-2 rounded-full" style={{ width: "75%" }} />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Resolution Quality</span>
                <span className="text-sm text-slate-600">94%</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-2">
                <div className="bg-blue-500 h-2 rounded-full" style={{ width: "94%" }} />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Customer Satisfaction</span>
                <span className="text-sm text-slate-600">4.6/5.0</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-2">
                <div className="bg-purple-500 h-2 rounded-full" style={{ width: "92%" }} />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Automation Rate</span>
                <span className="text-sm text-slate-600">67%</span>
              </div>
              <div className="w-full bg-slate-200 rounded-full h-2">
                <div className="bg-orange-500 h-2 rounded-full" style={{ width: "67%" }} />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </TabsContent>

    {/* Insights Tab */}
    <TabsContent value="insights" className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Key Insights */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="w-5 h-5" />
              Key Insights
            </CardTitle>
            <CardDescription>
              AI-powered insights and recommendations
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-green-600 mt-0.5" />
                <div>
                  <h4 className="font-medium text-green-900">Resolution Time Improved</h4>
                  <p className="text-sm text-green-700 mt-1">
                    Average resolution time decreased by 15% this month, indicating improved efficiency.
                  </p>
                </div>
              </div>
            </div>

            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-start gap-3">
                <Eye className="w-5 h-5 text-blue-600 mt-0.5" />
                <div>
                  <h4 className="font-medium text-blue-900">Vendor Issues Identified</h4>
                  <p className="text-sm text-blue-700 mt-1">
                    3 vendors account for 40% of exceptions. Consider vendor outreach program.
                  </p>
                </div>
              </div>
            </div>

            <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5" />
                <div>
                  <h4 className="font-medium text-amber-900">Confidence Threshold Impact</h4>
                  <p className="text-sm text-amber-700 mt-1">
                    60% of exceptions are due to low confidence. Consider adjusting extraction model.
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Recommendations */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="w-5 h-5" />
              Recommendations
            </CardTitle>
            <CardDescription>
              Actionable recommendations to improve exception handling
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <div className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">1</div>
                <div>
                  <h4 className="font-medium">Optimize Extraction Model</h4>
                  <p className="text-sm text-slate-600">
                    Retrain the document extraction model with recent samples to improve confidence scores.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">2</div>
                <div>
                  <h4 className="font-medium">Implement Auto-Assignment</h4>
                  <p className="text-sm text-slate-600">
                    Set up automatic assignment based on exception type and team expertise.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">3</div>
                <div>
                  <h4 className="font-medium">Vendor Communication</h4>
                  <p className="text-sm text-slate-600">
                    Create templates for common vendor communications to reduce resolution time.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">4</div>
                <div>
                  <h4 className="font-medium">Weekly Reviews</h4>
                  <p className="text-sm text-slate-600">
                    Schedule weekly exception reviews to identify patterns and prevent recurring issues.
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </TabsContent>
  </Tabs>
</div>
  )
}