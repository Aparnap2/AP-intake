"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
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
  AlertCircle,
  CheckCircle2,
  Clock,
  Eye,
  Edit,
  Save,
  X,
  FileText,
  User,
  Calendar,
  TrendingUp,
  AlertTriangle,
  Flag,
  Download,
  Share2,
  MessageSquare,
  History,
  Settings,
  RefreshCw,
  ExternalLink,
  Copy,
  Mail,
  Phone,
  ChevronRight,
  Info,
  Lightbulb
} from "lucide-react"
import { cn } from "@/lib/utils"
import { ConfidenceMeter, FieldConfidenceMeter } from "./ConfidenceMeter"
import { getSeverityColor, getStatusColor, getExceptionReasonDescription } from "@/lib/exception-types"
import { useException, useExceptionSuggestions } from "@/hooks/useExceptions"

interface ExceptionReviewProps {
  exceptionId: string
  onClose?: () => void
  onExceptionUpdate?: (exception: any) => void
}

export function ExceptionReview({ exceptionId, onClose, onExceptionUpdate }: ExceptionReviewProps) {
  const {
    exception,
    loading,
    error,
    updateException,
    assignException,
    resolveException,
    escalateException,
    closeException,
    refresh
  } = useException(exceptionId)

  const { suggestions, loading: suggestionsLoading } = useExceptionSuggestions(exceptionId)

  const [activeTab, setActiveTab] = useState("details")
  const [isEditing, setIsEditing] = useState(false)
  const [editedFields, setEditedFields] = useState<Record<string, any>>({})
  const [resolutionNotes, setResolutionNotes] = useState("")
  const [selectedResolutionMethod, setSelectedResolutionMethod] = useState("")
  const [selectedAssignee, setSelectedAssignee] = useState("")
  const [showResolveDialog, setShowResolveDialog] = useState(false)
  const [showEscalateDialog, setShowEscalateDialog] = useState(false)

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

  useEffect(() => {
    if (exception) {
      setEditedFields({})
      setResolutionNotes("")
      setSelectedResolutionMethod("")
      setSelectedAssignee(exception.assigned_to || "")
    }
  }, [exception])

  const handleFieldEdit = (field: string, value: any) => {
    setEditedFields(prev => ({ ...prev, [field]: value }))
  }

  const handleSaveEdits = async () => {
    if (!exception) return

    try {
      await updateException({
        ...editedFields,
        resolution_notes: "Field values manually corrected"
      })
      setIsEditing(false)
      setEditedFields({})
      refresh()
      onExceptionUpdate?.(exception)
    } catch (error) {
      console.error('Failed to save edits:', error)
    }
  }

  const handleResolve = async () => {
    if (!exception || !selectedResolutionMethod) return

    try {
      await resolveException(selectedResolutionMethod, resolutionNotes)
      setShowResolveDialog(false)
      refresh()
      onExceptionUpdate?.(exception)
    } catch (error) {
      console.error('Failed to resolve exception:', error)
    }
  }

  const handleAssign = async () => {
    if (!exception || !selectedAssignee) return

    try {
      await assignException(selectedAssignee)
      refresh()
      onExceptionUpdate?.(exception)
    } catch (error) {
      console.error('Failed to assign exception:', error)
    }
  }

  const handleEscalate = async (reason: string) => {
    if (!exception) return

    try {
      await escalateException(reason)
      setShowEscalateDialog(false)
      refresh()
      onExceptionUpdate?.(exception)
    } catch (error) {
      console.error('Failed to escalate exception:', error)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="text-center space-y-4">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-blue-600" />
          <p className="text-slate-600">Loading exception details...</p>
        </div>
      </div>
    )
  }

  if (error || !exception) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="text-center space-y-4">
          <AlertTriangle className="w-12 h-12 text-red-600 mx-auto" />
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Error</h3>
            <p className="text-slate-600">{error || "Exception not found"}</p>
          </div>
          <Button variant="outline" onClick={onClose}>
            Go Back
          </Button>
        </div>
      </div>
    )
  }

  const isResolved = exception.status === "resolved" || exception.status === "closed"
  const needsAction = exception.status === "open" || exception.status === "in_progress"

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className={cn("p-2 rounded-lg", getSeverityColor(exception.severity))}>
              <AlertCircle className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">{exception.title}</h1>
              <p className="text-slate-600">{exception.description}</p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={refresh}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline" onClick={onClose}>
            <X className="w-4 h-4 mr-2" />
            Close
          </Button>
        </div>
      </div>

      {/* Status and Metadata */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Status</p>
                <Badge className={getStatusColor(exception.status)} mt-1}>
                  {exception.status.replace(/_/g, " ")}
                </Badge>
              </div>
              <Clock className="w-4 h-4 text-slate-400" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Severity</p>
                <Badge className={getSeverityColor(exception.severity)} mt-1>
                  {exception.severity}
                </Badge>
              </div>
              <Flag className="w-4 h-4 text-slate-400" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Confidence</p>
                <div className="mt-1">
                  <ConfidenceMeter
                    confidence={exception.overall_confidence}
                    threshold={exception.min_confidence_threshold}
                    size="sm"
                  />
                </div>
              </div>
              <TrendingUp className="w-4 h-4 text-slate-400" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Assigned To</p>
                <p className="text-sm text-slate-900 mt-1">
                  {exception.assigned_to || "Unassigned"}
                </p>
              </div>
              <User className="w-4 h-4 text-slate-400" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="details">Exception Details</TabsTrigger>
          <TabsTrigger value="invoice">Invoice Data</TabsTrigger>
          <TabsTrigger value="confidence">Confidence Analysis</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
          <TabsTrigger value="actions">Actions</TabsTrigger>
        </TabsList>

        {/* Exception Details Tab */}
        <TabsContent value="details" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Exception Information */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Info className="w-5 h-5" />
                  Exception Information
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="text-sm font-medium text-slate-600">Reason Code</Label>
                  <div className="mt-1">
                    <Badge variant="outline" className="text-xs">
                      {exception.reason_code.replace(/_/g, " ").toUpperCase()}
                    </Badge>
                  </div>
                  <p className="text-sm text-slate-600 mt-1">
                    {getExceptionReasonDescription(exception.reason_code)}
                  </p>
                </div>

                <div>
                  <Label className="text-sm font-medium text-slate-600">Description</Label>
                  <p className="text-sm text-slate-900 mt-1">{exception.description}</p>
                </div>

                <div>
                  <Label className="text-sm font-medium text-slate-600">Created</Label>
                  <p className="text-sm text-slate-900 mt-1">
                    {new Date(exception.created_at).toLocaleString()}
                  </p>
                </div>

                {exception.updated_at !== exception.created_at && (
                  <div>
                    <Label className="text-sm font-medium text-slate-600">Last Updated</Label>
                    <p className="text-sm text-slate-900 mt-1">
                      {new Date(exception.updated_at).toLocaleString()}
                    </p>
                  </div>
                )}

                {exception.resolved_at && (
                  <div>
                    <Label className="text-sm font-medium text-slate-600">Resolved</Label>
                    <p className="text-sm text-slate-900 mt-1">
                      {new Date(exception.resolved_at).toLocaleString()}
                    </p>
                    <p className="text-sm text-slate-600 mt-1">
                      by {exception.resolved_by}
                    </p>
                  </div>
                )}

                {exception.tags && exception.tags.length > 0 && (
                  <div>
                    <Label className="text-sm font-medium text-slate-600">Tags</Label>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {exception.tags.map((tag, index) => (
                        <Badge key={index} variant="secondary" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Affected Fields */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5" />
                  Affected Fields
                </CardTitle>
              </CardHeader>
              <CardContent>
                {exception.affected_fields && exception.affected_fields.length > 0 ? (
                  <div className="space-y-3">
                    {exception.affected_fields.map((field, index) => (
                      <div key={index} className="border rounded-lg p-3">
                        <div className="flex items-center justify-between mb-2">
                          <Label className="text-sm font-medium">{field.field_name}</Label>
                          {field.confidence_score && (
                            <ConfidenceMeter
                              confidence={field.confidence_score}
                              size="sm"
                              showLabel={false}
                            />
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          <div>
                            <span className="text-slate-600">Current: </span>
                            <span className="font-medium">{field.current_value || "N/A"}</span>
                          </div>
                          {field.expected_value && (
                            <div>
                              <span className="text-slate-600">Expected: </span>
                              <span className="font-medium text-green-600">{field.expected_value}</span>
                            </div>
                          )}
                        </div>
                        {field.validation_error && (
                          <p className="text-xs text-red-600 mt-1">{field.validation_error}</p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">No specific fields affected</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Suggestions */}
          {suggestions && suggestions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Lightbulb className="w-5 h-5" />
                  Suggested Actions
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {suggestions.map((suggestion, index) => (
                    <div key={index} className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg">
                      <ChevronRight className="w-4 h-4 text-blue-600 mt-0.5" />
                      <p className="text-sm text-blue-900">{suggestion}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Invoice Data Tab */}
        <TabsContent value="invoice" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Invoice Details */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="w-5 h-5" />
                  Invoice Information
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="text-sm font-medium text-slate-600">Invoice Number</Label>
                  <Input
                    value={editedFields.invoice_number ?? exception.invoice_number ?? ""}
                    onChange={(e) => handleFieldEdit("invoice_number", e.target.value)}
                    disabled={!isEditing}
                    className="mt-1"
                  />
                </div>

                <div>
                  <Label className="text-sm font-medium text-slate-600">Vendor Name</Label>
                  <Input
                    value={editedFields.vendor_name ?? exception.vendor_name ?? ""}
                    onChange={(e) => handleFieldEdit("vendor_name", e.target.value)}
                    disabled={!isEditing}
                    className="mt-1"
                  />
                </div>

                <div>
                  <Label className="text-sm font-medium text-slate-600">Total Amount</Label>
                  <Input
                    type="number"
                    value={editedFields.total_amount ?? exception.total_amount ?? ""}
                    onChange={(e) => handleFieldEdit("total_amount", parseFloat(e.target.value))}
                    disabled={!isEditing}
                    className="mt-1"
                  />
                </div>

                <div className="flex gap-2">
                  {isEditing ? (
                    <>
                      <Button size="sm" onClick={handleSaveEdits}>
                        <Save className="w-4 h-4 mr-2" />
                        Save Changes
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setIsEditing(false)}>
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <Button size="sm" variant="outline" onClick={() => setIsEditing(true)}>
                      <Edit className="w-4 h-4 mr-2" />
                      Edit Fields
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Document Preview */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Eye className="w-5 h-5" />
                  Document Preview
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="aspect-[8.5/11] bg-slate-100 rounded-lg flex items-center justify-center">
                  <div className="text-center space-y-4">
                    <FileText className="w-12 h-12 text-slate-400 mx-auto" />
                    <div>
                      <p className="text-sm font-medium text-slate-900">Invoice Document</p>
                      <p className="text-xs text-slate-600">Click to view full document</p>
                    </div>
                    <Button size="sm" variant="outline">
                      <ExternalLink className="w-4 h-4 mr-2" />
                      Open Document
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Confidence Analysis Tab */}
        <TabsContent value="confidence" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5" />
                Confidence Analysis
              </CardTitle>
              <CardDescription>
                Detailed breakdown of extraction confidence scores
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Overall Confidence */}
              <div>
                <Label className="text-base font-medium">Overall Confidence</Label>
                <div className="mt-2">
                  <ConfidenceMeter
                    confidence={exception.overall_confidence}
                    threshold={exception.min_confidence_threshold}
                    size="lg"
                    showThreshold={true}
                  />
                </div>
                <p className="text-sm text-slate-600 mt-2">
                  {exception.overall_confidence >= exception.min_confidence_threshold
                    ? "Confidence is above the minimum threshold for automatic processing."
                    : "Confidence is below the minimum threshold, requiring human review."}
                </p>
              </div>

              <Separator />

              {/* Field-level Confidence */}
              <div>
                <Label className="text-base font-medium">Field-Level Confidence</Label>
                <div className="mt-3 space-y-2">
                  {exception.affected_fields?.map((field, index) => (
                    <FieldConfidenceMeter
                      key={index}
                      fieldName={field.field_name}
                      confidence={field.confidence_score || 0}
                      threshold={exception.min_confidence_threshold}
                    />
                  )) || (
                    <p className="text-sm text-slate-500">No field-level confidence data available</p>
                  )}
                </div>
              </div>

              <Separator />

              {/* Confidence Guidelines */}
              <div>
                <Label className="text-base font-medium">Confidence Guidelines</Label>
                <div className="mt-3 space-y-2">
                  <div className="flex items-center gap-3 p-3 bg-green-50 rounded-lg">
                    <CheckCircle2 className="w-5 h-5 text-green-600" />
                    <div>
                      <p className="text-sm font-medium text-green-900">95% - 100%: Excellent</p>
                      <p className="text-xs text-green-700">High confidence, suitable for automatic processing</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
                    <Info className="w-5 h-5 text-blue-600" />
                    <div>
                      <p className="text-sm font-medium text-blue-900">80% - 94%: Good</p>
                      <p className="text-xs text-blue-700">Generally reliable, minimal verification needed</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 p-3 bg-yellow-50 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-yellow-600" />
                    <div>
                      <p className="text-sm font-medium text-yellow-900">60% - 79%: Fair</p>
                      <p className="text-xs text-yellow-700">Requires human verification and correction</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 p-3 bg-red-50 rounded-lg">
                    <AlertCircle className="w-5 h-5 text-red-600" />
                    <div>
                      <p className="text-sm font-medium text-red-900">Below 60%: Poor</p>
                      <p className="text-xs text-red-700">Manual data entry recommended</p>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="w-5 h-5" />
                Exception History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {/* Created */}
                <div className="flex items-start gap-4">
                  <div className="w-2 h-2 bg-blue-600 rounded-full mt-2" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">Exception Created</span>
                      <Badge variant="outline" className="text-xs">
                        {new Date(exception.created_at).toLocaleDateString()}
                      </Badge>
                    </div>
                    <p className="text-sm text-slate-600 mt-1">
                      Exception was automatically created during invoice processing due to {exception.reason_code.replace(/_/g, " ")}.
                    </p>
                  </div>
                </div>

                {/* Assigned */}
                {exception.assigned_to && (
                  <div className="flex items-start gap-4">
                    <div className="w-2 h-2 bg-yellow-600 rounded-full mt-2" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">Assigned to {exception.assigned_to}</span>
                        <Badge variant="outline" className="text-xs">
                          Pending Review
                        </Badge>
                      </div>
                      <p className="text-sm text-slate-600 mt-1">
                        Exception assigned for manual review and resolution.
                      </p>
                    </div>
                  </div>
                )}

                {/* In Progress */}
                {exception.status === "in_progress" && (
                  <div className="flex items-start gap-4">
                    <div className="w-2 h-2 bg-orange-600 rounded-full mt-2" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">Review in Progress</span>
                        <Badge variant="outline" className="text-xs">
                          In Progress
                        </Badge>
                      </div>
                      <p className="text-sm text-slate-600 mt-1">
                        Exception is currently being reviewed by the assigned team member.
                      </p>
                    </div>
                  </div>
                )}

                {/* Resolved */}
                {exception.resolved_at && (
                  <div className="flex items-start gap-4">
                    <div className="w-2 h-2 bg-green-600 rounded-full mt-2" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">Exception Resolved</span>
                        <Badge className="bg-green-100 text-green-800 border-green-200 text-xs">
                          Resolved
                        </Badge>
                      </div>
                      <p className="text-sm text-slate-600 mt-1">
                        Exception was resolved using {exception.resolution_method?.replace(/_/g, " ")}.
                      </p>
                      {exception.resolution_notes && (
                        <p className="text-sm text-slate-600 mt-1 italic">
                          Note: {exception.resolution_notes}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Actions Tab */}
        <TabsContent value="actions" className="space-y-6">
          {needsAction && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Quick Actions */}
              <Card>
                <CardHeader>
                  <CardTitle>Quick Actions</CardTitle>
                  <CardDescription>
                    Common actions for resolving exceptions
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Button
                    className="w-full justify-start"
                    variant="outline"
                    onClick={() => setShowResolveDialog(true)}
                  >
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Resolve Exception
                  </Button>

                  <Select value={selectedAssignee} onValueChange={setSelectedAssignee}>
                    <SelectTrigger className="w-full">
                      <User className="w-4 h-4 mr-2" />
                      <SelectValue placeholder="Assign to team member" />
                    </SelectTrigger>
                    <SelectContent>
                      {teamMembers.map((member) => (
                        <SelectItem key={member.id} value={member.id}>
                          {member.name} - {member.role}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {selectedAssignee && selectedAssignee !== exception.assigned_to && (
                    <Button
                      className="w-full"
                      onClick={handleAssign}
                      disabled={!selectedAssignee}
                    >
                      Assign Exception
                    </Button>
                  )}

                  <Button
                    className="w-full justify-start"
                    variant="outline"
                    onClick={() => setShowEscalateDialog(true)}
                  >
                    <AlertTriangle className="w-4 h-4 mr-2" />
                    Escalate Exception
                  </Button>

                  <Button
                    className="w-full justify-start"
                    variant="outline"
                  >
                    <Mail className="w-4 h-4 mr-2" />
                    Contact Vendor
                  </Button>
                </CardContent>
              </Card>

              {/* Resolution Method */}
              <Card>
                <CardHeader>
                  <CardTitle>Resolution Method</CardTitle>
                  <CardDescription>
                    Choose how to resolve this exception
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {resolutionMethods.map((method) => (
                    <div
                      key={method.value}
                      className={cn(
                        "p-3 border rounded-lg cursor-pointer transition-colors",
                        selectedResolutionMethod === method.value
                          ? "border-blue-500 bg-blue-50"
                          : "border-slate-200 hover:border-slate-300"
                      )}
                      onClick={() => setSelectedResolutionMethod(method.value)}
                    >
                      <div className="flex items-center gap-2">
                        <div className={cn(
                          "w-3 h-3 rounded-full border-2",
                          selectedResolutionMethod === method.value
                            ? "border-blue-500 bg-blue-500"
                            : "border-slate-300"
                        )} />
                        <span className="font-medium text-sm">{method.label}</span>
                      </div>
                      <p className="text-xs text-slate-600 mt-1 ml-5">
                        {method.description}
                      </p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          )}

          {/* Resolution Notes */}
          {needsAction && (
            <Card>
              <CardHeader>
                <CardTitle>Resolution Notes</CardTitle>
                <CardDescription>
                  Add notes explaining how this exception was resolved
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Textarea
                  placeholder="Describe how you resolved this exception..."
                  value={resolutionNotes}
                  onChange={(e) => setResolutionNotes(e.target.value)}
                  rows={4}
                />
                <Button
                  onClick={handleResolve}
                  disabled={!selectedResolutionMethod || !resolutionNotes.trim()}
                  className="w-full"
                >
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Resolve Exception
                </Button>
              </CardContent>
            </Card>
          )}

          {isResolved && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                  Exception Resolved
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="text-sm font-medium text-slate-600">Resolution Method</Label>
                  <p className="text-sm text-slate-900 mt-1">
                    {exception.resolution_method?.replace(/_/g, " ") || "N/A"}
                  </p>
                </div>
                {exception.resolution_notes && (
                  <div>
                    <Label className="text-sm font-medium text-slate-600">Resolution Notes</Label>
                    <p className="text-sm text-slate-900 mt-1">{exception.resolution_notes}</p>
                  </div>
                )}
                <div>
                  <Label className="text-sm font-medium text-slate-600">Resolved By</Label>
                  <p className="text-sm text-slate-900 mt-1">
                    {exception.resolved_by} on {new Date(exception.resolved_at!).toLocaleString()}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* Resolve Dialog */}
      <Dialog open={showResolveDialog} onOpenChange={setShowResolveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Resolve Exception</DialogTitle>
            <DialogDescription>
              Confirm the resolution details for this exception.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Resolution Method</Label>
              <Select value={selectedResolutionMethod} onValueChange={setSelectedResolutionMethod}>
                <SelectTrigger>
                  <SelectValue placeholder="Select resolution method" />
                </SelectTrigger>
                <SelectContent>
                  {resolutionMethods.map((method) => (
                    <SelectItem key={method.value} value={method.value}>
                      {method.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Resolution Notes</Label>
              <Textarea
                placeholder="Describe how you resolved this exception..."
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <div className="flex gap-3">
            <Button
              onClick={handleResolve}
              disabled={!selectedResolutionMethod || !resolutionNotes.trim()}
            >
              Resolve Exception
            </Button>
            <Button variant="outline" onClick={() => setShowResolveDialog(false)}>
              Cancel
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Escalate Dialog */}
      <Dialog open={showEscalateDialog} onOpenChange={setShowEscalateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Escalate Exception</DialogTitle>
            <DialogDescription>
              Escalate this exception to a senior team member for review.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Escalation Reason</Label>
              <Textarea
                placeholder="Explain why this exception needs escalation..."
                rows={3}
              />
            </div>
          </div>
          <div className="flex gap-3">
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">
                  <AlertTriangle className="w-4 h-4 mr-2" />
                  Escalate Exception
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Confirm Escalation</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will escalate the exception to senior management. Are you sure?
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={() => handleEscalate("Requires senior review")}>
                    Escalate
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
            <Button variant="outline" onClick={() => setShowEscalateDialog(false)}>
              Cancel
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}