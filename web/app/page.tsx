"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { AlertCircle, CheckCircle2, Clock, FileText, AlertTriangle, Mail } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

// Demo data representing extracted invoice data
const demoIntake = {
  id: "INV-2024-001",
  documentId: "doc_abc123",
  filename: "Invoice_Acme_Corp_2024.pdf",
  uploadedAt: "2024-11-05T14:32:00Z",
  status: "pending_review",
  extractedFields: {
    invoiceNumber: {
      value: "INV-2024-5647",
      confidence: 0.98,
      status: "validated",
    },
    invoiceDate: {
      value: "2024-11-01",
      confidence: 0.97,
      status: "validated",
    },
    dueDate: {
      value: "2024-11-30",
      confidence: 0.96,
      status: "validated",
    },
    vendorName: {
      value: "Acme Corp Manufacturing",
      confidence: 0.94,
      status: "validated",
    },
    vendorId: {
      value: "VENDOR-4521",
      confidence: 0.92,
      status: "needs_review",
    },
    totalAmount: {
      value: "$12,450.50",
      confidence: 0.99,
      status: "validated",
    },
    currency: {
      value: "USD",
      confidence: 1.0,
      status: "validated",
    },
    lineItems: [
      {
        description: "Manufacturing supplies - Q4 batch",
        quantity: 500,
        unitPrice: 24.0,
        amount: 12000.0,
        confidence: 0.95,
        status: "validated",
      },
      {
        description: "Shipping and handling",
        quantity: 1,
        unitPrice: 450.5,
        amount: 450.5,
        confidence: 0.91,
        status: "needs_review",
      },
    ],
    purchaseOrder: {
      value: "PO-2024-0891",
      confidence: 0.89,
      status: "needs_review",
    },
    paymentTerms: {
      value: "Net 30",
      confidence: 0.94,
      status: "validated",
    },
    taxAmount: {
      value: "$0.00",
      confidence: 1.0,
      status: "validated",
    },
  },
  validationIssues: [
    {
      id: "issue_1",
      field: "vendorId",
      severity: "warning",
      message: "Vendor ID not found in master list. Please verify or add new vendor.",
    },
    {
      id: "issue_2",
      field: "purchaseOrder",
      severity: "info",
      message: "PO partially matches existing records. Review recommended.",
    },
  ],
  overallConfidence: 0.95,
  extractionTime: 1240, // milliseconds
}

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

const StatusIcon = ({ status }: { status: "validated" | "needs_review" }) => {
  if (status === "validated") return <CheckCircle2 className="w-4 h-4 text-green-600" />
  return <AlertCircle className="w-4 h-4 text-amber-600" />
}

export default function APIntakeDashboard() {
  const [selectedView, setSelectedView] = useState<"summary" | "detailed" | "lineItems">("summary")

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <FileText className="w-8 h-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-slate-900">AP Intake Review</h1>
          </div>
          <p className="text-slate-600">
            Document: <span className="font-mono text-sm">{demoIntake.filename}</span>
          </p>
        </div>

        {/* Status Banner */}
        <div className="flex items-center justify-between bg-white rounded-lg border border-slate-200 p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-blue-600" />
            <div>
              <p className="font-medium text-slate-900">Pending Review</p>
              <p className="text-sm text-slate-500">
                Extracted in {demoIntake.extractionTime}ms • {demoIntake.extractedFields.lineItems.length} line items
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-slate-900">{demoIntake.extractedFields.totalAmount.value}</p>
            <p className="text-sm text-slate-500">{demoIntake.extractedFields.currency.value}</p>
          </div>
        </div>

        {/* Validation Issues */}
        {demoIntake.validationIssues.length > 0 && (
          <Alert className="border-amber-200 bg-amber-50">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <AlertTitle>Validation Alerts ({demoIntake.validationIssues.length})</AlertTitle>
            <AlertDescription className="mt-2 space-y-2">
              {demoIntake.validationIssues.map((issue) => (
                <div key={issue.id} className="flex items-start gap-2 text-sm">
                  <span className="text-amber-600 font-semibold min-w-fit">{issue.field}:</span>
                  <span className="text-amber-800">{issue.message}</span>
                </div>
              ))}
            </AlertDescription>
          </Alert>
        )}

        {/* View Tabs */}
        <div className="flex gap-2 border-b border-slate-200">
          {["summary", "detailed", "lineItems"].map((view) => (
            <button
              key={view}
              onClick={() => setSelectedView(view as typeof selectedView)}
              className={`px-4 py-3 font-medium text-sm border-b-2 transition-colors ${
                selectedView === view
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-slate-600 hover:text-slate-900"
              }`}
            >
              {view === "summary" && "Summary"}
              {view === "detailed" && "Detailed Fields"}
              {view === "lineItems" && "Line Items"}
            </button>
          ))}
        </div>

        {/* Summary View */}
        {selectedView === "summary" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Invoice Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-slate-600 text-sm">Invoice Number</span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold">{demoIntake.extractedFields.invoiceNumber.value}</span>
                    <ConfidenceBadge confidence={demoIntake.extractedFields.invoiceNumber.confidence} />
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-600 text-sm">Invoice Date</span>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{demoIntake.extractedFields.invoiceDate.value}</span>
                    <StatusIcon status={demoIntake.extractedFields.invoiceDate.status} />
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-600 text-sm">Due Date</span>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{demoIntake.extractedFields.dueDate.value}</span>
                    <StatusIcon status={demoIntake.extractedFields.dueDate.status} />
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-600 text-sm">Payment Terms</span>
                  <span className="font-semibold">{demoIntake.extractedFields.paymentTerms.value}</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Vendor Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-slate-600 text-sm">Vendor Name</span>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">{demoIntake.extractedFields.vendorName.value}</span>
                    <StatusIcon status={demoIntake.extractedFields.vendorName.status} />
                  </div>
                </div>
                <div className="flex justify-between items-start">
                  <span className="text-slate-600 text-sm">Vendor ID</span>
                  <div className="flex flex-col items-end gap-1">
                    <span className="font-mono font-semibold">{demoIntake.extractedFields.vendorId.value}</span>
                    <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200 text-xs">
                      Needs Review
                    </Badge>
                  </div>
                </div>
                <div className="flex justify-between items-start">
                  <span className="text-slate-600 text-sm">Purchase Order</span>
                  <div className="flex flex-col items-end gap-1">
                    <span className="font-mono font-semibold">{demoIntake.extractedFields.purchaseOrder.value}</span>
                    <ConfidenceBadge confidence={demoIntake.extractedFields.purchaseOrder.confidence} />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Amount Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-slate-600 text-sm">Subtotal</span>
                  <span className="font-semibold">$12,000.00</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-600 text-sm">Tax</span>
                  <span className="font-semibold">{demoIntake.extractedFields.taxAmount.value}</span>
                </div>
                <div className="flex justify-between items-center border-t border-slate-200 pt-2">
                  <span className="text-slate-600 font-medium text-sm">Total Amount</span>
                  <span className="text-lg font-bold text-blue-600">
                    {demoIntake.extractedFields.totalAmount.value}
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Extraction Quality</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-slate-600 text-sm">Overall Confidence</span>
                    <span className="font-bold text-green-700">{(demoIntake.overallConfidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-slate-200 rounded-full h-2">
                    <div
                      className="bg-green-600 h-2 rounded-full"
                      style={{ width: `${demoIntake.overallConfidence * 100}%` }}
                    />
                  </div>
                </div>
                <div className="pt-2">
                  <p className="text-xs text-slate-500">
                    Status: <span className="text-green-700 font-semibold">Ready for Processing</span>
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Detailed Fields View */}
        {selectedView === "detailed" && (
          <Card>
            <CardHeader>
              <CardTitle>Extracted Fields</CardTitle>
              <CardDescription>Review confidence scores and validation status</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {Object.entries(demoIntake.extractedFields).map(([key, field]: [string, any]) => {
                  if (Array.isArray(field)) return null
                  if (typeof field === "object" && field.value !== undefined) {
                    return (
                      <div
                        key={key}
                        className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-200"
                      >
                        <div className="flex items-center gap-3 flex-1">
                          <StatusIcon status={field.status} />
                          <div className="flex-1">
                            <p className="text-sm font-medium text-slate-700">{key}</p>
                            <p className="text-base font-semibold text-slate-900">{field.value}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <ConfidenceBadge confidence={field.confidence} />
                          <Badge
                            variant={field.status === "validated" ? "secondary" : "outline"}
                            className={
                              field.status === "needs_review" ? "bg-amber-50 text-amber-700 border-amber-200" : ""
                            }
                          >
                            {field.status === "validated" ? "Validated" : "Needs Review"}
                          </Badge>
                        </div>
                      </div>
                    )
                  }
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Line Items View */}
        {selectedView === "lineItems" && (
          <Card>
            <CardHeader>
              <CardTitle>Line Items</CardTitle>
              <CardDescription>{demoIntake.extractedFields.lineItems.length} items found</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {demoIntake.extractedFields.lineItems.map((item, idx) => (
                  <div key={idx} className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-slate-900">{item.description}</h3>
                          <StatusIcon status={item.status} />
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-slate-900">${item.amount.toFixed(2)}</p>
                        <ConfidenceBadge confidence={item.confidence} />
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div className="flex justify-between">
                        <span className="text-slate-600">Qty</span>
                        <span className="font-mono font-semibold">{item.quantity}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Unit Price</span>
                        <span className="font-mono font-semibold">${item.unitPrice.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Total</span>
                        <span className="font-mono font-semibold">${item.amount.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 justify-end">
          <Button variant="outline">Reject & Request Reupload</Button>
          <Button variant="outline">Request Manual Review</Button>
          <Button className="bg-green-600 hover:bg-green-700">Approve & Process</Button>
        </div>

        {/* Navigation to Full System */}
        <Card className="bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-blue-900 mb-2">
                  Ready for the Complete Invoice Management System?
                </h3>
                <p className="text-blue-700 mb-4">
                  Access the full dashboard with batch operations, approval workflows,
                  exception handling, and advanced analytics.
                </p>
                <div className="flex gap-3">
                  <Button asChild>
                    <a href="/invoices" className="flex items-center gap-2">
                      <FileText className="w-4 h-4" />
                      Open Invoice Dashboard
                    </a>
                  </Button>
                  <Button variant="outline" asChild>
                    <a href="/invoices?tab=exceptions" className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4" />
                      View Exceptions
                    </a>
                  </Button>
                  <Button variant="outline" asChild>
                    <a href="/email" className="flex items-center gap-2">
                      <Mail className="w-4 h-4" />
                      Email Integration
                    </a>
                  </Button>
                </div>
              </div>
              <div className="hidden md:block">
                <div className="bg-white/80 backdrop-blur rounded-lg p-4 border border-blue-200">
                  <h4 className="font-semibold text-slate-900 mb-2">Quick Stats</h4>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between gap-4">
                      <span className="text-slate-600">Total Invoices:</span>
                      <span className="font-medium">1,247</span>
                    </div>
                    <div className="flex justify-between gap-4">
                      <span className="text-slate-600">Pending Review:</span>
                      <span className="font-medium text-yellow-600">23</span>
                    </div>
                    <div className="flex justify-between gap-4">
                      <span className="text-slate-600">Auto-Approval Rate:</span>
                      <span className="font-medium text-green-600">78.5%</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
