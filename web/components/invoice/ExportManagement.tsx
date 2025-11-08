"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Download,
  Upload,
  FileText,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Settings,
  Play,
  Pause,
  RotateCcw,
  Eye,
  EyeOff,
  Calendar,
  Filter,
  Search,
  RefreshCw,
  ChevronRight,
  Database,
  FileSpreadsheet,
  FileJson,
  FileDown,
  Zap,
  Target,
  BarChart3,
  PieChart,
  Activity,
  Globe,
  Shield,
  Key,
  Users,
  Mail,
  Phone,
  MapPin,
  Star,
  Archive,
  Send,
  Copy,
  Share2,
  Printer,
  ExternalLink,
  HelpCircle,
  Info,
  Plus,
  MoreHorizontal,
  Edit,
  Trash2
} from "lucide-react"
import { cn } from "@/lib/utils"

// Types
interface ExportTemplate {
  id: string
  name: string
  description: string
  format: "csv" | "json" | "xml" | "xlsx" | "quickbooks" | "sap" | "custom"
  fields: ExportField[]
  filters: ExportFilter[]
  schedule?: ExportSchedule
  isActive: boolean
  lastExport?: string
  exportCount: number
  createdBy: string
  createdAt: string
}

interface ExportField {
  id: string
  name: string
  source: string // invoice field path
  transform?: string // transformation logic
  required: boolean
  format?: string
}

interface ExportFilter {
  id: string
  field: string
  operator: "equals" | "contains" | "greater_than" | "less_than" | "between" | "in"
  value: any
  required: boolean
}

interface ExportSchedule {
  enabled: boolean
  frequency: "daily" | "weekly" | "monthly"
  time: string
  recipients: string[]
  autoExport: boolean
}

interface ExportJob {
  id: string
  templateId: string
  templateName: string
  status: "pending" | "running" | "completed" | "failed" | "cancelled"
  progress: number
  startTime: string
  endTime?: string
  recordCount: number
  successCount: number
  errorCount: number
  fileUrl?: string
  errorDetails?: string
  triggeredBy: string
  format: string
  size?: number
}

interface QuickBooksConfig {
  companyId: string
  accessToken: string
  refreshToken: string
  realmId: string
  sandboxMode: boolean
  autoSync: boolean
  lastSync?: string
  mappedAccounts: Record<string, string>
  taxCodes: Record<string, string>
}

export function ExportManagement() {
  const [selectedTemplate, setSelectedTemplate] = useState<ExportTemplate | null>(null)
  const [isCreatingTemplate, setIsCreatingTemplate] = useState(false)
  const [exportJobs, setExportJobs] = useState<ExportJob[]>([])
  const [templates, setTemplates] = useState<ExportTemplate[]>([])
  const [showPreview, setShowPreview] = useState(false)
  const [selectedRecords, setSelectedRecords] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState("templates")

  // Mock data
  const mockTemplates: ExportTemplate[] = [
    {
      id: "1",
      name: "Daily Invoice Export",
      description: "Export all approved invoices from the past 24 hours",
      format: "csv",
      fields: [
        { id: "1", name: "Invoice Number", source: "invoiceNumber", required: true },
        { id: "2", name: "Vendor Name", source: "vendorName", required: true },
        { id: "3", name: "Amount", source: "totalAmount", required: true },
        { id: "4", name: "Invoice Date", source: "invoiceDate", required: true, format: "date" },
        { id: "5", name: "Due Date", source: "dueDate", required: true, format: "date" }
      ],
      filters: [
        { id: "1", field: "status", operator: "equals", value: "approved", required: true },
        { id: "2", field: "approvedAt", operator: "greater_than", value: "24h", required: true }
      ],
      schedule: {
        enabled: true,
        frequency: "daily",
        time: "02:00",
        recipients: ["finance@company.com", "ap-manager@company.com"],
        autoExport: true
      },
      isActive: true,
      lastExport: "2024-11-06T02:00:00Z",
      exportCount: 245,
      createdBy: "John Smith",
      createdAt: "2024-10-01T10:00:00Z"
    },
    {
      id: "2",
      name: "QuickBooks Integration",
      description: "Sync approved invoices to QuickBooks Online",
      format: "quickbooks",
      fields: [
        { id: "1", name: "Customer", source: "vendorName", required: true },
        { id: "2", name: "Amount", source: "totalAmount", required: true, format: "currency" },
        { id: "3", name: "Due Date", source: "dueDate", required: true, format: "date" },
        { id: "4", name: "Memo", source: "invoiceNumber", required: false },
        { id: "5", name: "Account", source: "accountCode", required: true }
      ],
      filters: [
        { id: "1", field: "status", operator: "equals", value: "approved", required: true },
        { id: "2", field: "quickbooksSynced", operator: "equals", value: false, required: true }
      ],
      schedule: {
        enabled: true,
        frequency: "hourly",
        time: "*:00",
        recipients: [],
        autoExport: true
      },
      isActive: true,
      lastExport: "2024-11-06T11:00:00Z",
      exportCount: 189,
      createdBy: "Sarah Johnson",
      createdAt: "2024-09-15T14:30:00Z"
    }
  ]

  const mockJobs: ExportJob[] = [
    {
      id: "1",
      templateId: "1",
      templateName: "Daily Invoice Export",
      status: "completed",
      progress: 100,
      startTime: "2024-11-06T02:00:00Z",
      endTime: "2024-11-06T02:03:15Z",
      recordCount: 23,
      successCount: 23,
      errorCount: 0,
      fileUrl: "/exports/daily-invoices-2024-11-06.csv",
      triggeredBy: "Scheduled",
      format: "csv",
      size: 156780
    },
    {
      id: "2",
      templateId: "2",
      templateName: "QuickBooks Integration",
      status: "running",
      progress: 65,
      startTime: "2024-11-06T11:00:00Z",
      recordCount: 45,
      successCount: 29,
      errorCount: 0,
      triggeredBy: "Scheduled",
      format: "quickbooks"
    },
    {
      id: "3",
      templateId: "3",
      templateName: "Monthly Report",
      status: "failed",
      progress: 30,
      startTime: "2024-11-05T16:30:00Z",
      endTime: "2024-11-05T16:32:45Z",
      recordCount: 150,
      successCount: 45,
      errorCount: 105,
      errorDetails: "Connection timeout to QuickBooks API",
      triggeredBy: "John Smith",
      format: "xlsx"
    }
  ]

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-50 text-green-700 border-green-200"
      case "running":
        return "bg-blue-50 text-blue-700 border-blue-200"
      case "failed":
        return "bg-red-50 text-red-700 border-red-200"
      case "cancelled":
        return "bg-slate-50 text-slate-700 border-slate-200"
      default:
        return "bg-yellow-50 text-yellow-700 border-yellow-200"
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="w-4 h-4" />
      case "running":
        return <RefreshCw className="w-4 h-4 animate-spin" />
      case "failed":
        return <AlertTriangle className="w-4 h-4" />
      case "cancelled":
        return <Pause className="w-4 h-4" />
      default:
        return <Clock className="w-4 h-4" />
    }
  }

  const getFormatIcon = (format: string) => {
    switch (format) {
      case "csv":
        return <FileSpreadsheet className="w-4 h-4" />
      case "json":
        return <FileJson className="w-4 h-4" />
      case "quickbooks":
        return <Database className="w-4 h-4" />
      default:
        return <FileText className="w-4 h-4" />
    }
  }

  const handleRunExport = (templateId: string) => {
    const newJob: ExportJob = {
      id: Date.now().toString(),
      templateId,
      templateName: templates.find(t => t.id === templateId)?.name || "Unknown",
      status: "pending",
      progress: 0,
      startTime: new Date().toISOString(),
      recordCount: 0,
      successCount: 0,
      errorCount: 0,
      triggeredBy: "Manual",
      format: templates.find(t => t.id === templateId)?.format || "csv"
    }

    setExportJobs(prev => [newJob, ...prev])
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes"
    const k = 1024
    const sizes = ["Bytes", "KB", "MB", "GB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
  }

  const formatDuration = (startTime: string, endTime?: string) => {
    const start = new Date(startTime)
    const end = endTime ? new Date(endTime) : new Date()
    const durationMs = end.getTime() - start.getTime()
    const seconds = Math.floor(durationMs / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`
    } else {
      return `${seconds}s`
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Export Management</h1>
          <p className="text-slate-600">Manage export templates, schedules, and integrations</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline">
            <Settings className="w-4 h-4 mr-2" />
            Integration Settings
          </Button>
          <Button onClick={() => setIsCreatingTemplate(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Create Template
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Templates</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{templates.filter(t => t.isActive).length}</div>
            <p className="text-xs text-muted-foreground">
              {templates.length} total templates
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Running Jobs</CardTitle>
            <RefreshCw className="h-4 w-4 text-blue-600 animate-spin" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {exportJobs.filter(j => j.status === "running").length}
            </div>
            <p className="text-xs text-muted-foreground">
              Currently processing
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">94.2%</div>
            <p className="text-xs text-muted-foreground">
              Last 30 days
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Exports</CardTitle>
            <Download className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">1,847</div>
            <p className="text-xs text-muted-foreground">
              All time
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="templates">Templates</TabsTrigger>
          <TabsTrigger value="jobs">Export Jobs</TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
          <TabsTrigger value="schedule">Schedule</TabsTrigger>
        </TabsList>

        <TabsContent value="templates" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {mockTemplates.map((template) => (
              <Card key={template.id} className="hover:shadow-md transition-shadow">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        {getFormatIcon(template.format)}
                        <CardTitle className="text-lg">{template.name}</CardTitle>
                        <Badge variant={template.isActive ? "default" : "secondary"}>
                          {template.isActive ? "Active" : "Inactive"}
                        </Badge>
                      </div>
                      <CardDescription>{template.description}</CardDescription>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm">
                          <MoreHorizontal className="w-4 h-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => handleRunExport(template.id)}>
                          <Play className="w-4 h-4 mr-2" />
                          Run Now
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setSelectedTemplate(template)}>
                          <Eye className="w-4 h-4 mr-2" />
                          View Details
                        </DropdownMenuItem>
                        <DropdownMenuItem>
                          <Edit className="w-4 h-4 mr-2" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem>
                          <Copy className="w-4 h-4 mr-2" />
                          Duplicate
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem className="text-red-600">
                          <Trash2 className="w-4 h-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-600">Format:</span>
                      <Badge variant="outline">{template.format.toUpperCase()}</Badge>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-600">Fields:</span>
                      <span>{template.fields.length}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-600">Filters:</span>
                      <span>{template.filters.length}</span>
                    </div>
                    {template.schedule && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-600">Schedule:</span>
                        <span className="capitalize">{template.schedule.frequency}</span>
                      </div>
                    )}
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-600">Exports:</span>
                      <span>{template.exportCount}</span>
                    </div>
                    {template.lastExport && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-600">Last run:</span>
                        <span>{new Date(template.lastExport).toLocaleString()}</span>
                      </div>
                    )}
                    <Separator />
                    <div className="flex items-center gap-2">
                      <Button size="sm" onClick={() => handleRunExport(template.id)}>
                        <Play className="w-4 h-4 mr-1" />
                        Run Now
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setShowPreview(true)}>
                        <Eye className="w-4 h-4 mr-1" />
                        Preview
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="jobs" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Recent Export Jobs</CardTitle>
                <Button variant="outline" size="sm">
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Refresh
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {mockJobs.map((job) => (
                  <div key={job.id} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        {getStatusIcon(job.status)}
                        <div>
                          <h4 className="font-semibold">{job.templateName}</h4>
                          <div className="flex items-center gap-2 text-sm text-slate-600">
                            <span>Started by {job.triggeredBy}</span>
                            <span>•</span>
                            <span>{new Date(job.startTime).toLocaleString()}</span>
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <Badge className={getStatusColor(job.status)}>
                          {job.status}
                        </Badge>
                        {job.endTime && (
                          <div className="text-sm text-slate-500 mt-1">
                            {formatDuration(job.startTime, job.endTime)}
                          </div>
                        )}
                      </div>
                    </div>

                    {job.status === "running" && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span>Progress: {job.progress}%</span>
                          <span>{job.successCount} / {job.recordCount} records</span>
                        </div>
                        <Progress value={job.progress} className="h-2" />
                      </div>
                    )}

                    <div className="grid grid-cols-4 gap-4 text-sm mt-3">
                      <div>
                        <span className="text-slate-600">Records:</span>
                        <span className="ml-2 font-medium">{job.recordCount}</span>
                      </div>
                      <div>
                        <span className="text-slate-600">Success:</span>
                        <span className="ml-2 font-medium text-green-600">{job.successCount}</span>
                      </div>
                      <div>
                        <span className="text-slate-600">Errors:</span>
                        <span className="ml-2 font-medium text-red-600">{job.errorCount}</span>
                      </div>
                      {job.size && (
                        <div>
                          <span className="text-slate-600">Size:</span>
                          <span className="ml-2 font-medium">{formatFileSize(job.size)}</span>
                        </div>
                      )}
                    </div>

                    {job.errorDetails && (
                      <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                        <strong>Error:</strong> {job.errorDetails}
                      </div>
                    )}

                    {job.fileUrl && (
                      <div className="flex items-center gap-2 mt-3">
                        <Button size="sm" variant="outline">
                          <Download className="w-4 h-4 mr-1" />
                          Download File
                        </Button>
                        <Button size="sm" variant="outline">
                          <Eye className="w-4 h-4 mr-1" />
                          View Records
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="integrations" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>System Integrations</CardTitle>
              <CardDescription>
                Configure connections to external accounting and ERP systems
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* QuickBooks Integration */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Database className="w-5 h-5 text-green-600" />
                      <CardTitle className="text-lg">QuickBooks Online</CardTitle>
                      <Badge variant="outline" className="text-green-600 border-green-200">
                        Connected
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-slate-600">Company ID:</span>
                        <span className="font-mono">123146523456789</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Realm ID:</span>
                        <span className="font-mono">462081636512345</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Environment:</span>
                        <span>Sandbox</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Last Sync:</span>
                        <span>2 minutes ago</span>
                      </div>
                    </div>
                    <Separator />
                    <div className="space-y-2">
                      <h4 className="font-semibold">Sync Status</h4>
                      <div className="space-y-1 text-sm">
                        <div className="flex items-center justify-between">
                          <span>Invoices:</span>
                          <span className="text-green-600">189 synced</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span>Vendors:</span>
                          <span className="text-green-600">45 synced</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span>Chart of Accounts:</span>
                          <span className="text-blue-600">Loading...</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline">
                        <RefreshCw className="w-4 h-4 mr-1" />
                        Sync Now
                      </Button>
                      <Button size="sm" variant="outline">
                        <Settings className="w-4 h-4 mr-1" />
                        Configure
                      </Button>
                    </div>
                  </CardContent>
                </Card>

                {/* SAP Integration */}
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Database className="w-5 h-5 text-blue-600" />
                      <CardTitle className="text-lg">SAP S/4HANA</CardTitle>
                      <Badge variant="outline" className="text-slate-600 border-slate-200">
                        Not Connected
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-slate-600">
                      Connect to your SAP system for direct invoice posting and real-time synchronization.
                    </p>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-slate-600">Status:</span>
                        <span className="text-slate-500">Configuration Required</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">System:</span>
                        <span className="font-mono text-slate-500">Not configured</span>
                      </div>
                    </div>
                    <Separator />
                    <Button className="w-full">
                      <Plus className="w-4 h-4 mr-2" />
                      Configure SAP Connection
                    </Button>
                  </CardContent>
                </Card>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="schedule" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Export Schedule</CardTitle>
              <CardDescription>
                Manage automated export schedules and notifications
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {mockTemplates
                  .filter(template => template.schedule)
                  .map((template) => (
                    <div key={template.id} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <h4 className="font-semibold">{template.name}</h4>
                          <p className="text-sm text-slate-600">{template.description}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={template.schedule?.enabled ? "default" : "secondary"}>
                            {template.schedule?.enabled ? "Enabled" : "Disabled"}
                          </Badge>
                          <Button size="sm" variant="outline">
                            <Settings className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>

                      <div className="grid grid-cols-3 gap-4 text-sm">
                        <div>
                          <span className="text-slate-600">Frequency:</span>
                          <span className="ml-2 capitalize font-medium">
                            {template.schedule?.frequency}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-600">Time:</span>
                          <span className="ml-2 font-medium">{template.schedule?.time}</span>
                        </div>
                        <div>
                          <span className="text-slate-600">Recipients:</span>
                          <span className="ml-2 font-medium">
                            {template.schedule?.recipients.length} people
                          </span>
                        </div>
                      </div>

                      {template.schedule?.recipients && template.schedule.recipients.length > 0 && (
                        <div className="mt-3">
                          <span className="text-sm text-slate-600">Email notifications sent to:</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {template.schedule.recipients.map((email, idx) => (
                              <Badge key={idx} variant="outline" className="text-xs">
                                {email}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Template Details Dialog */}
      {selectedTemplate && (
        <Dialog open={!!selectedTemplate} onOpenChange={() => setSelectedTemplate(null)}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{selectedTemplate.name}</DialogTitle>
              <DialogDescription>{selectedTemplate.description}</DialogDescription>
            </DialogHeader>

            <div className="space-y-6">
              {/* Template Info */}
              <div className="grid grid-cols-2 gap-4">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">Template Details</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Format:</span>
                      <Badge variant="outline">{selectedTemplate.format.toUpperCase()}</Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Status:</span>
                      <Badge variant={selectedTemplate.isActive ? "default" : "secondary"}>
                        {selectedTemplate.isActive ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Created by:</span>
                      <span>{selectedTemplate.createdBy}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Created:</span>
                      <span>{new Date(selectedTemplate.createdAt).toLocaleDateString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Total Exports:</span>
                      <span>{selectedTemplate.exportCount}</span>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">Schedule Info</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {selectedTemplate.schedule ? (
                      <div className="space-y-2">
                        <div className="flex justify-between">
                          <span className="text-sm text-slate-600">Enabled:</span>
                          <span>{selectedTemplate.schedule.enabled ? "Yes" : "No"}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-slate-600">Frequency:</span>
                          <span className="capitalize">{selectedTemplate.schedule.frequency}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-slate-600">Time:</span>
                          <span>{selectedTemplate.schedule.time}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-slate-600">Auto Export:</span>
                          <span>{selectedTemplate.schedule.autoExport ? "Yes" : "No"}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-slate-600">Last Run:</span>
                          <span>
                            {selectedTemplate.lastExport
                              ? new Date(selectedTemplate.lastExport).toLocaleString()
                              : "Never"}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-slate-600">No schedule configured</p>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Export Fields */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Export Fields ({selectedTemplate.fields.length})</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {selectedTemplate.fields.map((field) => (
                      <div key={field.id} className="flex items-center justify-between p-2 border rounded">
                        <div className="flex items-center gap-3">
                          <span className="font-medium">{field.name}</span>
                          {field.required && (
                            <Badge variant="destructive" className="text-xs">Required</Badge>
                          )}
                          {field.format && (
                            <Badge variant="outline" className="text-xs">
                              {field.format}
                            </Badge>
                          )}
                        </div>
                        <div className="text-sm text-slate-600 font-mono">
                          {field.source}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Filters */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Export Filters ({selectedTemplate.filters.length})</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {selectedTemplate.filters.map((filter) => (
                      <div key={filter.id} className="flex items-center justify-between p-2 border rounded">
                        <div className="flex items-center gap-3">
                          <span className="font-medium">{filter.field}</span>
                          <Badge variant="outline" className="text-xs">
                            {filter.operator}
                          </Badge>
                          {filter.required && (
                            <Badge variant="destructive" className="text-xs">Required</Badge>
                          )}
                        </div>
                        <div className="text-sm text-slate-600">
                          {Array.isArray(filter.value) ? filter.value.join(", ") : filter.value}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Actions */}
              <div className="flex items-center justify-between border-t pt-6">
                <Button variant="outline" onClick={() => setSelectedTemplate(null)}>
                  Close
                </Button>
                <div className="flex gap-3">
                  <Button variant="outline" onClick={() => handleRunExport(selectedTemplate.id)}>
                    <Play className="w-4 h-4 mr-2" />
                    Run Export
                  </Button>
                  <Button>
                    <Edit className="w-4 h-4 mr-2" />
                    Edit Template
                  </Button>
                </div>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}