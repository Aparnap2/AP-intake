"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Progress } from "@/components/ui/progress"
import {
  FileText,
  AlertCircle,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Eye,
  Edit,
  Save,
  X,
  Download,
  Upload,
  Search,
  Filter,
  ChevronRight,
  Calendar,
  DollarSign,
  Building,
  Package,
  Truck,
  User,
  Settings,
  RefreshCw,
  CheckSquare,
  Square,
  MoreHorizontal,
  MessageSquare,
  Send,
  Paperclip,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Maximize2,
  Minimize2
} from "lucide-react"
import { cn } from "@/lib/utils"

// Types for our invoice data
interface InvoiceField {
  value: string | number
  confidence: number
  status: "validated" | "needs_review" | "error"
  editable?: boolean
  suggestions?: string[]
}

interface LineItem {
  id: string
  description: string
  quantity: number
  unitPrice: number
  amount: number
  confidence: number
  status: "validated" | "needs_review" | "error"
  taxCode?: string
  accountCode?: string
}

interface ValidationIssue {
  id: string
  field: string
  severity: "error" | "warning" | "info"
  message: string
  suggestedFix?: string
  autoFixable?: boolean
}

interface Invoice {
  id: string
  documentId: string
  filename: string
  uploadedAt: string
  status: "pending_review" | "approved" | "rejected" | "needs_more_info" | "processing"
  extractedFields: Record<string, InvoiceField>
  lineItems: LineItem[]
  validationIssues: ValidationIssue[]
  overallConfidence: number
  extractionTime: number
  assignedTo?: string
  reviewedBy?: string
  reviewedAt?: string
  comments?: Comment[]
  pdfUrl?: string
}

interface Comment {
  id: string
  author: string
  timestamp: string
  message: string
  type: "comment" | "approval" | "rejection" | "request_info"
}

// Invoice Review Component
export function InvoiceReview({ invoice }: { invoice: Invoice }) {
  const [activeTab, setActiveTab] = useState("summary")
  const [isEditing, setIsEditing] = useState(false)
  const [editedFields, setEditedFields] = useState<Record<string, any>>({})
  const [zoomLevel, setZoomLevel] = useState(1)
  const [selectedItems, setSelectedItems] = useState<string[]>([])
  const [newComment, setNewComment] = useState("")
  const [expandedSections, setExpandedSections] = useState<string[]>(["basic", "vendor", "amounts"])

  const ConfidenceBadge = ({ confidence }: { confidence: number }) => {
    if (confidence >= 0.95)
      return (
        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
          High: {(confidence * 100).toFixed(0)}%
        </Badge>
      )
    if (confidence >= 0.85)
      return (
        <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
          Good: {(confidence * 100).toFixed(0)}%
        </Badge>
      )
    return (
      <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
        Review: {(confidence * 100).toFixed(0)}%
      </Badge>
    )
  }

  const StatusIcon = ({ status }: { status: "validated" | "needs_review" | "error" }) => {
    switch (status) {
      case "validated":
        return <CheckCircle2 className="w-4 h-4 text-green-600" />
      case "error":
        return <AlertCircle className="w-4 h-4 text-red-600" />
      default:
        return <AlertCircle className="w-4 h-4 text-amber-600" />
    }
  }

  const EditableField = ({
    fieldKey,
    field,
    label
  }: {
    fieldKey: string
    field: InvoiceField
    label: string
  }) => {
    const [isFieldEditing, setIsFieldEditing] = useState(false)
    const currentValue = editedFields[fieldKey] ?? field.value

    const handleSave = () => {
      setEditedFields(prev => ({ ...prev, [fieldKey]: currentValue }))
      setIsFieldEditing(false)
    }

    if (isFieldEditing) {
      return (
        <div className="flex items-center gap-2">
          <Input
            value={currentValue}
            onChange={(e) => setEditedFields(prev => ({ ...prev, [fieldKey]: e.target.value }))}
            className="flex-1"
          />
          <Button size="sm" onClick={handleSave}>
            <Save className="w-4 h-4" />
          </Button>
          <Button size="sm" variant="outline" onClick={() => setIsFieldEditing(false)}>
            <X className="w-4 h-4" />
          </Button>
        </div>
      )
    }

    return (
      <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-200">
        <div className="flex items-center gap-3 flex-1">
          <StatusIcon status={field.status} />
          <div className="flex-1">
            <p className="text-sm font-medium text-slate-700">{label}</p>
            <p className="text-base font-semibold text-slate-900">{currentValue}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ConfidenceBadge confidence={field.confidence} />
          {field.editable && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setIsFieldEditing(true)}
            >
              <Edit className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>
    )
  }

  const toggleSection = (section: string) => {
    setExpandedSections(prev =>
      prev.includes(section)
        ? prev.filter(s => s !== section)
        : [...prev, section]
    )
  }

  const toggleItemSelection = (itemId: string) => {
    setSelectedItems(prev =>
      prev.includes(itemId)
        ? prev.filter(id => id !== itemId)
        : [...prev, itemId]
    )
  }

  const addComment = () => {
    if (!newComment.trim()) return

    const comment: Comment = {
      id: Date.now().toString(),
      author: "Current User", // This would come from auth context
      timestamp: new Date().toISOString(),
      message: newComment,
      type: "comment"
    }

    setNewComment("")
    // Here you would save the comment to the backend
  }

  const renderPDFPreview = () => (
    <div className="border rounded-lg bg-white p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-slate-600" />
          <span className="font-medium">{invoice.filename}</span>
        </div>
        <div className="flex items-center gap-1">
          <Button size="sm" variant="outline" onClick={() => setZoomLevel(Math.max(0.5, zoomLevel - 0.25))}>
            <ZoomOut className="w-4 h-4" />
          </Button>
          <span className="text-sm font-mono px-2">{Math.round(zoomLevel * 100)}%</span>
          <Button size="sm" variant="outline" onClick={() => setZoomLevel(Math.min(2, zoomLevel + 0.25))}>
            <ZoomIn className="w-4 h-4" />
          </Button>
          <Button size="sm" variant="outline">
            <Download className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div className="overflow-auto max-h-96 bg-slate-50 rounded">
        <div
          className="bg-white shadow-lg mx-auto"
          style={{
            width: `${210 * zoomLevel}mm`,
            transform: `scale(${zoomLevel})`,
            transformOrigin: 'top center',
            transition: 'transform 0.2s'
          }}
        >
          <div className="p-8 space-y-4">
            {/* Mock PDF content */}
            <div className="text-center space-y-2">
              <h2 className="text-xl font-bold">INVOICE</h2>
              <div className="h-px bg-black"></div>
            </div>

            <div className="grid grid-cols-2 gap-8">
              <div className="space-y-2">
                <p className="text-sm font-semibold">FROM:</p>
                <p className="text-sm">{invoice.extractedFields.vendorName?.value || "Vendor Name"}</p>
                <p className="text-sm">Vendor Address</p>
                <p className="text-sm">City, State ZIP</p>
              </div>
              <div className="text-right space-y-2">
                <p className="text-sm"><strong>Invoice #:</strong> {invoice.extractedFields.invoiceNumber?.value || "N/A"}</p>
                <p className="text-sm"><strong>Date:</strong> {invoice.extractedFields.invoiceDate?.value || "N/A"}</p>
                <p className="text-sm"><strong>Due:</strong> {invoice.extractedFields.dueDate?.value || "N/A"}</p>
                <p className="text-sm"><strong>PO:</strong> {invoice.extractedFields.purchaseOrder?.value || "N/A"}</p>
              </div>
            </div>

            <div className="mt-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left pb-2">Description</th>
                    <th className="text-center pb-2">Qty</th>
                    <th className="text-right pb-2">Price</th>
                    <th className="text-right pb-2">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {invoice.lineItems.map((item, idx) => (
                    <tr key={item.id} className="border-b">
                      <td className="py-2">{item.description}</td>
                      <td className="text-center py-2">{item.quantity}</td>
                      <td className="text-right py-2">${item.unitPrice.toFixed(2)}</td>
                      <td className="text-right py-2">${item.amount.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={3} className="text-right py-2 font-semibold">TOTAL:</td>
                    <td className="text-right py-2 font-bold">
                      {invoice.extractedFields.totalAmount?.value || "$0.00"}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <FileText className="w-8 h-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-slate-900">Invoice Review</h1>
          </div>
          <p className="text-slate-600">
            Document: <span className="font-mono text-sm">{invoice.filename}</span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant={invoice.status === "pending_review" ? "secondary" : "default"}>
            {invoice.status.replace("_", " ")}
          </Badge>
          <div className="text-right">
            <p className="text-2xl font-bold text-slate-900">{invoice.extractedFields.totalAmount?.value || "$0.00"}</p>
            <p className="text-sm text-slate-500">{invoice.extractedFields.currency?.value || "USD"}</p>
          </div>
        </div>
      </div>

      {/* Validation Issues */}
      {invoice.validationIssues.length > 0 && (
        <Alert className="border-amber-200 bg-amber-50">
          <AlertTriangle className="h-4 w-4 text-amber-600" />
          <AlertTitle>Validation Alerts ({invoice.validationIssues.length})</AlertTitle>
          <AlertDescription className="mt-2 space-y-2">
            {invoice.validationIssues.map((issue) => (
              <div key={issue.id} className="flex items-start gap-2 text-sm">
                <span className="text-amber-600 font-semibold min-w-fit">{issue.field}:</span>
                <span className="text-amber-800">{issue.message}</span>
                {issue.suggestedFix && (
                  <Badge variant="outline" className="ml-2 text-xs">
                    {issue.suggestedFix}
                  </Badge>
                )}
              </div>
            ))}
          </AlertDescription>
        </Alert>
      )}

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column - Data Review */}
        <div className="space-y-6">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="summary">Summary</TabsTrigger>
              <TabsTrigger value="detailed">Detailed Fields</TabsTrigger>
              <TabsTrigger value="lineItems">Line Items</TabsTrigger>
            </TabsList>

            <TabsContent value="summary" className="space-y-4">
              <CollapsibleSection
                title="Invoice Details"
                expanded={expandedSections.includes("basic")}
                onToggle={() => toggleSection("basic")}
              >
                <div className="space-y-3">
                  <EditableField
                    fieldKey="invoiceNumber"
                    field={invoice.extractedFields.invoiceNumber!}
                    label="Invoice Number"
                  />
                  <EditableField
                    fieldKey="invoiceDate"
                    field={invoice.extractedFields.invoiceDate!}
                    label="Invoice Date"
                  />
                  <EditableField
                    fieldKey="dueDate"
                    field={invoice.extractedFields.dueDate!}
                    label="Due Date"
                  />
                  <EditableField
                    fieldKey="paymentTerms"
                    field={invoice.extractedFields.paymentTerms!}
                    label="Payment Terms"
                  />
                </div>
              </CollapsibleSection>

              <CollapsibleSection
                title="Vendor Information"
                expanded={expandedSections.includes("vendor")}
                onToggle={() => toggleSection("vendor")}
              >
                <div className="space-y-3">
                  <EditableField
                    fieldKey="vendorName"
                    field={invoice.extractedFields.vendorName!}
                    label="Vendor Name"
                  />
                  <EditableField
                    fieldKey="vendorId"
                    field={invoice.extractedFields.vendorId!}
                    label="Vendor ID"
                  />
                  <EditableField
                    fieldKey="purchaseOrder"
                    field={invoice.extractedFields.purchaseOrder!}
                    label="Purchase Order"
                  />
                </div>
              </CollapsibleSection>

              <CollapsibleSection
                title="Amount Summary"
                expanded={expandedSections.includes("amounts")}
                onToggle={() => toggleSection("amounts")}
              >
                <div className="space-y-3">
                  <div className="flex justify-between items-center p-3 rounded-lg bg-slate-50">
                    <span className="text-slate-600 text-sm">Subtotal</span>
                    <span className="font-semibold">$12,000.00</span>
                  </div>
                  <div className="flex justify-between items-center p-3 rounded-lg bg-slate-50">
                    <span className="text-slate-600 text-sm">Tax</span>
                    <span className="font-semibold">{invoice.extractedFields.taxAmount?.value || "$0.00"}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 rounded-lg bg-blue-50 border border-blue-200">
                    <span className="text-blue-700 font-medium text-sm">Total Amount</span>
                    <span className="text-xl font-bold text-blue-600">
                      {invoice.extractedFields.totalAmount?.value || "$0.00"}
                    </span>
                  </div>
                </div>
              </CollapsibleSection>
            </TabsContent>

            <TabsContent value="detailed" className="space-y-4">
              <div className="space-y-3">
                {Object.entries(invoice.extractedFields).map(([key, field]) => (
                  <EditableField
                    key={key}
                    fieldKey={key}
                    field={field}
                    label={key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}
                  />
                ))}
              </div>
            </TabsContent>

            <TabsContent value="lineItems" className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-semibold">Line Items</h3>
                  <Badge variant="secondary">{invoice.lineItems.length} items</Badge>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setSelectedItems(invoice.lineItems.map(item => item.id))}
                  >
                    <CheckSquare className="w-4 h-4 mr-1" />
                    Select All
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setSelectedItems([])}
                  >
                    <Square className="w-4 h-4 mr-1" />
                    Clear
                  </Button>
                </div>
              </div>

              <div className="space-y-3">
                {invoice.lineItems.map((item) => (
                  <div
                    key={item.id}
                    className={cn(
                      "p-4 rounded-lg border space-y-3 cursor-pointer transition-colors",
                      selectedItems.includes(item.id)
                        ? "bg-blue-50 border-blue-200"
                        : "bg-slate-50 border-slate-200 hover:bg-slate-100"
                    )}
                    onClick={() => toggleItemSelection(item.id)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3 flex-1">
                        <input
                          type="checkbox"
                          checked={selectedItems.includes(item.id)}
                          onChange={() => toggleItemSelection(item.id)}
                          className="mt-1"
                        />
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h4 className="font-semibold text-slate-900">{item.description}</h4>
                            <StatusIcon status={item.status} />
                          </div>
                          <div className="grid grid-cols-4 gap-4 text-sm mt-2">
                            <div>
                              <span className="text-slate-600">Qty:</span>
                              <span className="ml-2 font-mono font-semibold">{item.quantity}</span>
                            </div>
                            <div>
                              <span className="text-slate-600">Unit Price:</span>
                              <span className="ml-2 font-mono font-semibold">${item.unitPrice.toFixed(2)}</span>
                            </div>
                            <div>
                              <span className="text-slate-600">Total:</span>
                              <span className="ml-2 font-mono font-semibold">${item.amount.toFixed(2)}</span>
                            </div>
                            <div>
                              <ConfidenceBadge confidence={item.confidence} />
                            </div>
                          </div>
                          {(item.taxCode || item.accountCode) && (
                            <div className="flex gap-4 text-sm mt-2">
                              {item.taxCode && (
                                <span className="text-slate-600">
                                  Tax Code: <span className="font-mono">{item.taxCode}</span>
                                </span>
                              )}
                              {item.accountCode && (
                                <span className="text-slate-600">
                                  Account: <span className="font-mono">{item.accountCode}</span>
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {/* Right Column - PDF Preview & Comments */}
        <div className="space-y-6">
          {renderPDFPreview()}

          {/* Comments Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="w-5 h-5" />
                Comments & History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-48 mb-4">
                <div className="space-y-3">
                  {invoice.comments?.map((comment) => (
                    <div key={comment.id} className="border-b pb-3">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium text-sm">{comment.author}</span>
                        <span className="text-xs text-slate-500">
                          {new Date(comment.timestamp).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-sm text-slate-700">{comment.message}</p>
                      <Badge variant="outline" className="mt-1 text-xs">
                        {comment.type.replace("_", " ")}
                      </Badge>
                    </div>
                  ))}
                </div>
              </ScrollArea>

              <div className="flex gap-2">
                <Input
                  placeholder="Add a comment..."
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && addComment()}
                />
                <Button size="sm" onClick={addComment}>
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between border-t pt-6">
        <div className="flex gap-3">
          <Button variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            Re-process
          </Button>
          <Button variant="outline">
            <Upload className="w-4 h-4 mr-2" />
            Request Re-upload
          </Button>
        </div>

        <div className="flex gap-3">
          <Button variant="outline">
            <AlertCircle className="w-4 h-4 mr-2" />
            Request More Info
          </Button>
          <Button variant="destructive">
            <X className="w-4 h-4 mr-2" />
            Reject
          </Button>
          <Button className="bg-green-600 hover:bg-green-700">
            <CheckCircle2 className="w-4 h-4 mr-2" />
            Approve & Process
          </Button>
        </div>
      </div>
    </div>
  )
}

// Collapsible Section Component
function CollapsibleSection({
  title,
  expanded,
  onToggle,
  children
}: {
  title: string
  expanded: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <Card>
      <CardHeader
        className="pb-3 cursor-pointer hover:bg-slate-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{title}</CardTitle>
          <ChevronRight
            className={cn(
              "w-4 h-4 transition-transform",
              expanded && "rotate-90"
            )}
          />
        </div>
      </CardHeader>
      {expanded && (
        <CardContent className="pt-0">
          {children}
        </CardContent>
      )}
    </Card>
  )
}