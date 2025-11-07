"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import {
  Activity,
  Play,
  Pause,
  Square,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Mail,
  FileText,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Eye,
  Trash2,
  MoreHorizontal,
  Zap,
  Server,
  Database,
  Cpu,
  Wifi,
  Download,
  ExternalLink,
  Calendar,
  Filter,
  Search,
  XCircle,
  AlertCircle,
  Info,
  List,
  Grid3X3,
  ArrowUp,
  ArrowDown,
  Minus
} from "lucide-react"
import { cn } from "@/lib/utils"

interface EmailProcessingJob {
  id: string
  accountId: string
  accountEmail: string
  status: "pending" | "running" | "completed" | "failed" | "cancelled" | "paused"
  startedAt: string
  completedAt?: string
  emailsProcessed: number
  totalEmails: number
  invoicesFound: number
  errors: string[]
  progress: number
  processingRate?: number
  estimatedTimeRemaining?: number
  retryCount?: number
  maxRetries?: number
}

interface ProcessingStats {
  totalJobs: number
  activeJobs: number
  completedJobs: number
  failedJobs: number
  avgProcessingTime: number
  successRate: number
  emailsProcessedToday: number
  invoicesFoundToday: number
  systemLoad: number
}

interface EmailProcessingMonitorProps {
  jobs: EmailProcessingJob[]
}

export function EmailProcessingMonitor({ jobs }: EmailProcessingMonitorProps) {
  const [processingJobs, setProcessingJobs] = useState<EmailProcessingJob[]>(jobs)
  const [selectedJob, setSelectedJob] = useState<EmailProcessingJob | null>(null)
  const [showJobDetails, setShowJobDetails] = useState(false)
  const [activeView, setActiveView] = useState<"active" | "completed" | "failed">("active")
  const [refreshing, setRefreshing] = useState(false)
  const [stats, setStats] = useState<ProcessingStats>({
    totalJobs: jobs.length,
    activeJobs: jobs.filter(job => job.status === "running").length,
    completedJobs: jobs.filter(job => job.status === "completed").length,
    failedJobs: jobs.filter(job => job.status === "failed").length,
    avgProcessingTime: 2.3,
    successRate: 94.2,
    emailsProcessedToday: 1247,
    invoicesFoundToday: 47,
    systemLoad: 65
  })

  // Simulate real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      setProcessingJobs(prev => prev.map(job => {
        if (job.status === "running" && job.progress < 100) {
          const newProgress = Math.min(job.progress + Math.random() * 5, 100)
          const newEmailsProcessed = Math.floor((newProgress / 100) * job.totalEmails)
          const newInvoicesFound = Math.floor(newEmailsProcessed * 0.15) // 15% invoice detection rate

          return {
            ...job,
            progress: newProgress,
            emailsProcessed: newEmailsProcessed,
            invoicesFound: newInvoicesFound,
            processingRate: 12.5 + Math.random() * 5,
            estimatedTimeRemaining: newProgress < 100 ? (100 - newProgress) / 5 : 0
          }
        }
        return job
      }))

      // Update stats
      setStats(prev => ({
        ...prev,
        emailsProcessedToday: prev.emailsProcessedToday + Math.floor(Math.random() * 3),
        invoicesFoundToday: Math.max(0, prev.invoicesFoundToday + (Math.random() > 0.7 ? 1 : 0)),
        systemLoad: Math.max(20, Math.min(90, prev.systemLoad + (Math.random() - 0.5) * 10))
      }))
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  const handleRefreshJobs = async () => {
    setRefreshing(true)
    // Simulate API call
    setTimeout(() => {
      setRefreshing(false)
    }, 1500)
  }

  const handlePauseJob = (jobId: string) => {
    setProcessingJobs(prev => prev.map(job =>
      job.id === jobId ? { ...job, status: "paused" as const } : job
    ))
  }

  const handleResumeJob = (jobId: string) => {
    setProcessingJobs(prev => prev.map(job =>
      job.id === jobId ? { ...job, status: "running" as const } : job
    ))
  }

  const handleCancelJob = (jobId: string) => {
    setProcessingJobs(prev => prev.map(job =>
      job.id === jobId ? { ...job, status: "cancelled" as const } : job
    ))
  }

  const handleRetryJob = (jobId: string) => {
    setProcessingJobs(prev => prev.map(job =>
      job.id === jobId ? {
        ...job,
        status: "pending" as const,
        errors: [],
        retryCount: (job.retryCount || 0) + 1
      } : job
    ))
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running":
        return "bg-blue-50 text-blue-700 border-blue-200"
      case "completed":
        return "bg-green-50 text-green-700 border-green-200"
      case "failed":
        return "bg-red-50 text-red-700 border-red-200"
      case "cancelled":
        return "bg-gray-50 text-gray-700 border-gray-200"
      case "paused":
        return "bg-yellow-50 text-yellow-700 border-yellow-200"
      default:
        return "bg-slate-50 text-slate-700 border-slate-200"
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "running":
        return <Activity className="w-4 h-4 text-blue-600" />
      case "completed":
        return <CheckCircle2 className="w-4 h-4 text-green-600" />
      case "failed":
        return <XCircle className="w-4 h-4 text-red-600" />
      case "cancelled":
        return <Square className="w-4 h-4 text-gray-600" />
      case "paused":
        return <Pause className="w-4 h-4 text-yellow-600" />
      default:
        return <Clock className="w-4 h-4 text-slate-600" />
    }
  }

  const filteredJobs = processingJobs.filter(job => {
    switch (activeView) {
      case "active":
        return ["pending", "running", "paused"].includes(job.status)
      case "completed":
        return job.status === "completed"
      case "failed":
        return job.status === "failed"
      default:
        return true
    }
  })

  const activeJobs = filteredJobs.filter(job => ["running", "paused"].includes(job.status))

  return (
    <div className="space-y-6">
      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Jobs</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.activeJobs}</div>
            <p className="text-xs text-muted-foreground">
              {stats.totalJobs} total jobs today
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.successRate}%</div>
            <p className="text-xs text-muted-foreground">
              {stats.completedJobs} completed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Emails Processed</CardTitle>
            <Mail className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.emailsProcessedToday.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              Today so far
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Load</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.systemLoad}%</div>
            <p className="text-xs text-muted-foreground">
              CPU utilization
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Active Jobs Overview */}
      {activeJobs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="w-5 h-5" />
              Active Processing
            </CardTitle>
            <CardDescription>
              Real-time monitoring of running email processing jobs
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {activeJobs.map((job) => (
                <div key={job.id} className="p-4 border rounded-lg space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {getStatusIcon(job.status)}
                      <div>
                        <div className="font-medium">{job.accountEmail}</div>
                        <div className="text-sm text-slate-500">
                          Job ID: {job.id}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={getStatusColor(job.status)}>
                        {job.status}
                      </Badge>
                      <Badge variant="outline">
                        {job.invoicesFound} invoices found
                      </Badge>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Progress: {job.emailsProcessed.toLocaleString()} / {job.totalEmails.toLocaleString()} emails</span>
                      <span>{job.progress.toFixed(1)}%</span>
                    </div>
                    <Progress value={job.progress} className="h-2" />
                  </div>

                  <div className="flex items-center justify-between text-sm text-slate-600">
                    <div className="flex items-center gap-4">
                      <span>Rate: {job.processingRate?.toFixed(1) || 0} emails/min</span>
                      {job.estimatedTimeRemaining && job.estimatedTimeRemaining > 0 && (
                        <span>ETA: {Math.ceil(job.estimatedTimeRemaining)} min</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => job.status === "running" ? handlePauseJob(job.id) : handleResumeJob(job.id)}
                      >
                        {job.status === "running" ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleCancelJob(job.id)}
                      >
                        <Square className="w-3 h-3" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setSelectedJob(job)
                          setShowJobDetails(true)
                        }}
                      >
                        <Eye className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Job Queue Management */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Processing Queue</CardTitle>
              <CardDescription>
                Manage and monitor all email processing jobs
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={handleRefreshJobs}
                disabled={refreshing}
              >
                <RefreshCw className={cn("w-4 h-4 mr-2", refreshing && "animate-spin")} />
                Refresh
              </Button>
            </div>
          </div>

          {/* View Tabs */}
          <Tabs value={activeView} onValueChange={(value) => setActiveView(value as any)}>
            <TabsList>
              <TabsTrigger value="active">
                Active ({filteredJobs.filter(j => ["pending", "running", "paused"].includes(j.status)).length})
              </TabsTrigger>
              <TabsTrigger value="completed">
                Completed ({filteredJobs.filter(j => j.status === "completed").length})
              </TabsTrigger>
              <TabsTrigger value="failed">
                Failed ({filteredJobs.filter(j => j.status === "failed").length})
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job</TableHead>
                  <TableHead>Account</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Progress</TableHead>
                  <TableHead>Emails</TableHead>
                  <TableHead>Invoices</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredJobs.map((job) => (
                  <TableRow key={job.id} className="cursor-pointer hover:bg-slate-50">
                    <TableCell className="font-mono text-sm">{job.id}</TableCell>
                    <TableCell>{job.accountEmail}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(job.status)}
                        <Badge className={getStatusColor(job.status)}>
                          {job.status}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <Progress value={job.progress} className="h-1 flex-1" />
                          <span className="text-xs text-slate-600">{job.progress.toFixed(0)}%</span>
                        </div>
                        {job.status === "failed" && job.retryCount && (
                          <div className="text-xs text-amber-600">
                            Retry {job.retryCount}/{job.maxRetries || 3}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        {job.emailsProcessed.toLocaleString()} / {job.totalEmails.toLocaleString()}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {job.invoicesFound}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm">
                      {new Date(job.startedAt).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-sm">
                      {job.completedAt
                        ? `${Math.round((new Date(job.completedAt).getTime() - new Date(job.startedAt).getTime()) / 60000)}m`
                        : job.status === "running"
                          ? `${Math.round((new Date().getTime() - new Date(job.startedAt).getTime()) / 60000)}m`
                          : "-"
                      }
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => {
                            setSelectedJob(job)
                            setShowJobDetails(true)
                          }}>
                            <Eye className="w-4 h-4 mr-2" />
                            View Details
                          </DropdownMenuItem>
                          {job.status === "running" && (
                            <DropdownMenuItem onClick={() => handlePauseJob(job.id)}>
                              <Pause className="w-4 h-4 mr-2" />
                              Pause
                            </DropdownMenuItem>
                          )}
                          {job.status === "paused" && (
                            <DropdownMenuItem onClick={() => handleResumeJob(job.id)}>
                              <Play className="w-4 h-4 mr-2" />
                              Resume
                            </DropdownMenuItem>
                          )}
                          {["running", "paused"].includes(job.status) && (
                            <DropdownMenuItem onClick={() => handleCancelJob(job.id)}>
                              <Square className="w-4 h-4 mr-2" />
                              Cancel
                            </DropdownMenuItem>
                          )}
                          {job.status === "failed" && (
                            <DropdownMenuItem onClick={() => handleRetryJob(job.id)}>
                              <RefreshCw className="w-4 h-4 mr-2" />
                              Retry
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuSeparator />
                          <DropdownMenuItem>
                            <Download className="w-4 h-4 mr-2" />
                            Download Logs
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* System Performance */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            System Performance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 border rounded-lg space-y-2">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-blue-600" />
                <span className="font-medium">Processing Queue</span>
              </div>
              <div className="text-2xl font-bold">{activeJobs.length}</div>
              <div className="text-sm text-slate-600">Jobs in queue</div>
            </div>

            <div className="p-4 border rounded-lg space-y-2">
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-green-600" />
                <span className="font-medium">Avg Processing Time</span>
              </div>
              <div className="text-2xl font-bold">{stats.avgProcessingTime}s</div>
              <div className="text-sm text-slate-600">Per email</div>
            </div>

            <div className="p-4 border rounded-lg space-y-2">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-purple-600" />
                <span className="font-medium">Detection Rate</span>
              </div>
              <div className="text-2xl font-bold">15.2%</div>
              <div className="text-sm text-slate-600">Invoice emails found</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Job Details Dialog */}
      <Dialog open={showJobDetails} onOpenChange={setShowJobDetails}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Job Details</DialogTitle>
            <DialogDescription>
              Detailed information about email processing job
            </DialogDescription>
          </DialogHeader>

          {selectedJob && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-slate-600">Job ID</label>
                  <div className="font-mono text-sm">{selectedJob.id}</div>
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-600">Status</label>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(selectedJob.status)}
                    <Badge className={getStatusColor(selectedJob.status)}>
                      {selectedJob.status}
                    </Badge>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-600">Account</label>
                  <div className="text-sm">{selectedJob.accountEmail}</div>
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-600">Started</label>
                  <div className="text-sm">{new Date(selectedJob.startedAt).toLocaleString()}</div>
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="font-medium">Processing Progress</h4>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Emails Processed</span>
                    <span>{selectedJob.emailsProcessed.toLocaleString()} / {selectedJob.totalEmails.toLocaleString()}</span>
                  </div>
                  <Progress value={selectedJob.progress} />
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="flex justify-between">
                    <span>Invoices Found:</span>
                    <span className="font-semibold">{selectedJob.invoicesFound}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Processing Rate:</span>
                    <span className="font-semibold">{selectedJob.processingRate?.toFixed(1) || 0} emails/min</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Success Rate:</span>
                    <span className="font-semibold text-green-600">
                      {((selectedJob.emailsProcessed - (selectedJob.errors?.length || 0)) / selectedJob.emailsProcessed * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Est. Time Remaining:</span>
                    <span className="font-semibold">
                      {selectedJob.estimatedTimeRemaining ? `${Math.ceil(selectedJob.estimatedTimeRemaining)} min` : "N/A"}
                    </span>
                  </div>
                </div>
              </div>

              {selectedJob.errors && selectedJob.errors.length > 0 && (
                <div className="space-y-3">
                  <h4 className="font-medium text-red-600">Errors ({selectedJob.errors.length})</h4>
                  <div className="space-y-2">
                    {selectedJob.errors.map((error, index) => (
                      <div key={index} className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-800">
                        {error}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowJobDetails(false)}>
                  Close
                </Button>
                {selectedJob.status === "failed" && (
                  <Button onClick={() => handleRetryJob(selectedJob.id)}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Retry Job
                  </Button>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}