"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Checkbox } from "@/components/ui/checkbox"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Progress } from "@/components/ui/progress"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
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
  FileText,
  Plus,
  Search,
  Filter,
  Download,
  Upload,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  Eye,
  Edit,
  Trash2,
  MoreHorizontal,
  Calendar,
  DollarSign,
  Building,
  User,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  X,
  CheckSquare,
  Square,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Users,
  FileCheck,
  AlertTriangle,
  Settings,
  Bell,
  Mail,
  Phone,
  MapPin,
  Star,
  Archive,
  Send,
  Reply,
  Forward,
  Printer,
  Share2,
  Copy,
  Move
} from "lucide-react"
import { cn } from "@/lib/utils"

// Types
interface Invoice {
  id: string
  invoiceNumber: string
  vendorName: string
  vendorId: string
  amount: number
  currency: string
  dueDate: string
  status: "pending_review" | "approved" | "rejected" | "needs_more_info" | "processing" | "paid"
  assignedTo?: string
  uploadedAt: string
  reviewedAt?: string
  priority: "low" | "medium" | "high" | "urgent"
  confidence: number
  validationIssues: number
  reviewer?: string
  tags?: string[]
  hasAttachments: boolean
  comments: number
}

interface FilterState {
  search: string
  status: string[]
  priority: string[]
  vendor: string[]
  assignedTo: string[]
  dateRange: string
  amountRange: string
}

interface Column {
  key: string
  label: string
  sortable: boolean
  width?: string
}

export function InvoiceDashboard({ onInvoiceSelect }: { onInvoiceSelect?: (invoice: any) => void }) {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedInvoices, setSelectedInvoices] = useState<string[]>([])
  const [filters, setFilters] = useState<FilterState>({
    search: "",
    status: [],
    priority: [],
    vendor: [],
    assignedTo: [],
    dateRange: "",
    amountRange: ""
  })
  const [sortColumn, setSortColumn] = useState<string>("uploadedAt")
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc")
  const [currentPage, setCurrentPage] = useState(1)
  const [showBulkActions, setShowBulkActions] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const invoicesPerPage = 25

  // Mock data
  const mockInvoices: Invoice[] = [
    {
      id: "1",
      invoiceNumber: "INV-2024-5647",
      vendorName: "Acme Corp Manufacturing",
      vendorId: "VENDOR-4521",
      amount: 12450.50,
      currency: "USD",
      dueDate: "2024-11-30",
      status: "pending_review",
      assignedTo: "john.doe",
      uploadedAt: "2024-11-05T14:32:00Z",
      priority: "high",
      confidence: 0.95,
      validationIssues: 2,
      reviewer: "Jane Smith",
      tags: ["Q4", "Manufacturing"],
      hasAttachments: true,
      comments: 3
    },
    {
      id: "2",
      invoiceNumber: "INV-2024-5648",
      vendorName: "Global Supplies Inc",
      vendorId: "VENDOR-1234",
      amount: 8750.00,
      currency: "USD",
      dueDate: "2024-12-15",
      status: "approved",
      uploadedAt: "2024-11-04T09:15:00Z",
      reviewedAt: "2024-11-05T10:30:00Z",
      priority: "medium",
      confidence: 0.98,
      validationIssues: 0,
      reviewer: "Bob Johnson",
      tags: ["Office Supplies"],
      hasAttachments: false,
      comments: 1
    },
    {
      id: "3",
      invoiceNumber: "INV-2024-5649",
      vendorName: "Tech Solutions Ltd",
      vendorId: "VENDOR-6789",
      amount: 25000.00,
      currency: "USD",
      dueDate: "2024-11-20",
      status: "needs_more_info",
      assignedTo: "sarah.wilson",
      uploadedAt: "2024-11-03T16:45:00Z",
      priority: "urgent",
      confidence: 0.72,
      validationIssues: 5,
      tags: ["Software", "License"],
      hasAttachments: true,
      comments: 7
    },
    {
      id: "4",
      invoiceNumber: "INV-2024-5650",
      vendorName: "Office Depot",
      vendorId: "VENDOR-2468",
      amount: 1250.75,
      currency: "USD",
      dueDate: "2024-12-01",
      status: "processing",
      uploadedAt: "2024-11-06T11:20:00Z",
      priority: "low",
      confidence: 0.91,
      validationIssues: 1,
      tags: ["Stationery"],
      hasAttachments: false,
      comments: 0
    },
    {
      id: "5",
      invoiceNumber: "INV-2024-5651",
      vendorName: "Cleaning Services Co",
      vendorId: "VENDOR-1357",
      amount: 3500.00,
      currency: "USD",
      dueDate: "2024-11-25",
      status: "rejected",
      uploadedAt: "2024-11-02T13:10:00Z",
      reviewedAt: "2024-11-03T09:45:00Z",
      priority: "medium",
      confidence: 0.65,
      validationIssues: 3,
      reviewer: "Mike Davis",
      tags: ["Services", "Monthly"],
      hasAttachments: true,
      comments: 5
    }
  ]

  useEffect(() => {
    // Simulate API call
    setTimeout(() => {
      setInvoices(mockInvoices)
      setLoading(false)
    }, 1000)
  }, [])

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc")
    } else {
      setSortColumn(column)
      setSortDirection("asc")
    }
  }

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedInvoices(filteredInvoices.map(inv => inv.id))
    } else {
      setSelectedInvoices([])
    }
  }

  const handleSelectInvoice = (invoiceId: string, checked: boolean) => {
    if (checked) {
      setSelectedInvoices(prev => [...prev, invoiceId])
    } else {
      setSelectedInvoices(prev => prev.filter(id => id !== invoiceId))
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "approved":
        return "bg-green-50 text-green-700 border-green-200"
      case "rejected":
        return "bg-red-50 text-red-700 border-red-200"
      case "needs_more_info":
        return "bg-yellow-50 text-yellow-700 border-yellow-200"
      case "processing":
        return "bg-blue-50 text-blue-700 border-blue-200"
      case "paid":
        return "bg-emerald-50 text-emerald-700 border-emerald-200"
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

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.95) return "text-green-600"
    if (confidence >= 0.85) return "text-blue-600"
    if (confidence >= 0.75) return "text-yellow-600"
    return "text-red-600"
  }

  // Filter invoices
  const filteredInvoices = invoices.filter(invoice => {
    if (filters.search && !invoice.invoiceNumber.toLowerCase().includes(filters.search.toLowerCase()) &&
        !invoice.vendorName.toLowerCase().includes(filters.search.toLowerCase())) {
      return false
    }
    if (filters.status.length > 0 && !filters.status.includes(invoice.status)) {
      return false
    }
    if (filters.priority.length > 0 && !filters.priority.includes(invoice.priority)) {
      return false
    }
    return true
  })

  // Sort invoices
  const sortedInvoices = [...filteredInvoices].sort((a, b) => {
    const aValue = a[sortColumn as keyof Invoice]
    const bValue = b[sortColumn as keyof Invoice]

    if (aValue === undefined) return 1
    if (bValue === undefined) return -1

    let comparison = 0
    if (typeof aValue === 'string' && typeof bValue === 'string') {
      comparison = aValue.localeCompare(bValue)
    } else if (typeof aValue === 'number' && typeof bValue === 'number') {
      comparison = aValue - bValue
    }

    return sortDirection === "asc" ? comparison : -comparison
  })

  // Pagination
  const totalPages = Math.ceil(sortedInvoices.length / invoicesPerPage)
  const paginatedInvoices = sortedInvoices.slice(
    (currentPage - 1) * invoicesPerPage,
    currentPage * invoicesPerPage
  )

  // Calculate statistics
  const stats = {
    total: invoices.length,
    pending: invoices.filter(inv => inv.status === "pending_review").length,
    approved: invoices.filter(inv => inv.status === "approved").length,
    rejected: invoices.filter(inv => inv.status === "rejected").length,
    avgConfidence: invoices.reduce((sum, inv) => sum + inv.confidence, 0) / invoices.length,
    totalAmount: invoices.reduce((sum, inv) => sum + inv.amount, 0),
    urgentItems: invoices.filter(inv => inv.priority === "urgent").length
  }

  const columns: Column[] = [
    { key: "invoiceNumber", label: "Invoice Number", sortable: true, width: "150px" },
    { key: "vendorName", label: "Vendor", sortable: true, width: "200px" },
    { key: "amount", label: "Amount", sortable: true, width: "120px" },
    { key: "dueDate", label: "Due Date", sortable: true, width: "120px" },
    { key: "status", label: "Status", sortable: true, width: "120px" },
    { key: "assignedTo", label: "Assigned To", sortable: true, width: "150px" },
    { key: "confidence", label: "Confidence", sortable: true, width: "100px" },
    { key: "validationIssues", label: "Issues", sortable: true, width: "80px" },
    { key: "uploadedAt", label: "Uploaded", sortable: true, width: "120px" }
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="text-center space-y-4">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-blue-600" />
          <p className="text-slate-600">Loading invoices...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Invoice Management</h1>
          <p className="text-slate-600">Review and process invoice submissions</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline">
            <Upload className="w-4 h-4 mr-2" />
            Upload Invoice
          </Button>
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            New Invoice
          </Button>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Invoices</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">
              +20.1% from last month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Review</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.pending}</div>
            <p className="text-xs text-muted-foreground">
              {Math.round((stats.pending / stats.total) * 100)}% of total
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Approved</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.approved}</div>
            <p className="text-xs text-muted-foreground">
              {Math.round((stats.approved / stats.total) * 100)}% approval rate
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Amount</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${stats.totalAmount.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground">
              Across all invoices
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters and Search */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4 flex-1">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Search invoices..."
                  value={filters.search}
                  onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                  className="pl-10"
                />
              </div>

              <Button
                variant="outline"
                onClick={() => setShowFilters(!showFilters)}
                className="flex items-center gap-2"
              >
                <Filter className="w-4 h-4" />
                Filters
                {(filters.status.length > 0 || filters.priority.length > 0) && (
                  <Badge variant="secondary" className="ml-1">
                    {filters.status.length + filters.priority.length}
                  </Badge>
                )}
              </Button>

              <Button variant="outline" onClick={() => setInvoices(mockInvoices)}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </div>

            {selectedInvoices.length > 0 && (
              <div className="flex items-center gap-3">
                <span className="text-sm text-slate-600">
                  {selectedInvoices.length} selected
                </span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm">
                      <MoreHorizontal className="w-4 h-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem>
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      Approve Selected
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <X className="w-4 h-4 mr-2" />
                      Reject Selected
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <Mail className="w-4 h-4 mr-2" />
                      Send for Review
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem>
                      <Archive className="w-4 h-4 mr-2" />
                      Archive Selected
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            )}
          </div>

          {showFilters && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-4 border-t">
              <div>
                <label className="text-sm font-medium mb-2 block">Status</label>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="All statuses" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="pending_review">Pending Review</SelectItem>
                    <SelectItem value="approved">Approved</SelectItem>
                    <SelectItem value="rejected">Rejected</SelectItem>
                    <SelectItem value="needs_more_info">Needs More Info</SelectItem>
                    <SelectItem value="processing">Processing</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">Priority</label>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="All priorities" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="urgent">Urgent</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">Date Range</label>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="Select range" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="today">Today</SelectItem>
                    <SelectItem value="week">This Week</SelectItem>
                    <SelectItem value="month">This Month</SelectItem>
                    <SelectItem value="quarter">This Quarter</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">Amount Range</label>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="Select range" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="0-1000">$0 - $1,000</SelectItem>
                    <SelectItem value="1000-5000">$1,000 - $5,000</SelectItem>
                    <SelectItem value="5000-10000">$5,000 - $10,000</SelectItem>
                    <SelectItem value="10000+">$10,000+</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
        </CardHeader>
      </Card>

      {/* Invoices Table */}
      <Card>
        <CardHeader>
          <CardTitle>Invoices ({filteredInvoices.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <Checkbox
                      checked={selectedInvoices.length === paginatedInvoices.length}
                      onCheckedChange={handleSelectAll}
                    />
                  </TableHead>
                  {columns.map((column) => (
                    <TableHead key={column.key} style={{ width: column.width }}>
                      {column.sortable ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-auto p-0 font-semibold"
                          onClick={() => handleSort(column.key)}
                        >
                          {column.label}
                          <ArrowUpDown className="ml-2 h-4 w-4" />
                        </Button>
                      ) : (
                        column.label
                      )}
                    </TableHead>
                  ))}
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedInvoices.map((invoice) => (
                  <TableRow
                    key={invoice.id}
                    className={cn(
                      "cursor-pointer hover:bg-slate-50",
                      selectedInvoices.includes(invoice.id) && "bg-blue-50"
                    )}
                    onClick={() => onInvoiceSelect && onInvoiceSelect(invoice)}
                  >
                    <TableCell>
                      <Checkbox
                        checked={selectedInvoices.includes(invoice.id)}
                        onCheckedChange={(checked) => handleSelectInvoice(invoice.id, checked as boolean)}
                      />
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-semibold">{invoice.invoiceNumber}</span>
                        {invoice.hasAttachments && (
                          <Paperclip className="w-4 h-4 text-slate-400" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div>
                        <div className="font-medium">{invoice.vendorName}</div>
                        <div className="text-sm text-slate-500">{invoice.vendorId}</div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="font-semibold">${invoice.amount.toFixed(2)}</div>
                      <div className="text-sm text-slate-500">{invoice.currency}</div>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <Badge className={getStatusColor(invoice.status)}>
                          {invoice.status.replace("_", " ")}
                        </Badge>
                        <div>
                          <Badge className={getPriorityColor(invoice.priority)} variant="secondary">
                            {invoice.priority}
                          </Badge>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      {invoice.assignedTo ? (
                        <div className="flex items-center gap-2">
                          <Avatar className="h-6 w-6">
                            <AvatarImage src={`/avatars/${invoice.assignedTo}.jpg`} />
                            <AvatarFallback>
                              {invoice.assignedTo.split('.').map(n => n[0]).join('').toUpperCase()}
                            </AvatarFallback>
                          </Avatar>
                          <span className="text-sm">{invoice.assignedTo}</span>
                        </div>
                      ) : (
                        <span className="text-sm text-slate-400">Unassigned</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className={cn("font-semibold", getConfidenceColor(invoice.confidence))}>
                          {(invoice.confidence * 100).toFixed(0)}%
                        </span>
                        {invoice.validationIssues > 0 && (
                          <Badge variant="outline" className="text-amber-600 border-amber-200">
                            {invoice.validationIssues}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-center">
                        {invoice.validationIssues > 0 ? (
                          <Badge variant="destructive">{invoice.validationIssues}</Badge>
                        ) : (
                          <CheckCircle2 className="w-4 h-4 text-green-600 mx-auto" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        {new Date(invoice.uploadedAt).toLocaleDateString()}
                      </div>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem>
                            <Eye className="w-4 h-4 mr-2" />
                            View Details
                          </DropdownMenuItem>
                          <DropdownMenuItem>
                            <Edit className="w-4 h-4 mr-2" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem>
                            <Send className="w-4 h-4 mr-2" />
                            Send for Review
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem>
                            <Download className="w-4 h-4 mr-2" />
                            Download
                          </DropdownMenuItem>
                          <DropdownMenuItem>
                            <Share2 className="w-4 h-4 mr-2" />
                            Share
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem className="text-red-600">
                            <Trash2 className="w-4 h-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-2 py-4">
            <div className="flex items-center space-x-2 text-sm text-muted-foreground">
              <span>Showing {((currentPage - 1) * invoicesPerPage) + 1} to {Math.min(currentPage * invoicesPerPage, sortedInvoices.length)} of {sortedInvoices.length} invoices</span>
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </Button>
              <div className="flex items-center space-x-1">
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const page = i + 1
                  return (
                    <Button
                      key={page}
                      variant={currentPage === page ? "default" : "outline"}
                      size="sm"
                      onClick={() => setCurrentPage(page)}
                    >
                      {page}
                    </Button>
                  )
                })}
                {totalPages > 5 && (
                  <>
                    <span>...</span>
                    <Button
                      variant={currentPage === totalPages ? "default" : "outline"}
                      size="sm"
                      onClick={() => setCurrentPage(totalPages)}
                    >
                      {totalPages}
                    </Button>
                  </>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}