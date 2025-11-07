"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  User,
  Calendar,
  DollarSign,
  Building,
  FileText,
  MessageSquare,
  Send,
  Eye,
  Edit,
  Trash2,
  MoreHorizontal,
  Search,
  Filter,
  Download,
  Upload,
  RefreshCw,
  ChevronRight,
  ChevronLeft,
  CheckSquare,
  Square,
  ArrowRight,
  Users,
  Settings,
  Bell,
  Mail,
  Phone,
  Star,
  Shield,
  Key,
  Lock,
  Unlock,
  History,
  TrendingUp,
  BarChart3,
  PieChart,
  Activity,
  UserCheck,
  UserX,
  AlertCircle,
  Info,
  Zap,
  Target,
  Award,
  Flag,
  FileCheck,
  FileX,
  Hourglass,
  Play,
  Pause,
  SkipForward,
  RotateCcw,
  Copy,
  Share2,
  Printer,
  Archive,
  ExternalLink
} from "lucide-react"
import { cn } from "@/lib/utils"

// Types
interface User {
  id: string
  name: string
  email: string
  role: UserRole
  avatar?: string
  department: string
  permissions: Permission[]
  isActive: boolean
  lastActive: string
}

interface UserRole {
  id: string
  name: string
  level: number // 1=Basic, 2=Advanced, 3=Manager, 4=Admin, 5=Super Admin
  permissions: Permission[]
  limits: {
    maxApprovalAmount: number
    canDelegate: boolean
    canOverride: boolean
    requiresApproval: boolean
  }
}

interface Permission {
  id: string
  name: string
  resource: string
  action: string
  conditions?: string[]
}

interface ApprovalRequest {
  id: string
  invoiceId: string
  invoiceNumber: string
  vendorName: string
  amount: number
  currency: string
  requestType: "initial_approval" | "exception_override" | "amount_exceeds_limit" | "policy_violation"
  requesterId: string
  requesterName: string
  currentApproverId: string
  currentApproverName: string
  status: "pending" | "approved" | "rejected" | "cancelled" | "delegated"
  priority: "low" | "medium" | "high" | "urgent"
  submittedAt: string
  dueBy: string
  approvals: ApprovalStep[]
  comments: Comment[]
  attachments: Attachment[]
  metadata: Record<string, any>
}

interface ApprovalStep {
  id: string
  approverId: string
  approverName: string
  approverRole: string
  status: "pending" | "approved" | "rejected" | "delegated"
  actionAt?: string
  comments?: string
  delegatedTo?: string
  conditions: string[]
}

interface Comment {
  id: string
  authorId: string
  authorName: string
  message: string
  timestamp: string
  type: "comment" | "approval" | "rejection" | "delegation"
}

interface Attachment {
  id: string
  name: string
  type: string
  size: number
  uploadedAt: string
  uploadedBy: string
}

interface DelegationRule {
  id: string
  delegatorId: string
  delegateId: string
  startDate: string
  endDate: string
  scope: string[] // approval types, amounts, etc.
  isActive: boolean
  autoApprove: boolean
}

// Mock data
const mockUsers: User[] = [
  {
    id: "1",
    name: "John Smith",
    email: "john.smith@company.com",
    role: {
      id: "manager",
      name: "Manager",
      level: 3,
      permissions: [
        { id: "1", name: "Approve Invoices", resource: "invoice", action: "approve" },
        { id: "2", name: "Review Exceptions", resource: "exception", action: "review" },
        { id: "3", name: "Delegate Approvals", resource: "approval", action: "delegate" }
      ],
      limits: {
        maxApprovalAmount: 10000,
        canDelegate: true,
        canOverride: true,
        requiresApproval: false
      }
    },
    department: "Finance",
    permissions: [],
    isActive: true,
    lastActive: "2024-11-06T09:30:00Z"
  },
  {
    id: "2",
    name: "Sarah Johnson",
    email: "sarah.johnson@company.com",
    role: {
      id: "admin",
      name: "Administrator",
      level: 4,
      permissions: [
        { id: "1", name: "Full Approval Access", resource: "invoice", action: "approve" },
        { id: "2", name: "User Management", resource: "user", action: "manage" },
        { id: "3", name: "System Configuration", resource: "system", action: "configure" }
      ],
      limits: {
        maxApprovalAmount: 50000,
        canDelegate: true,
        canOverride: true,
        requiresApproval: false
      }
    },
    department: "Finance",
    permissions: [],
    isActive: true,
    lastActive: "2024-11-06T10:15:00Z"
  }
]

const mockApprovalRequests: ApprovalRequest[] = [
  {
    id: "1",
    invoiceId: "INV-2024-5647",
    invoiceNumber: "INV-2024-5647",
    vendorName: "Acme Corp Manufacturing",
    amount: 15000,
    currency: "USD",
    requestType: "amount_exceeds_limit",
    requesterId: "3",
    requesterName: "Mike Davis",
    currentApproverId: "1",
    currentApproverName: "John Smith",
    status: "pending",
    priority: "high",
    submittedAt: "2024-11-05T14:30:00Z",
    dueBy: "2024-11-08T17:00:00Z",
    approvals: [
      {
        id: "1",
        approverId: "1",
        approverName: "John Smith",
        approverRole: "Manager",
        status: "pending",
        conditions: ["Amount exceeds $10,000 limit"]
      },
      {
        id: "2",
        approverId: "2",
        approverName: "Sarah Johnson",
        approverRole: "Administrator",
        status: "pending",
        conditions: ["Secondary approval required for amounts > $15,000"]
      }
    ],
    comments: [
      {
        id: "1",
        authorId: "3",
        authorName: "Mike Davis",
        message: "This invoice exceeds my approval limit. Please review and approve if appropriate.",
        timestamp: "2024-11-05T14:30:00Z",
        type: "comment"
      }
    ],
    attachments: [],
    metadata: {
      originalAmount: 15000,
      requestReason: "Monthly manufacturing supplies - Q4 bulk order",
      department: "Procurement"
    }
  },
  {
    id: "2",
    invoiceId: "INV-2024-5648",
    invoiceNumber: "INV-2024-5648",
    vendorName: "Global Supplies Inc",
    amount: 7500,
    currency: "USD",
    requestType: "initial_approval",
    requesterId: "3",
    requesterName: "Mike Davis",
    currentApproverId: "1",
    currentApproverName: "John Smith",
    status: "approved",
    priority: "medium",
    submittedAt: "2024-11-04T09:15:00Z",
    dueBy: "2024-11-07T17:00:00Z",
    approvals: [
      {
        id: "1",
        approverId: "1",
        approverName: "John Smith",
        approverRole: "Manager",
        status: "approved",
        actionAt: "2024-11-05T11:20:00Z",
        comments: "Approved for standard office supplies.",
        conditions: ["Standard approval workflow"]
      }
    ],
    comments: [
      {
        id: "1",
        authorId: "1",
        authorName: "John Smith",
        message: "Approved for standard office supplies.",
        timestamp: "2024-11-05T11:20:00Z",
        type: "approval"
      }
    ],
    attachments: [],
    metadata: {
      department: "Administration",
      budgetCode: "ADM-2024-001"
    }
  }
]

export function ApprovalWorkflow() {
  const [currentUser, setCurrentUser] = useState<User>(mockUsers[0])
  const [approvalRequests, setApprovalRequests] = useState<ApprovalRequest[]>(mockApprovalRequests)
  const [selectedRequest, setSelectedRequest] = useState<ApprovalRequest | null>(null)
  const [showDetails, setShowDetails] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")
  const [filterStatus, setFilterStatus] = useState("all")
  const [filterPriority, setFilterPriority] = useState("all")
  const [bulkAction, setBulkAction] = useState("")
  const [selectedRequests, setSelectedRequests] = useState<string[]>([])
  const [newComment, setNewComment] = useState("")
  const [showDelegationDialog, setShowDelegationDialog] = useState(false)

  const getStatusColor = (status: string) => {
    switch (status) {
      case "approved":
        return "bg-green-50 text-green-700 border-green-200"
      case "rejected":
        return "bg-red-50 text-red-700 border-red-200"
      case "pending":
        return "bg-yellow-50 text-yellow-700 border-yellow-200"
      case "delegated":
        return "bg-blue-50 text-blue-700 border-blue-200"
      default:
        return "bg-slate-50 text-slate-700 border-slate-200"
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "urgent":
        return "bg-red-100 text-red-800"
      case "high":
        return "bg-orange-100 text-orange-800"
      case "medium":
        return "bg-yellow-100 text-yellow-800"
      default:
        return "bg-blue-100 text-blue-800"
    }
  }

  const getRequestTypeColor = (type: string) => {
    switch (type) {
      case "amount_exceeds_limit":
        return "bg-purple-50 text-purple-700 border-purple-200"
      case "exception_override":
        return "bg-orange-50 text-orange-700 border-orange-200"
      case "policy_violation":
        return "bg-red-50 text-red-700 border-red-200"
      default:
        return "bg-blue-50 text-blue-700 border-blue-200"
    }
  }

  const handleApprove = (requestId: string, comments?: string) => {
    setApprovalRequests(prev => prev.map(req => {
      if (req.id === requestId) {
        const updatedApprovals = req.approvals.map(step =>
          step.approverId === currentUser.id && step.status === "pending"
            ? { ...step, status: "approved" as const, actionAt: new Date().toISOString(), comments }
            : step
        )

        const allApproved = updatedApprovals.every(step => step.status === "approved")

        return {
          ...req,
          approvals: updatedApprovals,
          status: allApproved ? "approved" : "pending" as const,
          comments: comments ? [...req.comments, {
            id: Date.now().toString(),
            authorId: currentUser.id,
            authorName: currentUser.name,
            message: comments,
            timestamp: new Date().toISOString(),
            type: "approval"
          }] : req.comments
        }
      }
      return req
    }))
  }

  const handleReject = (requestId: string, comments?: string) => {
    setApprovalRequests(prev => prev.map(req => {
      if (req.id === requestId) {
        const updatedApprovals = req.approvals.map(step =>
          step.approverId === currentUser.id && step.status === "pending"
            ? { ...step, status: "rejected" as const, actionAt: new Date().toISOString(), comments }
            : step
        )

        return {
          ...req,
          approvals: updatedApprovals,
          status: "rejected",
          comments: comments ? [...req.comments, {
            id: Date.now().toString(),
            authorId: currentUser.id,
            authorName: currentUser.name,
            message: comments,
            timestamp: new Date().toISOString(),
            type: "rejection"
          }] : req.comments
        }
      }
      return req
    }))
  }

  const handleDelegate = (requestId: string, delegateTo: string, comments?: string) => {
    setApprovalRequests(prev => prev.map(req => {
      if (req.id === requestId) {
        const updatedApprovals = req.approvals.map(step =>
          step.approverId === currentUser.id && step.status === "pending"
            ? { ...step, status: "delegated" as const, delegatedTo: delegateTo, comments }
            : step
        )

        return {
          ...req,
          approvals: updatedApprovals,
          status: "delegated",
          comments: comments ? [...req.comments, {
            id: Date.now().toString(),
            authorId: currentUser.id,
            authorName: currentUser.name,
            message: `Delegated to ${delegateTo}. ${comments}`,
            timestamp: new Date().toISOString(),
            type: "delegation"
          }] : req.comments
        }
      }
      return req
    }))
  }

  const addComment = (requestId: string) => {
    if (!newComment.trim()) return

    setApprovalRequests(prev => prev.map(req => {
      if (req.id === requestId) {
        return {
          ...req,
          comments: [...req.comments, {
            id: Date.now().toString(),
            authorId: currentUser.id,
            authorName: currentUser.name,
            message: newComment,
            timestamp: new Date().toISOString(),
            type: "comment"
          }]
        }
      }
      return req
    }))

    setNewComment("")
  }

  const filteredRequests = approvalRequests.filter(req => {
    const matchesSearch = req.invoiceNumber.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         req.vendorName.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = filterStatus === "all" || req.status === filterStatus
    const matchesPriority = filterPriority === "all" || req.priority === filterPriority

    return matchesSearch && matchesStatus && matchesPriority
  })

  const myRequests = filteredRequests.filter(req =>
    req.approvals.some(step => step.approverId === currentUser.id && step.status === "pending")
  )

  const stats = {
    pending: myRequests.length,
    approved: approvalRequests.filter(req => req.status === "approved").length,
    rejected: approvalRequests.filter(req => req.status === "rejected").length,
    delegated: approvalRequests.filter(req => req.status === "delegated").length,
    avgApprovalTime: 2.3, // days
    approvalRate: 87.5 // percentage
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Approval Workflow</h1>
          <p className="text-slate-600">Manage invoice approvals with role-based permissions</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-2 bg-slate-100 rounded-lg">
            <Shield className="w-4 h-4 text-slate-600" />
            <span className="text-sm font-medium">{currentUser.role.name}</span>
          </div>
          <Button variant="outline" onClick={() => setShowDelegationDialog(true)}>
            <Users className="w-4 h-4 mr-2" />
            Manage Delegation
          </Button>
          <Button variant="outline">
            <Settings className="w-4 h-4 mr-2" />
            Workflow Settings
          </Button>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending</CardTitle>
            <Clock className="h-4 w-4 text-yellow-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{stats.pending}</div>
            <p className="text-xs text-muted-foreground">
              Awaiting my action
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Approved</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{stats.approved}</div>
            <p className="text-xs text-muted-foreground">
              This month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Rejected</CardTitle>
            <XCircle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{stats.rejected}</div>
            <p className="text-xs text-muted-foreground">
              This month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Delegated</CardTitle>
            <Users className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{stats.delegated}</div>
            <p className="text-xs text-muted-foreground">
              Active delegations
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Approval Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-emerald-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">{stats.approvalRate}%</div>
            <p className="text-xs text-muted-foreground">
              Avg. {stats.avgApprovalTime} days
            </p>
          </CardContent>
        </Card>
      </div>

      {/* My Pending Approvals */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Hourglass className="w-5 h-5" />
                My Pending Approvals
              </CardTitle>
              <CardDescription>
                {myRequests.length} requests requiring your attention
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Search requests..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 w-64"
                />
              </div>
              <Select value={filterPriority} onValueChange={setFilterPriority}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Priority</SelectItem>
                  <SelectItem value="urgent">Urgent</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {myRequests.length === 0 ? (
            <div className="text-center py-8">
              <CheckCircle2 className="w-12 h-12 mx-auto mb-4 text-green-500" />
              <h3 className="text-lg font-semibold text-slate-900">All caught up!</h3>
              <p className="text-slate-600">No pending approvals at this time.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {myRequests.map((request) => (
                <div
                  key={request.id}
                  className="border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => setSelectedRequest(request)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <Badge className={getRequestTypeColor(request.requestType)}>
                          {request.requestType.replace("_", " ").toUpperCase()}
                        </Badge>
                        <Badge className={getPriorityColor(request.priority)}>
                          {request.priority}
                        </Badge>
                        <Badge className={getStatusColor(request.status)}>
                          {request.status}
                        </Badge>
                      </div>

                      <h4 className="font-semibold text-slate-900 mb-1">
                        {request.invoiceNumber} - {request.vendorName}
                      </h4>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-slate-600 mb-3">
                        <div>
                          <span className="block font-medium">Amount</span>
                          <span className="font-semibold text-slate-900">
                            ${request.amount.toLocaleString()} {request.currency}
                          </span>
                        </div>
                        <div>
                          <span className="block font-medium">Requested by</span>
                          <span>{request.requesterName}</span>
                        </div>
                        <div>
                          <span className="block font-medium">Submitted</span>
                          <span>{new Date(request.submittedAt).toLocaleDateString()}</span>
                        </div>
                        <div>
                          <span className="block font-medium">Due by</span>
                          <span className={cn(
                            "font-medium",
                            new Date(request.dueBy) < new Date() && "text-red-600"
                          )}>
                            {new Date(request.dueBy).toLocaleDateString()}
                          </span>
                        </div>
                      </div>

                      {/* Approval Progress */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-medium">Approval Progress</span>
                          <span>
                            {request.approvals.filter(a => a.status === "approved").length} / {request.approvals.length}
                          </span>
                        </div>
                        <Progress
                          value={(request.approvals.filter(a => a.status === "approved").length / request.approvals.length) * 100}
                          className="h-2"
                        />
                        <div className="flex items-center gap-2">
                          {request.approvals.map((step, idx) => (
                            <div
                              key={step.id}
                              className={cn(
                                "flex items-center gap-2 px-2 py-1 rounded text-xs",
                                step.status === "approved" && "bg-green-100 text-green-800",
                                step.status === "pending" && "bg-yellow-100 text-yellow-800",
                                step.status === "rejected" && "bg-red-100 text-red-800",
                                step.status === "delegated" && "bg-blue-100 text-blue-800"
                              )}
                            >
                              {step.status === "approved" && <CheckCircle2 className="w-3 h-3" />}
                              {step.status === "pending" && <Clock className="w-3 h-3" />}
                              {step.status === "rejected" && <XCircle className="w-3 h-3" />}
                              {step.status === "delegated" && <Users className="w-3 h-3" />}
                              {step.approverName}
                              {step.delegatedTo && (
                                <span>→ {step.delegatedTo}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>

                      {request.comments.length > 0 && (
                        <div className="mt-3 p-3 bg-slate-50 rounded">
                          <div className="flex items-center gap-2 mb-1">
                            <MessageSquare className="w-4 h-4 text-slate-600" />
                            <span className="text-sm font-medium">Latest Comment</span>
                          </div>
                          <p className="text-sm text-slate-700">
                            {request.comments[request.comments.length - 1].message}
                          </p>
                          <p className="text-xs text-slate-500 mt-1">
                            {request.comments[request.comments.length - 1].authorName} •
                            {new Date(request.comments[request.comments.length - 1].timestamp).toLocaleString()}
                          </p>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 ml-4">
                      <Button size="sm" variant="outline">
                        <Eye className="w-4 h-4" />
                      </Button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button size="sm" variant="outline">
                            <MoreHorizontal className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleApprove(request.id, "Approved via quick action")}>
                            <CheckCircle2 className="w-4 h-4 mr-2 text-green-600" />
                            Approve
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleReject(request.id, "Rejected via quick action")}>
                            <XCircle className="w-4 h-4 mr-2 text-red-600" />
                            Reject
                          </DropdownMenuItem>
                          <DropdownMenuItem>
                            <Users className="w-4 h-4 mr-2 text-blue-600" />
                            Delegate
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem>
                            <MessageSquare className="w-4 h-4 mr-2" />
                            Add Comment
                          </DropdownMenuItem>
                          <DropdownMenuItem>
                            <Download className="w-4 h-4 mr-2" />
                            Download
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Approval History */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="w-5 h-5" />
            Recent Approval Activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-64">
            <div className="space-y-3">
              {approvalRequests
                .filter(req => req.status !== "pending")
                .slice(0, 10)
                .map((request) => (
                  <div key={request.id} className="flex items-center justify-between p-3 border rounded">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-8 h-8 rounded-full flex items-center justify-center",
                        request.status === "approved" && "bg-green-100",
                        request.status === "rejected" && "bg-red-100",
                        request.status === "delegated" && "bg-blue-100"
                      )}>
                        {request.status === "approved" && <CheckCircle2 className="w-4 h-4 text-green-600" />}
                        {request.status === "rejected" && <XCircle className="w-4 h-4 text-red-600" />}
                        {request.status === "delegated" && <Users className="w-4 h-4 text-blue-600" />}
                      </div>
                      <div>
                        <div className="font-medium">{request.invoiceNumber}</div>
                        <div className="text-sm text-slate-600">{request.vendorName}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-medium">${request.amount.toLocaleString()}</div>
                      <div className="text-xs text-slate-500">
                        {request.approvals.find(a => a.actionAt)?.actionAt &&
                          new Date(request.approvals.find(a => a.actionAt)!.actionAt!).toLocaleDateString()
                        }
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Request Details Dialog */}
      {selectedRequest && (
        <Dialog open={!!selectedRequest} onOpenChange={() => setSelectedRequest(null)}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Approval Request Details</DialogTitle>
              <DialogDescription>
                Review and act on approval request for {selectedRequest.invoiceNumber}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-6">
              {/* Request Information */}
              <div className="grid grid-cols-2 gap-4">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">Invoice Information</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Invoice Number</span>
                      <span className="font-mono font-semibold">{selectedRequest.invoiceNumber}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Vendor</span>
                      <span className="font-semibold">{selectedRequest.vendorName}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Amount</span>
                      <span className="font-bold text-lg">${selectedRequest.amount.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Request Type</span>
                      <Badge className={getRequestTypeColor(selectedRequest.requestType)}>
                        {selectedRequest.requestType.replace("_", " ").toUpperCase()}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base">Request Details</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Requested by</span>
                      <span className="font-semibold">{selectedRequest.requesterName}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Submitted</span>
                      <span>{new Date(selectedRequest.submittedAt).toLocaleDateString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Due by</span>
                      <span className={cn(
                        "font-medium",
                        new Date(selectedRequest.dueBy) < new Date() && "text-red-600"
                      )}>
                        {new Date(selectedRequest.dueBy).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-slate-600">Priority</span>
                      <Badge className={getPriorityColor(selectedRequest.priority)}>
                        {selectedRequest.priority}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Approval Chain */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Approval Chain</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {selectedRequest.approvals.map((step, index) => (
                      <div key={step.id} className="flex items-center gap-3">
                        <div className="flex flex-col items-center">
                          <div className={cn(
                            "w-10 h-10 rounded-full flex items-center justify-center border-2",
                            step.status === "approved" && "border-green-500 bg-green-50",
                            step.status === "pending" && "border-yellow-500 bg-yellow-50",
                            step.status === "rejected" && "border-red-500 bg-red-50",
                            step.status === "delegated" && "border-blue-500 bg-blue-50"
                          )}>
                            {step.status === "approved" && <CheckCircle2 className="w-5 h-5 text-green-600" />}
                            {step.status === "pending" && <Clock className="w-5 h-5 text-yellow-600" />}
                            {step.status === "rejected" && <XCircle className="w-5 h-5 text-red-600" />}
                            {step.status === "delegated" && <Users className="w-5 h-5 text-blue-600" />}
                          </div>
                          {index < selectedRequest.approvals.length - 1 && (
                            <div className="w-0.5 h-8 bg-slate-300"></div>
                          )}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <div>
                              <div className="font-medium">{step.approverName}</div>
                              <div className="text-sm text-slate-600">{step.approverRole}</div>
                              {step.conditions.length > 0 && (
                                <div className="text-xs text-slate-500 mt-1">
                                  {step.conditions.join(", ")}
                                </div>
                              )}
                            </div>
                            <div className="text-right">
                              <Badge className={getStatusColor(step.status)}>
                                {step.status}
                              </Badge>
                              {step.actionAt && (
                                <div className="text-xs text-slate-500 mt-1">
                                  {new Date(step.actionAt).toLocaleString()}
                                </div>
                              )}
                              {step.delegatedTo && (
                                <div className="text-xs text-blue-600 mt-1">
                                  Delegated to {step.delegatedTo}
                                </div>
                              )}
                            </div>
                          </div>
                          {step.comments && (
                            <div className="mt-2 p-2 bg-slate-50 rounded text-sm text-slate-700">
                              {step.comments}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Comments Section */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Comments</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3 max-h-48 overflow-y-auto mb-4">
                    {selectedRequest.comments.map((comment) => (
                      <div key={comment.id} className="flex gap-3">
                        <Avatar className="w-8 h-8">
                          <AvatarFallback>{comment.authorName.split(' ').map(n => n[0]).join('')}</AvatarFallback>
                        </Avatar>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-sm">{comment.authorName}</span>
                            <span className="text-xs text-slate-500">
                              {new Date(comment.timestamp).toLocaleString()}
                            </span>
                            <Badge variant="outline" className="text-xs">
                              {comment.type}
                            </Badge>
                          </div>
                          <p className="text-sm text-slate-700">{comment.message}</p>
                        </div>
                      </div>
                    ))}
                  </div>

                  {selectedRequest.approvals.some(step => step.approverId === currentUser.id && step.status === "pending") && (
                    <div className="flex gap-2">
                      <Textarea
                        placeholder="Add a comment..."
                        value={newComment}
                        onChange={(e) => setNewComment(e.target.value)}
                        className="flex-1"
                      />
                      <Button onClick={() => addComment(selectedRequest.id)}>
                        <Send className="w-4 h-4" />
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Action Buttons */}
              {selectedRequest.approvals.some(step => step.approverId === currentUser.id && step.status === "pending") && (
                <div className="flex items-center justify-between border-t pt-6">
                  <div className="text-sm text-slate-600">
                    Your approval limit: <span className="font-semibold">${currentUser.role.limits.maxApprovalAmount.toLocaleString()}</span>
                  </div>
                  <div className="flex gap-3">
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="destructive">
                          <XCircle className="w-4 h-4 mr-2" />
                          Reject
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Reject Approval Request</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to reject this approval request? This action cannot be undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => handleReject(selectedRequest.id, "Rejected")}>
                            Reject Request
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>

                    <Button variant="outline">
                      <Users className="w-4 h-4 mr-2" />
                      Delegate
                    </Button>

                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button className="bg-green-600 hover:bg-green-700">
                          <CheckCircle2 className="w-4 h-4 mr-2" />
                          Approve
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Approve Request</AlertDialogTitle>
                          <AlertDialogDescription>
                            Approve this invoice for ${selectedRequest.amount.toLocaleString()} from {selectedRequest.vendorName}?
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction onClick={() => handleApprove(selectedRequest.id, "Approved")}>
                            Approve Request
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}