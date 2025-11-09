"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
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
  Trash2,
  Diff,
  UserCheck,
  UserX,
  Gavel,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  ArrowRightLeft
} from "lucide-react"
import { cn } from "@/lib/utils"
import { DiffViewer } from "./DiffViewer"

// Types
interface ExportTemplate {
  id: string
  name: string
  description: string
  format: "csv" | "json" | "xml" | "xlsx" | "quickbooks" | "sap" | "custom"
  fields: ExportField[]
  filters: ExportFilter[]
  schedule?: ExportSchedule
  approval_workflow_id?: string
  is_active: boolean
  last_export?: string
  export_count: number
  created_by: string
  created_at: string
  requires_approval: boolean
}

interface ExportField {
  id: string
  name: string
  source: string
  transform?: string
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
  auto_export: boolean
}

interface ExportJob {
  id: string
  template_id: string
  template_name: string
  status: "pending" | "running" | "completed" | "failed" | "cancelled" | "requires_approval"
  progress: number
  start_time: string
  end_time?: string
  record_count: number
  success_count: number
  error_count: number
  file_url?: string
  error_details?: string
  triggered_by: string
  format: string
  size?: number
  approval_request_id?: string
  approver?: string
  approval_status?: "pending" | "approved" | "rejected"
}

interface StagedExport {
  id: string
  invoice_id: string
  invoice_number: string
  vendor_name: string
  format: string
  status: "pending_approval" | "approved" | "rejected" | "exported"
  export_data: any
  approval_request_id?: string
  approver?: string
  approval_comments?: string
  created_at: string
  diff_data?: any
}

interface ERPConnection {
  id: string
  system_type: string
  environment: string
  status: "connected" | "disconnected" | "error"
  last_sync?: string
  configuration: any
  test_result?: any
}

interface ApprovalWorkflow {
  id: string
  name: string
  description: string
  workflow_type: string
  steps: number
  is_active: boolean
}

export function ExportDashboard() {
  const [selectedTemplate, setSelectedTemplate] = useState<ExportTemplate | null>(null)
  const [selectedJob, setSelectedJob] = useState<ExportJob | null>(null)
  const [selectedStagedExport, setSelectedStagedExport] = useState<StagedExport | null>(null)
  const [isCreatingTemplate, setIsCreatingTemplate] = useState(false)
  const [exportJobs, setExportJobs] = useState<ExportJob[]>([])
  const [stagedExports, setStagedExports] = useState<StagedExport[]>([])
  const [templates, setTemplates] = useState<ExportTemplate[]>([])
  const [erpConnections, setERPConnections] = useState<ERPConnection[]>([])
  const [approvalWorkflows, setApprovalWorkflows] = useState<ApprovalWorkflow[]>([])
  const [activeTab, setActiveTab] = useState("overview")
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [showDiffDialog, setShowDiffDialog] = useState(false)

  // Mock data - replace with API calls
  useEffect(() => {
    // Load mock data
    setTemplates([
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
          auto_export: false
        },
        approval_workflow_id: "workflow_1",
        is_active: true,
        requires_approval: true,
        last_export: "2024-11-06T02:00:00Z",
        export_count: 245,
        created_by: "John Smith",
        created_at: "2024-10-01T10:00:00Z"
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
          auto_export: true
        },
        approval_workflow_id: "workflow_2",
        is_active: true,
        requires_approval: false,
        last_export: "2024-11-06T11:00:00Z",
        export_count: 189,
        created_by: "Sarah Johnson",
        created_at: "2024-09-15T14:30:00Z"
      }
    ])

    setExportJobs([
      {
        id: "1",
        template_id: "1",
        template_name: "Daily Invoice Export",
        status: "completed",
        progress: 100,
        start_time: "2024-11-06T02:00:00Z",
        end_time: "2024-11-06T02:03:15Z",
        record_count: 23,
        success_count: 23,
        error_count: 0,
        file_url: "/exports/daily-invoices-2024-11-06.csv",
        triggered_by: "Scheduled",
        format: "csv",
        size: 156780
      },
      {
        id: "2",
        template_id: "2",
        template_name: "QuickBooks Integration",
        status: "requires_approval",
        progress: 65,
        start_time: "2024-11-06T11:00:00Z",
        record_count: 45,
        success_count: 29,
        error_count: 0,
        triggered_by: "Manual",
        format: "quickbooks",
        approval_request_id: "approval_1",
        approver: "John Smith",
        approval_status: "pending"
      },
      {
        id: "3",
        template_id: "3",
        template_name: "Monthly Report",
        status: "failed",
        progress: 30,
        start_time: "2024-11-05T16:30:00Z",
        end_time: "2024-11-05T16:32:45Z",
        record_count: 150,
        success_count: 45,
        error_count: 105,
        error_details: "Connection timeout to QuickBooks API",
        triggered_by: "John Smith",
        format: "xlsx"
      }
    ])

    setStagedExports([
      {
        id: "1",
        invoice_id: "inv_1",
        invoice_number: "INV-2024-001",
        vendor_name: "ABC Supplies",
        format: "quickbooks",
        status: "pending_approval",
        export_data: { /* mock data */ },
        approval_request_id: "approval_2",
        created_at: "2024-11-06T10:30:00Z"
      },
      {
        id: "2",
        invoice_id: "inv_2",
        invoice_number: "INV-2024-002",
        vendor_name: "XYZ Corporation",
        format: "csv",
        status: "approved",
        export_data: { /* mock data */ },
        approval_request_id: "approval_3",
        approver: "Sarah Johnson",
        approval_comments: "Approved with minor corrections to line items",
        created_at: "2024-11-05T15:45:00Z"
      }
    ])

    setERPConnections([
      {
        id: "1",
        system_type: "QuickBooks",
        environment: "Sandbox",
        status: "connected",
        last_sync: "2024-11-06T11:00:00Z",
        configuration: { realm_id: "462081636512345" },
        test_result: { success: true, message: "Connection successful" }
      },
      {
        id: "2",
        system_type: "SAP",
        environment: "Development",
        status: "disconnected",
        configuration: { base_url: "https://sap-dev.company.com" },
        test_result: { success: false, message: "Authentication failed" }
      }
    ])

    setApprovalWorkflows([
      {
        id: "workflow_1",
        name: "Standard Export Approval",
        description: "Two-step approval for standard exports",
        workflow_type: "invoice_export",
        steps: 2,
        is_active: true
      },
      {
        id: "workflow_2",
        name: "High-Value Export Approval",
        description: "Three-step approval for high-value exports",
        workflow_type: "invoice_export",
        steps: 3,
        is_active: true
      }
    ])
  }, [])

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
      case "requires_approval":
        return "bg-yellow-50 text-yellow-700 border-yellow-200"
      case "pending_approval":
        return "bg-orange-50 text-orange-700 border-orange-200"
      case "approved":
        return "bg-green-50 text-green-700 border-green-200"
      case "rejected":
        return "bg-red-50 text-red-700 border-red-200"
      default:
        return "bg-gray-50 text-gray-700 border-gray-200"
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
      case "requires_approval":
        return <Gavel className="w-4 h-4" />
      case "pending_approval":
        return <Clock className="w-4 h-4" />
      case "approved":
        return <CheckCircle2 className="w-4 h-4" />
      case "rejected":
        return <XCircle className="w-4 h-4" />
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
      case "sap":
        return <Database className="w-4 h-4" />
      default:
        return <FileText className="w-4 h-4" />
    }
  }

  const handleApproveExport = (jobId: string) => {
    // Handle approval logic
    console.log("Approving export:", jobId)
  }

  const handleRejectExport = (jobId: string) => {
    // Handle rejection logic
    console.log("Rejecting export:", jobId)
  }

  const handleRunExport = (templateId: string) => {
    // Handle export execution
    console.log("Running export:", templateId)
  }

  const handleViewDiff = (exportId: string) => {
    const stagedExport = stagedExports.find(se => se.id === exportId)
    if (stagedExport) {
      setSelectedStagedExport(stagedExport)
      setShowDiffDialog(true)
    }
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
          <p className="text-slate-600">Manage export templates, approval workflows, and ERP integrations</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline">
            <Settings className="w-4 h-4 mr-2" />
            ERP Settings
          </Button>
          <Button onClick={() => setIsCreatingTemplate(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Create Template
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Templates</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{templates.filter(t => t.is_active).length}</div>
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
            <CardTitle className="text-sm font-medium">Pending Approvals</CardTitle>
            <Gavel className="h-4 w-4 text-orange-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {exportJobs.filter(j => j.status === "requires_approval").length}
            </div>
            <p className="text-xs text-muted-foreground">
              Need approval
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
            <CardTitle className="text-sm font-medium">ERP Connections</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {erpConnections.filter(c => c.status === "connected").length}/{erpConnections.length}
            </div>
            <p className="text-xs text-muted-foreground">
              Connected systems
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
          <TabsTrigger value="jobs">Export Jobs</TabsTrigger>
          <TabsTrigger value="approvals">Approvals</TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
          <TabsTrigger value="workflows">Workflows</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Export Jobs */}
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
                <div className="space-y-3">
                  {exportJobs.slice(0, 5).map((job) => (
                    <div key={job.id} className="flex items-center justify-between p-3 border rounded-lg">
                      <div className="flex items-center gap-3">
                        {getStatusIcon(job.status)}
                        <div>
                          <h4 className="font-medium">{job.template_name}</h4>
                          <div className="text-sm text-gray-600">
                            {new Date(job.start_time).toLocaleString()}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge className={getStatusColor(job.status)}>
                          {job.status}
                        </Badge>
                        {job.approval_status && (
                          <Badge variant="outline">
                            {job.approval_status}
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Staged Exports */}
            <Card>
              <CardHeader>
                <CardTitle>Staged Exports</CardTitle>
                <CardDescription>Exports awaiting approval</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {stagedExports.slice(0, 5).map((export) => (
                    <div key={export.id} className="flex items-center justify-between p-3 border rounded-lg">
                      <div className="flex items-center gap-3">
                        {getFormatIcon(export.format)}
                        <div>
                          <h4 className="font-medium">{export.invoice_number}</h4>
                          <div className="text-sm text-gray-600">
                            {export.vendor_name} • {export.format}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge className={getStatusColor(export.status)}>
                          {export.status}
                        </Badge>
                        {export.diff_data && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleViewDiff(export.id)}
                          >
                            <Diff className="w-4 h-4 mr-1" />
                            Diff
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* ERP Connection Status */}
          <Card>
            <CardHeader>
              <CardTitle>ERP Integration Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {erpConnections.map((connection) => (
                  <Card key={connection.id}>
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          {getFormatIcon(connection.system_type.toLowerCase())}
                          <h4 className="font-semibold">{connection.system_type}</h4>
                          <Badge
                            variant={connection.status === "connected" ? "default" : "secondary"}
                          >
                            {connection.status}
                          </Badge>
                        </div>
                        <Button variant="outline" size="sm">
                          <RefreshCw className="w-4 h-4 mr-1" />
                          Test
                        </Button>
                      </div>
                      <div className="text-sm text-gray-600">
                        <div>Environment: {connection.environment}</div>
                        {connection.last_sync && (
                          <div>Last sync: {new Date(connection.last_sync).toLocaleString()}</div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="templates" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {templates.map((template) => (
              <Card key={template.id} className="hover:shadow-md transition-shadow">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        {getFormatIcon(template.format)}
                        <CardTitle className="text-lg">{template.name}</CardTitle>
                        <Badge variant={template.is_active ? "default" : "secondary"}>
                          {template.is_active ? "Active" : "Inactive"}
                        </Badge>
                        {template.requires_approval && (
                          <Badge variant="outline">
                            <Gavel className="w-3 h-3 mr-1" />
                            Approval
                          </Badge>
                        )}
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
                      <span>{template.export_count}</span>
                    </div>
                    {template.last_export && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-600">Last run:</span>
                        <span>{new Date(template.last_export).toLocaleString()}</span>
                      </div>
                    )}
                    <Separator />
                    <div className="flex items-center gap-2">
                      <Button size="sm" onClick={() => handleRunExport(template.id)}>
                        <Play className="w-4 h-4 mr-1" />
                        Run Now
                      </Button>
                      <Button size="sm" variant="outline">
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
                <CardTitle>Export Jobs</CardTitle>
                <div className="flex items-center gap-2">
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="running">Running</SelectItem>
                      <SelectItem value="completed">Completed</SelectItem>
                      <SelectItem value="failed">Failed</SelectItem>
                      <SelectItem value="requires_approval">Requires Approval</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button variant="outline" size="sm">
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Refresh
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Template</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Progress</TableHead>
                    <TableHead>Records</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {exportJobs
                    .filter(job => statusFilter === "all" || job.status === statusFilter)
                    .map((job) => (
                      <TableRow key={job.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getFormatIcon(job.format)}
                            <div>
                              <div className="font-medium">{job.template_name}</div>
                              <div className="text-sm text-gray-600">By {job.triggered_by}</div>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getStatusIcon(job.status)}
                            <Badge className={getStatusColor(job.status)}>
                              {job.status}
                            </Badge>
                            {job.approval_status && (
                              <Badge variant="outline">
                                {job.approval_status}
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {job.status === "running" && (
                            <div className="space-y-1">
                              <div className="flex items-center justify-between text-sm">
                                <span>{job.progress}%</span>
                                <span>{job.success_count}/{job.record_count}</span>
                              </div>
                              <Progress value={job.progress} className="h-2" />
                            </div>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            <div>Total: {job.record_count}</div>
                            <div className="text-green-600">Success: {job.success_count}</div>
                            {job.error_count > 0 && (
                              <div className="text-red-600">Errors: {job.error_count}</div>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            {new Date(job.start_time).toLocaleString()}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            {formatDuration(job.start_time, job.end_time)}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {job.file_url && (
                              <Button size="sm" variant="outline">
                                <Download className="w-4 h-4 mr-1" />
                                Download
                              </Button>
                            )}
                            {job.status === "requires_approval" && (
                              <div className="flex items-center gap-1">
                                <Button
                                  size="sm"
                                  onClick={() => handleApproveExport(job.id)}
                                >
                                  <UserCheck className="w-4 h-4 mr-1" />
                                  Approve
                                </Button>
                                <Button
                                  size="sm"
                                  variant="destructive"
                                  onClick={() => handleRejectExport(job.id)}
                                >
                                  <UserX className="w-4 h-4 mr-1" />
                                  Reject
                                </Button>
                              </div>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="approvals" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Pending Approvals</CardTitle>
              <CardDescription>Exports requiring your approval</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {stagedExports
                  .filter(se => se.status === "pending_approval")
                  .map((export) => (
                    <Card key={export.id}>
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            {getFormatIcon(export.format)}
                            <div>
                              <h4 className="font-semibold">{export.invoice_number}</h4>
                              <div className="text-sm text-gray-600">
                                {export.vendor_name} • {export.format} format
                              </div>
                              <div className="text-xs text-gray-500">
                                Requested {new Date(export.created_at).toLocaleString()}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleViewDiff(export.id)}
                            >
                              <Diff className="w-4 h-4 mr-1" />
                              View Changes
                            </Button>
                            <Button size="sm">
                              <UserCheck className="w-4 h-4 mr-1" />
                              Approve
                            </Button>
                            <Button size="sm" variant="destructive">
                              <UserX className="w-4 h-4 mr-1" />
                              Reject
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="integrations" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {erpConnections.map((connection) => (
              <Card key={connection.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getFormatIcon(connection.system_type.toLowerCase())}
                      <CardTitle className="text-lg">{connection.system_type}</CardTitle>
                      <Badge
                        variant={connection.status === "connected" ? "default" : "secondary"}
                      >
                        {connection.status}
                      </Badge>
                    </div>
                    <Button variant="outline" size="sm">
                      <Settings className="w-4 h-4" />
                    </Button>
                  </div>
                  <CardDescription>
                    {connection.environment} environment
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-slate-600">Status:</span>
                        <span className={connection.status === "connected" ? "text-green-600" : "text-red-600"}>
                          {connection.status}
                        </span>
                      </div>
                      {connection.last_sync && (
                        <div className="flex justify-between">
                          <span className="text-slate-600">Last Sync:</span>
                          <span>{new Date(connection.last_sync).toLocaleString()}</span>
                        </div>
                      )}
                    </div>
                    <Separator />
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline">
                        <RefreshCw className="w-4 h-4 mr-1" />
                        Test Connection
                      </Button>
                      <Button size="sm" variant="outline">
                        <RefreshCw className="w-4 h-4 mr-1" />
                        Sync Now
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="workflows" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Approval Workflows</CardTitle>
                <Button>
                  <Plus className="w-4 h-4 mr-2" />
                  Create Workflow
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {approvalWorkflows.map((workflow) => (
                  <Card key={workflow.id}>
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-semibold">{workflow.name}</h4>
                          <p className="text-sm text-gray-600">{workflow.description}</p>
                          <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                            <span>Type: {workflow.workflow_type}</span>
                            <span>Steps: {workflow.steps}</span>
                            <Badge variant={workflow.is_active ? "default" : "secondary"}>
                              {workflow.is_active ? "Active" : "Inactive"}
                            </Badge>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button variant="outline" size="sm">
                            <Eye className="w-4 h-4 mr-1" />
                            View
                          </Button>
                          <Button variant="outline" size="sm">
                            <Edit className="w-4 h-4 mr-1" />
                            Edit
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Diff Dialog */}
      <Dialog open={showDiffDialog} onOpenChange={setShowDiffDialog}>
        <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Export Changes Review</DialogTitle>
            <DialogDescription>
              Review the changes before approving the export
            </DialogDescription>
          </DialogHeader>
          {selectedStagedExport && (
            <div className="mt-4">
              {/* Mock diff data - replace with actual diff data */}
              <DiffViewer
                diffData={{
                  comparison_id: selectedStagedExport.id,
                  comparison_name: `Export Changes - ${selectedStagedExport.invoice_number}`,
                  timestamp: selectedStagedExport.created_at,
                  original_data: {},
                  modified_data: selectedStagedExport.export_data,
                  changes: [],
                  summary: {
                    total_changes: 0,
                    added_fields: 0,
                    removed_fields: 0,
                    modified_fields: 0,
                    critical_changes: 0,
                    high_changes: 0,
                    medium_changes: 0,
                    low_changes: 0,
                    overall_significance: "low"
                  },
                  context: {}
                }}
                onApprove={() => {
                  handleApproveExport(selectedStagedExport.id)
                  setShowDiffDialog(false)
                }}
                onReject={() => {
                  handleRejectExport(selectedStagedExport.id)
                  setShowDiffDialog(false)
                }}
              />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}