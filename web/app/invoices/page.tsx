"use client"

import { useState, useEffect } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  FileText,
  Eye,
  AlertTriangle,
  CheckCircle2,
  Clock,
  TrendingUp,
  Users,
  DollarSign,
  Settings,
  RefreshCw,
  Download,
  Upload,
  Search,
  Filter,
  BarChart3,
  PieChart,
  Activity,
  Mail
} from "lucide-react"
import { cn } from "@/lib/utils"

import { InvoiceDashboard } from "@/components/invoice/InvoiceDashboard"
import { InvoiceReview } from "@/components/invoice/InvoiceReview"
import { ExceptionResolution } from "@/components/invoice/ExceptionResolution"
import { ApprovalWorkflow } from "@/components/invoice/ApprovalWorkflow"
import { ExportManagement } from "@/components/invoice/ExportManagement"
import { NotificationCenter } from "@/components/invoice/NotificationCenter"
import { UploadModal } from "@/components/invoice/UploadModal"

// Mock data for statistics
const mockStats = {
  totalInvoices: 1247,
  pendingReview: 23,
  approved: 1198,
  rejected: 15,
  needsMoreInfo: 11,
  averageProcessingTime: 2.4,
  totalAmount: 2847560.50,
  thisMonthAmount: 342150.75,
  autoApprovalRate: 78.5,
  exceptionRate: 12.3
}

const mockExceptionData = [
  {
    id: "1",
    invoiceId: "INV-2024-5647",
    ruleId: "rule_1",
    ruleName: "Vendor Information Mismatch",
    category: "validation",
    severity: "medium",
    message: "Vendor name 'Acme Corp' does not match master record 'Acme Corporation Inc.'",
    field: "vendorName",
    currentValue: "Acme Corp",
    expectedValue: "Acme Corporation Inc.",
    suggestedFix: "Update to 'Acme Corporation Inc.'",
    autoFixable: true,
    status: "open",
    createdAt: "2024-11-05T14:32:00Z",
    confidence: 0.94,
    context: {}
  },
  {
    id: "2",
    invoiceId: "INV-2024-5648",
    ruleId: "rule_2",
    ruleName: "Amount Exceeds Limit",
    category: "business",
    severity: "high",
    message: "Invoice amount $15,000 exceeds approval limit of $10,000",
    field: "totalAmount",
    currentValue: "$15,000",
    suggestedFix: "Escalate to senior approver",
    autoFixable: false,
    status: "open",
    createdAt: "2024-11-04T09:15:00Z",
    confidence: 0.98,
    context: { limit: 10000, excess: 5000 }
  }
]

export default function InvoicesPage() {
  const [activeTab, setActiveTab] = useState("dashboard")
  const [selectedInvoice, setSelectedInvoice] = useState(null)
  const [stats, setStats] = useState(mockStats)
  const [loading, setLoading] = useState(false)
  const [uploadModalOpen, setUploadModalOpen] = useState(false)

  const handleApprovalComplete = (updatedInvoice) => {
    // Update the selected invoice with new status
    setSelectedInvoice(updatedInvoice)

    // Optionally update stats if needed
    if (updatedInvoice.status === "approved") {
      setStats(prev => ({
        ...prev,
        pendingReview: Math.max(0, prev.pendingReview - 1),
        approved: prev.approved + 1
      }))
    } else if (updatedInvoice.status === "rejected") {
      setStats(prev => ({
        ...prev,
        pendingReview: Math.max(0, prev.pendingReview - 1),
        rejected: prev.rejected + 1
      }))
    } else if (updatedInvoice.status === "needs_more_info") {
      setStats(prev => ({
        ...prev,
        pendingReview: Math.max(0, prev.pendingReview - 1),
        needsMoreInfo: prev.needsMoreInfo + 1
      }))
    }

    // Optional: Auto-navigate back to dashboard after successful approval
    if (updatedInvoice.status === "approved") {
      setTimeout(() => setActiveTab("dashboard"), 2000)
    }
  }

  useEffect(() => {
    // Simulate loading data
    setLoading(true)
    setTimeout(() => {
      setLoading(false)
    }, 1000)
  }, [])

  const handleInvoiceSelect = (invoice) => {
    setSelectedInvoice(invoice)
    setActiveTab("review")
  }

  const handleRefresh = () => {
    setLoading(true)
    setTimeout(() => {
      setLoading(false)
    }, 1000)
  }

  const handleUploadSuccess = (invoices: any[]) => {
    console.log("Upload successful:", invoices)
    // Refresh the invoice list after successful upload
    handleRefresh()
    // Show success message or update stats if needed
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="container mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold text-slate-900">Invoice Management</h1>
            <p className="text-lg text-slate-600 mt-2">
              Process, review, and approve invoices with AI-powered automation
            </p>
          </div>
          <div className="flex items-center gap-3">
            <NotificationCenter />
            <Button variant="outline" onClick={handleRefresh} disabled={loading}>
              <RefreshCw className={cn("w-4 h-4 mr-2", loading && "animate-spin")} />
              Refresh
            </Button>
            <Button variant="outline">
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
            <Button onClick={() => setUploadModalOpen(true)}>
              <Upload className="w-4 h-4 mr-2" />
              Upload Invoice
            </Button>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Processed</CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.totalInvoices.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground">
                +12% from last month
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Pending Review</CardTitle>
              <Clock className="h-4 w-4 text-yellow-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{stats.pendingReview}</div>
              <p className="text-xs text-muted-foreground">
                {Math.round((stats.pendingReview / stats.totalInvoices) * 100)}% of total
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Auto-Approval Rate</CardTitle>
              <TrendingUp className="h-4 w-4 text-green-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{stats.autoApprovalRate}%</div>
              <Progress value={stats.autoApprovalRate} className="h-2 mt-2" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Amount</CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">${stats.thisMonthAmount.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground">
                This month
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Main Content Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-7">
            <TabsTrigger value="dashboard" className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="review" className="flex items-center gap-2">
              <Eye className="w-4 h-4" />
              Review
            </TabsTrigger>
            <TabsTrigger value="exceptions" className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              Exceptions
              {mockExceptionData.filter(e => e.status === "open").length > 0 && (
                <Badge variant="destructive" className="ml-1 h-5 w-5 p-0 text-xs">
                  {mockExceptionData.filter(e => e.status === "open").length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="approvals" className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" />
              Approvals
            </TabsTrigger>
            <TabsTrigger value="exports" className="flex items-center gap-2">
              <Download className="w-4 h-4" />
              Exports
            </TabsTrigger>
            <TabsTrigger value="analytics" className="flex items-center gap-2">
              <PieChart className="w-4 h-4" />
              Analytics
            </TabsTrigger>
            <TabsTrigger value="email" className="flex items-center gap-2">
              <Mail className="w-4 h-4" />
              Email
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard" className="space-y-6">
            <InvoiceDashboard onInvoiceSelect={handleInvoiceSelect} />
          </TabsContent>

          <TabsContent value="review" className="space-y-6">
            {selectedInvoice ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-2xl font-bold">Invoice Review</h2>
                  <Button
                    variant="outline"
                    onClick={() => setActiveTab("dashboard")}
                  >
                    ← Back to Dashboard
                  </Button>
                </div>
                <InvoiceReview
                  invoice={selectedInvoice}
                  onApprovalComplete={handleApprovalComplete}
                />
              </div>
            ) : (
              <Card>
                <CardHeader>
                  <CardTitle>Select an Invoice to Review</CardTitle>
                  <CardDescription>
                    Choose an invoice from the dashboard to start the review process
                  </CardDescription>
                </CardHeader>
                <CardContent className="text-center py-8">
                  <Eye className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                  <p className="text-slate-600">No invoice selected for review</p>
                  <Button
                    className="mt-4"
                    onClick={() => setActiveTab("dashboard")}
                  >
                    Go to Dashboard
                  </Button>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="exceptions" className="space-y-6">
            <ExceptionResolution exceptions={mockExceptionData} />
          </TabsContent>

          <TabsContent value="approvals" className="space-y-6">
            <ApprovalWorkflow />
          </TabsContent>

          <TabsContent value="exports" className="space-y-6">
            <ExportManagement />
          </TabsContent>

          <TabsContent value="analytics" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Processing Trends</CardTitle>
                  <CardDescription>Invoice processing volume over time</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-64 flex items-center justify-center text-slate-500">
                    <div className="text-center">
                      <BarChart3 className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                      <p>Chart visualization would go here</p>
                      <p className="text-sm">Integration with chart library needed</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Exception Categories</CardTitle>
                  <CardDescription>Breakdown of exception types</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-64 flex items-center justify-center text-slate-500">
                    <div className="text-center">
                      <PieChart className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                      <p>Pie chart visualization would go here</p>
                      <p className="text-sm">Exception distribution by category</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Approval Performance</CardTitle>
                  <CardDescription>Approval times and rates by user</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-64 flex items-center justify-center text-slate-500">
                    <div className="text-center">
                      <Activity className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                      <p>Performance metrics would go here</p>
                      <p className="text-sm">User approval statistics</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Vendor Analysis</CardTitle>
                  <CardDescription>Top vendors by invoice volume and amount</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-64 flex items-center justify-center text-slate-500">
                    <div className="text-center">
                      <Users className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                      <p>Vendor rankings would go here</p>
                      <p className="text-sm">Vendor performance metrics</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="email" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Mail className="w-5 h-5" />
                  Email Integration
                </CardTitle>
                <CardDescription>
                  Automatic email processing for invoice detection and extraction
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Card className="border-blue-200 bg-blue-50">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Mail className="w-4 h-4 text-blue-600" />
                        Connected Accounts
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-blue-900">3</div>
                      <p className="text-sm text-blue-700">Gmail accounts active</p>
                    </CardContent>
                  </Card>

                  <Card className="border-green-200 bg-green-50">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600" />
                        Emails Processed
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-green-900">2,847</div>
                      <p className="text-sm text-green-700">This month</p>
                    </CardContent>
                  </Card>

                  <Card className="border-purple-200 bg-purple-50">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base flex items-center gap-2">
                        <FileText className="w-4 h-4 text-purple-600" />
                        Invoices Found
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-purple-900">428</div>
                      <p className="text-sm text-purple-700">Auto-detected</p>
                    </CardContent>
                  </Card>
                </div>

                <div className="flex justify-center">
                  <Button asChild className="bg-blue-600 hover:bg-blue-700">
                    <a href="/email" className="flex items-center gap-2">
                      <Mail className="w-4 h-4" />
                      Open Email Dashboard
                    </a>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Upload Modal */}
        <UploadModal
          open={uploadModalOpen}
          onOpenChange={setUploadModalOpen}
          onSuccess={handleUploadSuccess}
        />
      </div>
    </div>
  )
}