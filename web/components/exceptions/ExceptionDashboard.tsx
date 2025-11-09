"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Checkbox } from "@/components/ui/checkbox"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
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
  AlertCircle,
  CheckCircle2,
  Clock,
  Eye,
  Edit,
  MoreHorizontal,
  Search,
  Filter,
  RefreshCw,
  User,
  Calendar,
  TrendingUp,
  AlertTriangle,
  FileText,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Users,
  BarChart3,
  Settings,
  Download,
  Mail,
  Phone,
  MessageSquare,
  Flag,
  Archive,
  RotateCcw
} from "lucide-react"
import { cn } from "@/lib/utils"
import { ExceptionFilter } from "./ExceptionFilter"
import { ConfidenceMeter } from "./ConfidenceMeter"
import { getSeverityColor, getStatusColor, formatResolutionTime } from "@/lib/exception-types"
import { useExceptions, useBatchOperations, useExceptionAnalytics } from "@/hooks/useExceptions"

interface ExceptionDashboardProps {
  onExceptionSelect?: (exception: any) => void
}

export function ExceptionDashboard({ onExceptionSelect }: ExceptionDashboardProps) {
  const {
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
    hasSelected,
    allSelected,
  } = useExceptions()

  const { batchResolve, batchAssign, batchClose, loading: batchLoading } = useBatchOperations()
  const { analytics } = useExceptionAnalytics()

  const [showFilters, setShowFilters] = useState(false)
  const [sortBy, setSortBy] = useState("created_at")
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc")
  const [searchQuery, setSearchQuery] = useState("")
  const [showBulkActions, setShowBulkActions] = useState(false)

  const exceptionsPerPage = 25
  const totalPages = Math.ceil(total / exceptionsPerPage)

  // Auto-hide bulk actions when no items selected
  useEffect(() => {
    setShowBulkActions(hasSelected)
  }, [hasSelected])

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc")
    } else {
      setSortBy(column)
      setSortDirection("asc")
    }
  }

  const handleSearch = (value: string) => {
    setSearchQuery(value)
    updateFilters({ search: value })
  }

  const handleBulkResolve = async (resolutionMethod: string) => {
    try {
      await batchResolve({
        exception_ids: selectedExceptions,
        resolution_method: resolutionMethod,
      })
      refreshExceptions()
      selectAllExceptions(false)
    } catch (error) {
      console.error('Bulk resolve failed:', error)
    }
  }

  const handleBulkAssign = async (assignedTo: string) => {
    try {
      await batchAssign(selectedExceptions, assignedTo)
      refreshExceptions()
      selectAllExceptions(false)
    } catch (error) {
      console.error('Bulk assign failed:', error)
    }
  }

  const getPriorityIcon = (severity: string) => {
    switch (severity) {
      case "critical":
        return <AlertTriangle className="w-4 h-4 text-red-600" />
      case "high":
        return <AlertCircle className="w-4 h-4 text-orange-600" />
      case "medium":
        return <Clock className="w-4 h-4 text-yellow-600" />
      default:
        return <Flag className="w-4 h-4 text-blue-600" />
    }
  }

  const columns = [
    { key: "title", label: "Exception", sortable: true },
    { key: "reason_code", label: "Reason", sortable: true },
    { key: "severity", label: "Severity", sortable: true },
    { key: "status", label: "Status", sortable: true },
    { key: "overall_confidence", label: "Confidence", sortable: true },
    { key: "assigned_to", label: "Assigned To", sortable: true },
    { key: "created_at", label: "Created", sortable: true },
    { key: "invoice_number", label: "Invoice", sortable: true },
    { key: "vendor_name", label: "Vendor", sortable: true },
  ]

  // Sort exceptions
  const sortedExceptions = [...exceptions].sort((a, b) => {
    const aValue = a[sortBy as keyof typeof a]
    const bValue = b[sortBy as keyof typeof b]

    if (aValue === undefined) return 1
    if (bValue === undefined) return -1

    let comparison = 0
    if (typeof aValue === 'string' && typeof bValue === 'string') {
      comparison = aValue.localeCompare(bValue)
    } else if (typeof aValue === 'number' && typeof bValue === 'number') {
      comparison = aValue - bValue
    } else if (aValue instanceof Date && bValue instanceof Date) {
      comparison = aValue.getTime() - bValue.getTime()
    }

    return sortDirection === "asc" ? comparison : -comparison
  })

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="text-center space-y-4">
          <AlertTriangle className="w-12 h-12 text-red-600 mx-auto" />
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Error loading exceptions</h3>
            <p className="text-slate-600">{error}</p>
          </div>
          <Button onClick={refreshExceptions} variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            Try Again
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Exception Management</h1>
          <p className="text-slate-600">Review and resolve invoice processing exceptions</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
          <Button variant="outline">
            <BarChart3 className="w-4 h-4 mr-2" />
            Analytics
          </Button>
          <Button>
            <Settings className="w-4 h-4 mr-2" />
            Settings
          </Button>
        </div>
      </div>

      {/* Statistics Cards */}
      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Exceptions</CardTitle>
              <AlertCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{analytics.total_exceptions}</div>
              <p className="text-xs text-muted-foreground">
                Active issues requiring attention
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Open Exceptions</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{analytics.open_exceptions}</div>
              <p className="text-xs text-muted-foreground">
                Pending resolution
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Resolved Today</CardTitle>
              <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{analytics.resolved_today}</div>
              <p className="text-xs text-muted-foreground">
                Issues resolved today
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Resolution Time</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatResolutionTime(analytics.avg_resolution_time_hours)}
              </div>
              <p className="text-xs text-muted-foreground">
                Average time to resolve
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <ExceptionFilter
        filters={filters}
        onFiltersChange={updateFilters}
        onClearFilters={clearFilters}
      />

      {/* Bulk Actions Bar */}
      {showBulkActions && (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-blue-900">
                  {selectedExceptions.length} exceptions selected
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => selectAllExceptions(false)}
                  className="text-blue-700"
                >
                  Clear selection
                </Button>
              </div>
              <div className="flex items-center gap-2">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button size="sm" variant="outline" disabled={batchLoading}>
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      Resolve
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuItem onClick={() => handleBulkResolve("manual_correction")}>
                      Manual Correction
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleBulkResolve("vendor_contact")}>
                      Contact Vendor
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleBulkResolve("system_reprocess")}>
                      Reprocess
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleBulkResolve("exception_overridden")}>
                      Override Exception
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button size="sm" variant="outline" disabled={batchLoading}>
                      <User className="w-4 h-4 mr-2" />
                      Assign
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuItem onClick={() => handleBulkAssign("john.doe")}>
                      John Doe
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleBulkAssign("jane.smith")}>
                      Jane Smith
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleBulkAssign("mike.wilson")}>
                      Mike Wilson
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>

                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button size="sm" variant="outline" disabled={batchLoading}>
                      <Archive className="w-4 h-4 mr-2" />
                      Close
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Close selected exceptions?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will close {selectedExceptions.length} exceptions. This action cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={() => batchClose(selectedExceptions)}>
                        Close Exceptions
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Exceptions Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Exceptions ({total})</CardTitle>
            <Button variant="outline" onClick={refreshExceptions} disabled={loading}>
              <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center min-h-96">
              <div className="text-center space-y-4">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto text-blue-600" />
                <p className="text-slate-600">Loading exceptions...</p>
              </div>
            </div>
          ) : exceptions.length === 0 ? (
            <div className="flex items-center justify-center min-h-96">
              <div className="text-center space-y-4">
                <CheckCircle2 className="w-12 h-12 text-green-600 mx-auto" />
                <div>
                  <h3 className="text-lg font-semibold text-slate-900">No exceptions found</h3>
                  <p className="text-slate-600">
                    {searchQuery ? "Try adjusting your search or filters" : "All invoices are processing normally"}
                  </p>
                </div>
                {(searchQuery || Object.keys(filters).length > 0) && (
                  <Button variant="outline" onClick={clearFilters}>
                    <RotateCcw className="w-4 h-4 mr-2" />
                    Clear Filters
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <Checkbox
                        checked={allSelected}
                        onCheckedChange={(checked) => selectAllExceptions(checked as boolean)}
                      />
                    </TableHead>
                    {columns.map((column) => (
                      <TableHead key={column.key}>
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
                  {sortedExceptions.map((exception) => (
                    <TableRow
                      key={exception.id}
                      className={cn(
                        "cursor-pointer hover:bg-slate-50",
                        selectedExceptions.includes(exception.id) && "bg-blue-50"
                      )}
                      onClick={() => onExceptionSelect && onExceptionSelect(exception)}
                    >
                      <TableCell>
                        <Checkbox
                          checked={selectedExceptions.includes(exception.id)}
                          onCheckedChange={(checked) => selectException(exception.id, checked as boolean)}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getPriorityIcon(exception.severity)}
                          <div>
                            <div className="font-medium">{exception.title}</div>
                            <div className="text-sm text-slate-500 line-clamp-1">
                              {exception.description}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {exception.reason_code.replace(/_/g, " ")}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={getSeverityColor(exception.severity)}>
                          {exception.severity}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge className={getStatusColor(exception.status)}>
                          {exception.status.replace(/_/g, " ")}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <ConfidenceMeter
                          confidence={exception.overall_confidence}
                          threshold={exception.min_confidence_threshold}
                          size="sm"
                          showLabel={false}
                        />
                      </TableCell>
                      <TableCell>
                        {exception.assigned_to ? (
                          <div className="flex items-center gap-2">
                            <Avatar className="h-6 w-6">
                              <AvatarImage src={`/avatars/${exception.assigned_to}.jpg`} />
                              <AvatarFallback>
                                {exception.assigned_to.split('.').map(n => n[0]).join('').toUpperCase()}
                              </AvatarFallback>
                            </Avatar>
                            <span className="text-sm">{exception.assigned_to}</span>
                          </div>
                        ) : (
                          <span className="text-sm text-slate-400">Unassigned</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">
                          {new Date(exception.created_at).toLocaleDateString()}
                        </div>
                        <div className="text-xs text-slate-500">
                          {new Date(exception.created_at).toLocaleTimeString()}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="font-mono text-sm">
                          {exception.invoice_number || "N/A"}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">
                          {exception.vendor_name || "Unknown"}
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
                              Edit Exception
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem>
                              <User className="w-4 h-4 mr-2" />
                              Assign
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <CheckCircle2 className="w-4 h-4 mr-2" />
                              Resolve
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Mail className="w-4 h-4 mr-2" />
                              Contact Vendor
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem>
                              <Archive className="w-4 h-4 mr-2" />
                              Close Exception
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {/* Pagination */}
          {total > exceptionsPerPage && (
            <div className="flex items-center justify-between px-2 py-4">
              <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                <span>
                  Showing {pagination.skip + 1} to {Math.min(pagination.skip + exceptionsPerPage, total)} of {total} exceptions
                </span>
              </div>
              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPagination({ ...pagination, skip: Math.max(0, pagination.skip - exceptionsPerPage) })}
                  disabled={pagination.skip === 0}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                <div className="flex items-center space-x-1">
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    const page = i + 1
                    const isCurrentPage = pagination.skip === (page - 1) * exceptionsPerPage
                    return (
                      <Button
                        key={page}
                        variant={isCurrentPage ? "default" : "outline"}
                        size="sm"
                        onClick={() => setPagination({ ...pagination, skip: (page - 1) * exceptionsPerPage })}
                      >
                        {page}
                      </Button>
                    )
                  })}
                  {totalPages > 5 && (
                    <>
                      <span>...</span>
                      <Button
                        variant={pagination.skip === (totalPages - 1) * exceptionsPerPage ? "default" : "outline"}
                        size="sm"
                        onClick={() => setPagination({ ...pagination, skip: (totalPages - 1) * exceptionsPerPage })}
                      >
                        {totalPages}
                      </Button>
                    </>
                  )}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPagination({ ...pagination, skip: Math.min(total, pagination.skip + exceptionsPerPage) })}
                  disabled={pagination.skip + exceptionsPerPage >= total}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}