"use client"

import { useState, useEffect } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
  BarChart3,
  TrendingUp,
  Activity,
  Users,
  FileText,
  Target,
  RefreshCw,
  Download,
  Settings,
  Eye,
  Calendar
} from "lucide-react"

export default function AnalyticsPage() {
  const [selectedTimeRange, setSelectedTimeRange] = useState("30d")
  const [activeTab, setActiveTab] = useState("overview")
  const [loading, setLoading] = useState(false)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())

  // Mock trend data for demonstration
  const volumeTrendData = Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    value: Math.floor(50 + Math.random() * 20)
  }))
  const accuracyTrendData = Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    value: 0.92 + (Math.random() - 0.5) * 0.1
  }))
  const exceptionTrendData = Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    value: Math.floor(8 + Math.random() * 6)
  }))

  const timeRanges = [
    { value: "7d", label: "Last 7 days" },
    { value: "30d", label: "Last 30 days" },
    { value: "90d", label: "Last 90 days" },
    { value: "1y", label: "Last year" }
  ]

  const handleRefresh = async () => {
    setLoading(true)
    try {
      // Simulate API refresh
      await new Promise(resolve => setTimeout(resolve, 1000))
      setLastRefresh(new Date())
    } catch (error) {
      console.error("Error refreshing data:", error)
    } finally {
      setLoading(false)
    }
  }

  const handleExport = () => {
    // Implement export functionality
    console.log("Exporting dashboard data...")
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Analytics Dashboard</h1>
          <p className="text-slate-600">
            Comprehensive KPI monitoring and performance insights
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={selectedTimeRange} onValueChange={setSelectedTimeRange}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {timeRanges.map((range) => (
                <SelectItem key={range.value} value={range.value}>
                  {range.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button variant="outline" onClick={handleRefresh} disabled={loading}>
            <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
            Refresh
          </Button>

          <Button onClick={handleExport}>
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>

          <Button variant="outline" size="icon">
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Last Updated */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Activity className="w-4 h-4" />
        <span>Last updated: {lastRefresh.toLocaleTimeString()}</span>
        <Badge variant="secondary">Live</Badge>
      </div>

      {/* Main Dashboard Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="realtime" className="flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Real-Time
          </TabsTrigger>
          <TabsTrigger value="trends" className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            Trends
          </TabsTrigger>
          <TabsTrigger value="performance" className="flex items-center gap-2">
            <Target className="w-4 h-4" />
            Performance
          </TabsTrigger>
          <TabsTrigger value="team" className="flex items-center gap-2">
            <Users className="w-4 h-4" />
            Team
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab - Main KPI Dashboard */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Invoices</CardTitle>
                <FileText className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">1,247</div>
                <p className="text-xs text-muted-foreground">+12% from last month</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Processing Rate</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">94.7%</div>
                <p className="text-xs text-muted-foreground">+2.1% improvement</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Exceptions</CardTitle>
                <Target className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">8.2%</div>
                <p className="text-xs text-muted-foreground">-1.5% from last month</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Avg. Time</CardTitle>
                <Calendar className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">2.4h</div>
                <p className="text-xs text-muted-foreground">-30min improvement</p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Real-Time Tab */}
        <TabsContent value="realtime" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Real-Time Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-64 flex items-center justify-center text-slate-500">
                <div className="text-center">
                  <Activity className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                  <p>Real-time monitoring would go here</p>
                  <p className="text-sm">Live processing metrics and alerts</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Trends Tab */}
        <TabsContent value="trends" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Invoice Volume Trend</CardTitle>
                <p className="text-sm text-muted-foreground">Daily invoice volume over the selected period</p>
              </CardHeader>
              <CardContent>
                <div className="h-64 flex items-center justify-center text-slate-500">
                  <div className="text-center">
                    <BarChart3 className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                    <p>Chart visualization would go here</p>
                    <p className="text-sm">Volume: {volumeTrendData.reduce((sum, d) => sum + d.value, 0)} total</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Extraction Accuracy Trend</CardTitle>
                <p className="text-sm text-muted-foreground">Average confidence score for document extraction</p>
              </CardHeader>
              <CardContent>
                <div className="h-64 flex items-center justify-center text-slate-500">
                  <div className="text-center">
                    <TrendingUp className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                    <p>Chart visualization would go here</p>
                    <p className="text-sm">Accuracy: {(accuracyTrendData.reduce((sum, d) => sum + d.value, 0) / accuracyTrendData.length * 100).toFixed(1)}%</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Exception Trend</CardTitle>
                <p className="text-sm text-muted-foreground">Daily exception count over time</p>
              </CardHeader>
              <CardContent>
                <div className="h-64 flex items-center justify-center text-slate-500">
                  <div className="text-center">
                    <Activity className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                    <p>Chart visualization would go here</p>
                    <p className="text-sm">Exceptions: {exceptionTrendData.reduce((sum, d) => sum + d.value, 0)} total</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Trend Analysis Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="text-center p-4 bg-blue-50 rounded-lg">
                    <TrendingUp className="w-8 h-8 mx-auto mb-2 text-blue-600" />
                    <div className="font-semibold text-blue-900">Volume Trend</div>
                    <div className="text-sm text-blue-700">Increasing</div>
                    <div className="text-xs text-blue-600 mt-1">+18% vs last period</div>
                  </div>
                  <div className="text-center p-4 bg-green-50 rounded-lg">
                    <TrendingUp className="w-8 h-8 mx-auto mb-2 text-green-600" />
                    <div className="font-semibold text-green-900">Accuracy Trend</div>
                    <div className="text-sm text-green-700">Improving</div>
                    <div className="text-xs text-green-600 mt-1">+2.3% improvement</div>
                  </div>
                  <div className="text-center p-4 bg-orange-50 rounded-lg">
                    <TrendingUp className="w-8 h-8 mx-auto mb-2 text-orange-600" />
                    <div className="font-semibold text-orange-900">Exception Trend</div>
                    <div className="text-sm text-orange-700">Decreasing</div>
                    <div className="text-xs text-orange-600 mt-1">-15% vs last period</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Performance Tab */}
        <TabsContent value="performance" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Processing Speed</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">2.3s</div>
                <p className="text-xs text-muted-foreground">Average processing time</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
                <Target className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">96.8%</div>
                <p className="text-xs text-muted-foreground">Successful processing</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Daily Volume</CardTitle>
                <FileText className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">847</div>
                <p className="text-xs text-muted-foreground">Invoices processed today</p>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Processing Efficiency</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {[
                    { stage: "Document Reception", efficiency: 98, trend: "stable" },
                    { stage: "Data Extraction", efficiency: 94, trend: "improving" },
                    { stage: "Validation", efficiency: 89, trend: "improving" },
                    { stage: "Exception Resolution", efficiency: 87, trend: "stable" },
                    { stage: "Export Preparation", efficiency: 96, trend: "improving" }
                  ].map((item) => (
                    <div key={item.stage} className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">{item.stage}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold">{item.efficiency}%</span>
                          <Badge
                            variant={item.trend === "improving" ? "default" : "secondary"}
                            className="text-xs"
                          >
                            {item.trend}
                          </Badge>
                        </div>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${item.efficiency}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Quality Metrics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  <div className="text-center">
                    <div className="text-4xl font-bold text-green-600">94.7%</div>
                    <div className="text-sm text-muted-foreground">Overall Accuracy</div>
                    <div className="text-xs text-green-600 mt-1">+2.1% from last month</div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center p-3 bg-gray-50 rounded-lg">
                      <div className="text-lg font-bold">89.2%</div>
                      <div className="text-xs text-muted-foreground">Validation Pass Rate</div>
                    </div>
                    <div className="text-center p-3 bg-gray-50 rounded-lg">
                      <div className="text-lg font-bold">12.1%</div>
                      <div className="text-xs text-muted-foreground">Exception Rate</div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>High Confidence Extractions</span>
                      <span className="font-medium">78%</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span>Medium Confidence Extractions</span>
                      <span className="font-medium">17%</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span>Low Confidence Extractions</span>
                      <span className="font-medium">5%</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Team Tab */}
        <TabsContent value="team" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Team Members</CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">8</div>
                <p className="text-xs text-muted-foreground">
                  6 active, 2 on leave
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Avg Resolution Time</CardTitle>
                <Calendar className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">2.4h</div>
                <p className="text-xs text-muted-foreground">
                  -30min from last week
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Resolved Today</CardTitle>
                <Eye className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">24</div>
                <p className="text-xs text-muted-foreground">
                  On track for daily goal
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Team Efficiency</CardTitle>
                <Target className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">91%</div>
                <p className="text-xs text-muted-foreground">
                  Above target threshold
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Team Performance Overview</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">
                Detailed team analytics and individual performance metrics will be available here.
                This section will include reviewer rankings, workload distribution, and productivity analytics.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

