"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import {
  CheckCircle2,
  AlertTriangle,
  X,
  Search,
  Filter,
  Users,
  Clock,
  TrendingUp,
  AlertCircle,
  Settings,
  Play,
  Pause,
  RotateCcw,
  Download,
  Eye,
  Edit,
  MoreHorizontal,
  ChevronRight,
  Info,
  Zap,
  Target,
  Layers,
  FileText,
  User,
  Calendar,
  ArrowUpDown,
  BarChart3
} from "lucide-react"
import { cn } from "@/lib/utils"
import { getSeverityColor, getStatusColor, getExceptionReasonDescription, BatchResolutionRequest } from "@/lib/exception-types"
import { useExceptions, useBatchOperations } from "@/hooks/useExceptions"

interface BatchResolutionProps {
  selectedExceptions: string[]
  onExceptionsProcessed?: (results: any) => void
  onClose?: () => void
}

export function BatchResolution({ selectedExceptions, onExceptionsProcessed, onClose }: BatchResolutionProps) {
  const { exceptions, refreshExceptions } = useExceptions()
  const { batchResolve, batchAssign, batchClose, loading: batchLoading } = useBatchOperations()

  const [activeTab, setActiveTab] = useState("similar")
  const [resolutionMethod, setResolutionMethod] = useState("")
  const [resolutionNotes, setResolutionNotes] = useState("")
  const [assignedTo, setAssignedTo] = useState("")
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState("")
  const [isProcessing, setIsProcessing] = useState(false)
  const [processingProgress, setProcessingProgress] = useState(0)
  const [processingResults, setProcessingResults] = useState<any>(null)
  const [showConfirmation, setShowConfirmation] = useState(false)

  // Filter exceptions based on selection
  const selectedExceptionDetails = exceptions.filter(ex => selectedExceptions.includes(ex.id))

  // Group similar exceptions
  const similarExceptions = selectedExceptionDetails.reduce((groups, exception) => {
    const key = `${exception.reason_code}_${exception.severity}`
    if (!groups[key]) {
      groups[key] = {
        reason_code: exception.reason_code,
        severity: exception.severity,
        exceptions: [],
        title: getExceptionReasonDescription(exception.reason_code),
        confidence: exception.overall_confidence,
      }
    }
    groups[key].exceptions.push(exception)
    return groups
  }, {} as Record<string, any>)

  const similarGroups = Object.values(similarExceptions)

  const teamMembers = [
    { id: "john.doe", name: "John Doe", role: "Senior Analyst" },
    { id: "jane.smith", name: "Jane Smith", role: "Accounts Payable Lead" },
    { id: "mike.wilson", name: "Mike Wilson", role: "Finance Manager" },
    { id: "sarah.jones", name: "Sarah Jones", role: "Junior Analyst" },
  ]

  const resolutionMethods = [
    { value: "manual_correction", label: "Manual Correction", description: "Manually correct the extracted data" },
    { value: "vendor_contact", label: "Contact Vendor", description: "Reach out to vendor for clarification" },
    { value: "system_reprocess", label: "Reprocess Document", description: "Run document through extraction again" },
    { value: "exception_overridden", label: "Override Exception", description: "Override validation and approve" },
    { value: "data_enrichment", label: "Enrich Data", description: "Add missing data from external sources" },
    { value: "business_rule_adjusted", label: "Adjust Business Rules", description: "Modify validation rules" },
  ]

  const handleProcessBatch = async () => {
    if (!resolutionMethod) return

    setIsProcessing(true)
    setProcessingProgress(0)
    setProcessingResults(null)

    try {
      // Simulate progress updates
      const progressInterval = setInterval(() => {
        setProcessingProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval)
            return 90
          }
          return prev + Math.random() * 10
        })
      }, 200)

      const batchRequest: BatchResolutionRequest = {
        exception_ids: selectedExceptions,
        resolution_method: resolutionMethod,
        resolution_notes: resolutionNotes,
        assign_to: assignedTo || undefined,
        tags: tags.length > 0 ? tags : undefined,
      }

      const results = await batchResolve(batchRequest)

      clearInterval(progressInterval)
      setProcessingProgress(100)
      setProcessingResults(results)

      // Refresh the exceptions list
      setTimeout(() => {
        refreshExceptions()
        onExceptionsProcessed?.(results)
      }, 1000)

    } catch (error) {
      console.error('Batch processing failed:', error)
      setProcessingResults({
        resolved: [],
        failed: selectedExceptions.map(id => ({ id, error: 'Processing failed' }))
      })
    } finally {
      setIsProcessing(false)
    }
  }

  const handleAddTag = () => {
    if (tagInput.trim() && !tags.includes(tagInput.trim())) {
      setTags([...tags, tagInput.trim()])
      setTagInput("")
    }
  }

  const handleRemoveTag = (tagToRemove: string) => {
    setTags(tags.filter(tag => tag !== tagToRemove))
  }

  const getGroupStats = () => {
    const stats = {
      total: selectedExceptionDetails.length,
      byReason: {} as Record<string, number>,
      bySeverity: {} as Record<string, number>,
      avgConfidence: 0,
    }

    selectedExceptionDetails.forEach(exception => {
      stats.byReason[exception.reason_code] = (stats.byReason[exception.reason_code] || 0) + 1
      stats.bySeverity[exception.severity] = (stats.bySeverity[exception.severity] || 0) + 1
      stats.avgConfidence += exception.overall_confidence
    })

    stats.avgConfidence = stats.avgConfidence / stats.total

    return stats
  }

  const stats = getGroupStats()

  if (selectedExceptions.length === 0) {
    return (
      <Card>
        <CardContent className="py-12">
          <div className="text-center space-y-4">
            <Info className="w-12 h-12 text-slate-400 mx-auto" />
            <div>
              <h3 className="text-lg font-semibold text-slate-900">No Exceptions Selected</h3>
              <p className="text-slate-600">Select exceptions from the dashboard to perform batch operations.</p>
            </div>
            <Button variant="outline" onClick={onClose}>
              Return to Dashboard
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-100">
              <Layers className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Batch Resolution</h1>
              <p className="text-slate-600">Process {selectedExceptions.length} exceptions in bulk</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={onClose}>
            <X className="w-4 h-4 mr-2" />
            Close
          </Button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Total Exceptions</p>
                <div className="text-2xl font-bold">{stats.total}</div>
              </div>
              <FileText className="w-4 h-4 text-slate-400" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Reason Groups</p>
                <div className="text-2xl font-bold">{Object.keys(stats.byReason).length}</div>
              </div>
              <Target className="w-4 h-4 text-slate-400" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Avg Confidence</p>
                <div className="text-2xl font-bold">{Math.round(stats.avgConfidence * 100)}%</div>
              </div>
              <TrendingUp className="w-4 h-4 text-slate-400" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Status</p>
                <div className="text-lg font-bold">
                  {isProcessing ? (
                    <span className="text-blue-600">Processing</span>
                  ) : processingResults ? (
                    <span className="text-green-600">Completed</span>
                  ) : (
                    <span className="text-slate-600">Ready</span>
                  )}
                </div>
              </div>
              {isProcessing ? (
                <Clock className="w-4 h-4 text-blue-600 animate-spin" />
              ) : processingResults ? (
                <CheckCircle2 className="w-4 h-4 text-green-600" />
              ) : (
                <Play className="w-4 h-4 text-slate-400" />
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Processing Progress */}
      {isProcessing && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Processing exceptions...</span>
                <span className="text-sm text-slate-600">{Math.round(processingProgress)}%</span>
              </div>
              <Progress value={processingProgress} className="h-2" />
              <p className="text-xs text-slate-500">
                This may take a few moments. Please don't close this window.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Processing Results */}
      {processingResults && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-600" />
              Processing Complete
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-medium text-green-600 mb-2">
                  Successfully Resolved ({processingResults.resolved?.length || 0})
                </h4>
                <div className="space-y-1">
                  {processingResults.resolved?.slice(0, 5).map((id: string, index: number) => (
                    <div key={index} className="text-sm text-slate-600">
                      ✓ Exception {id.slice(0, 8)}...
                    </div>
                  ))}
                  {(processingResults.resolved?.length || 0) > 5 && (
                    <div className="text-sm text-slate-500">
                      ...and {(processingResults.resolved?.length || 0) - 5} more
                    </div>
                  )}
                </div>
              </div>

              {processingResults.failed?.length > 0 && (
                <div>
                  <h4 className="font-medium text-red-600 mb-2">
                    Failed ({processingResults.failed?.length || 0})
                  </h4>
                  <div className="space-y-1">
                    {processingResults.failed?.slice(0, 5).map((item: any, index: number) => (
                      <div key={index} className="text-sm text-slate-600">
                        ✗ Exception {item.id?.slice(0, 8)}... - {item.error || 'Unknown error'}
                      </div>
                    ))}
                    {(processingResults.failed?.length || 0) > 5 && (
                      <div className="text-sm text-slate-500">
                        ...and {(processingResults.failed?.length || 0) - 5} more
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
            <div className="flex gap-3 mt-6">
              <Button onClick={onClose}>
                Return to Dashboard
              </Button>
              <Button variant="outline">
                <Download className="w-4 h-4 mr-2" />
                Export Results
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Content */}
      {!isProcessing && !processingResults && (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="similar">Similar Exceptions</TabsTrigger>
            <TabsTrigger value="resolution">Resolution Settings</TabsTrigger>
            <TabsTrigger value="preview">Preview & Confirm</TabsTrigger>
          </TabsList>

          {/* Similar Exceptions Tab */}
          <TabsContent value="similar" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Exception Groups */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Layers className="w-5 h-5" />
                    Exception Groups
                  </CardTitle>
                  <CardDescription>
                    Exceptions grouped by reason and severity for efficient batch processing
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {similarGroups.map((group: any, index: number) => (
                    <div key={index} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <h4 className="font-medium">{group.title}</h4>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge className={getSeverityColor(group.severity)} variant="outline">
                              {group.severity}
                            </Badge>
                            <Badge variant="secondary" className="text-xs">
                              {group.exceptions.length} exceptions
                            </Badge>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-medium">
                            {Math.round(group.confidence * 100)}% avg confidence
                          </div>
                        </div>
                      </div>

                      <Accordion type="single" collapsible className="w-full">
                        <AccordionItem value={`group-${index}`} className="border-none">
                          <AccordionTrigger className="py-2 text-xs">
                            View exceptions ({group.exceptions.length})
                          </AccordionTrigger>
                          <AccordionContent>
                            <div className="space-y-2">
                              {group.exceptions.slice(0, 3).map((exception: any, exIndex: number) => (
                                <div key={exIndex} className="text-xs p-2 bg-slate-50 rounded">
                                  <div className="flex items-center justify-between">
                                    <span className="font-medium">{exception.title}</span>
                                    <Badge variant="outline" className="text-xs">
                                      {exception.status.replace(/_/g, " ")}
                                    </Badge>
                                  </div>
                                  <div className="text-slate-600 mt-1">
                                    Invoice: {exception.invoice_number || "N/A"}
                                  </div>
                                </div>
                              ))}
                              {group.exceptions.length > 3 && (
                                <div className="text-xs text-slate-500 text-center">
                                  ...and {group.exceptions.length - 3} more
                                </div>
                              )}
                            </div>
                          </AccordionContent>
                        </AccordionItem>
                      </Accordion>
                    </div>
                  ))}
                </CardContent>
              </Card>

              {/* Reason Breakdown */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="w-5 h-5" />
                    Breakdown Analysis
                  </CardTitle>
                  <CardDescription>
                    Detailed breakdown of selected exceptions by category
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* By Reason Code */}
                  <div>
                    <h4 className="font-medium mb-3">By Reason Code</h4>
                    <div className="space-y-2">
                      {Object.entries(stats.byReason).map(([reason, count]) => (
                        <div key={reason} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 bg-blue-500 rounded-full" />
                            <span className="text-sm">
                              {getExceptionReasonDescription(reason as any)}
                            </span>
                          </div>
                          <Badge variant="secondary">{count}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>

                  <Separator />

                  {/* By Severity */}
                  <div>
                    <h4 className="font-medium mb-3">By Severity</h4>
                    <div className="space-y-2">
                      {Object.entries(stats.bySeverity).map(([severity, count]) => (
                        <div key={severity} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className={cn(
                              "w-2 h-2 rounded-full",
                              severity === "critical" ? "bg-red-500" :
                              severity === "high" ? "bg-orange-500" :
                              severity === "medium" ? "bg-yellow-500" : "bg-blue-500"
                            )} />
                            <span className="text-sm capitalize">{severity}</span>
                          </div>
                          <Badge className={getSeverityColor(severity as any)}>{count}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>

                  <Separator />

                  {/* Quick Actions */}
                  <div>
                    <h4 className="font-medium mb-3">Suggested Actions</h4>
                    <div className="space-y-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="w-full justify-start"
                        onClick={() => setResolutionMethod("manual_correction")}
                      >
                        <Edit className="w-4 h-4 mr-2" />
                        Manual Correction (Recommended)
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="w-full justify-start"
                        onClick={() => setResolutionMethod("system_reprocess")}
                      >
                        <RotateCcw className="w-4 h-4 mr-2" />
                        Reprocess Documents
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="w-full justify-start"
                        onClick={() => setResolutionMethod("vendor_contact")}
                      >
                        <Users className="w-4 h-4 mr-2" />
                        Contact Vendors
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Resolution Settings Tab */}
          <TabsContent value="resolution" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Resolution Method */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Settings className="w-5 h-5" />
                    Resolution Method
                  </CardTitle>
                  <CardDescription>
                    Choose how to resolve all selected exceptions
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {resolutionMethods.map((method) => (
                    <div
                      key={method.value}
                      className={cn(
                        "p-4 border rounded-lg cursor-pointer transition-colors",
                        resolutionMethod === method.value
                          ? "border-blue-500 bg-blue-50"
                          : "border-slate-200 hover:border-slate-300"
                      )}
                      onClick={() => setResolutionMethod(method.value)}
                    >
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          "w-4 h-4 rounded-full border-2",
                          resolutionMethod === method.value
                            ? "border-blue-500 bg-blue-500"
                            : "border-slate-300"
                        )}>
                          {resolutionMethod === method.value && (
                            <div className="w-full h-full rounded-full bg-white scale-50" />
                          )}
                        </div>
                        <div className="flex-1">
                          <h4 className="font-medium">{method.label}</h4>
                          <p className="text-sm text-slate-600">{method.description}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              {/* Assignment & Tags */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <User className="w-5 h-5" />
                    Assignment & Tags
                  </CardTitle>
                  <CardDescription>
                    Optional assignment and categorization
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Assignment */}
                  <div>
                    <Label className="text-sm font-medium">Assign To (Optional)</Label>
                    <Select value={assignedTo} onValueChange={setAssignedTo}>
                      <SelectTrigger className="mt-1">
                        <User className="w-4 h-4 mr-2" />
                        <SelectValue placeholder="Select team member" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="">No assignment</SelectItem>
                        {teamMembers.map((member) => (
                          <SelectItem key={member.id} value={member.id}>
                            {member.name} - {member.role}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Tags */}
                  <div>
                    <Label className="text-sm font-medium">Tags (Optional)</Label>
                    <div className="mt-2 space-y-2">
                      <div className="flex gap-2">
                        <Input
                          placeholder="Add tag..."
                          value={tagInput}
                          onChange={(e) => setTagInput(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && handleAddTag()}
                          className="flex-1"
                        />
                        <Button size="sm" onClick={handleAddTag}>
                          Add
                        </Button>
                      </div>
                      {tags.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {tags.map((tag, index) => (
                            <Badge key={index} variant="secondary" className="text-xs">
                              {tag}
                              <button
                                onClick={() => handleRemoveTag(tag)}
                                className="ml-1 hover:text-red-600"
                              >
                                ×
                              </button>
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Resolution Notes */}
                  <div>
                    <Label className="text-sm font-medium">Resolution Notes</Label>
                    <Textarea
                      placeholder="Add notes explaining the batch resolution..."
                      value={resolutionNotes}
                      onChange={(e) => setResolutionNotes(e.target.value)}
                      rows={4}
                      className="mt-1"
                    />
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Processing Options */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="w-5 h-5" />
                  Processing Options
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center space-x-2">
                  <Checkbox id="notify-assignees" />
                  <Label htmlFor="notify-assignees" className="text-sm">
                    Notify assignees when resolution is complete
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox id="create-follow-up" />
                  <Label htmlFor="create-follow-up" className="text-sm">
                    Create follow-up tasks for failed resolutions
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox id="update-vendor" defaultChecked />
                  <Label htmlFor="update-vendor" className="text-sm">
                    Update vendor records with corrected information
                  </Label>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Preview & Confirm Tab */}
          <TabsContent value="preview" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Eye className="w-5 h-5" />
                  Preview & Confirm
                </CardTitle>
                <CardDescription>
                  Review your batch resolution settings before processing
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Summary */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-4 bg-blue-50 rounded-lg">
                    <h4 className="font-medium text-blue-900">Resolution Method</h4>
                    <p className="text-sm text-blue-700 mt-1">
                      {resolutionMethods.find(m => m.value === resolutionMethod)?.label || "Not selected"}
                    </p>
                  </div>
                  <div className="p-4 bg-green-50 rounded-lg">
                    <h4 className="font-medium text-green-900">Exceptions to Process</h4>
                    <p className="text-sm text-green-700 mt-1">{selectedExceptions.length} exceptions</p>
                  </div>
                  <div className="p-4 bg-purple-50 rounded-lg">
                    <h4 className="font-medium text-purple-900">Assignment</h4>
                    <p className="text-sm text-purple-700 mt-1">
                      {assignedTo ? teamMembers.find(m => m.id === assignedTo)?.name : "No assignment"}
                    </p>
                  </div>
                </div>

                {/* Exception List Preview */}
                <div>
                  <h4 className="font-medium mb-3">Exceptions to Process</h4>
                  <div className="border rounded-lg max-h-64 overflow-y-auto">
                    <table className="w-full">
                      <thead className="bg-slate-50">
                        <tr>
                          <th className="text-left p-3 text-sm font-medium">Exception</th>
                          <th className="text-left p-3 text-sm font-medium">Reason</th>
                          <th className="text-left p-3 text-sm font-medium">Severity</th>
                          <th className="text-left p-3 text-sm font-medium">Confidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedExceptionDetails.slice(0, 10).map((exception) => (
                          <tr key={exception.id} className="border-t">
                            <td className="p-3 text-sm">{exception.title}</td>
                            <td className="p-3 text-sm">{exception.reason_code.replace(/_/g, " ")}</td>
                            <td className="p-3">
                              <Badge className={getSeverityColor(exception.severity)} variant="outline">
                                {exception.severity}
                              </Badge>
                            </td>
                            <td className="p-3 text-sm">{Math.round(exception.overall_confidence * 100)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {selectedExceptionDetails.length > 10 && (
                      <div className="p-3 text-center text-sm text-slate-500 border-t">
                        ...and {selectedExceptionDetails.length - 10} more exceptions
                      </div>
                    )}
                  </div>
                </div>

                {/* Confirmation */}
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5" />
                    <div>
                      <h4 className="font-medium text-amber-900">Confirmation Required</h4>
                      <p className="text-sm text-amber-700 mt-1">
                        You are about to process {selectedExceptions.length} exceptions using "{resolutionMethods.find(m => m.value === resolutionMethod)?.label}".
                        This action will modify the selected exceptions and cannot be easily undone.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-3">
                  <Button
                    onClick={() => setActiveTab("resolution")}
                    variant="outline"
                  >
                    Back to Settings
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        size="lg"
                        disabled={!resolutionMethod || batchLoading}
                        className="flex-1"
                      >
                        <Zap className="w-4 h-4 mr-2" />
                        Process {selectedExceptions.length} Exceptions
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Confirm Batch Processing</AlertDialogTitle>
                        <AlertDialogDescription>
                          This will immediately process {selectedExceptions.length} exceptions using the selected resolution method.
                          Are you sure you want to continue?
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleProcessBatch}>
                          Process Exceptions
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}