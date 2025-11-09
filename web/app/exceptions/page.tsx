"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  BarChart3,
  Settings,
  Layers,
  Eye,
  Filter,
  RefreshCw,
  Plus,
  AlertCircle,
  TrendingUp,
  Target,
  Users
} from "lucide-react"
import { ExceptionDashboard } from "@/components/exceptions/ExceptionDashboard"
import { ExceptionReview } from "@/components/exceptions/ExceptionReview"
import { BatchResolution } from "@/components/exceptions/BatchResolution"
import { ExceptionAnalytics } from "@/components/exceptions/ExceptionAnalytics"
import { useExceptions } from "@/hooks/useExceptions"

export default function ExceptionsPage() {
  const [activeTab, setActiveTab] = useState("dashboard")
  const [selectedException, setSelectedException] = useState<string | null>(null)
  const [selectedExceptions, setSelectedExceptions] = useState<string[]>([])
  const [showBatchResolution, setShowBatchResolution] = useState(false)
  const [showExceptionReview, setShowExceptionReview] = useState(false)

  const { exceptions, refreshExceptions, stats } = useExceptions()

  const handleExceptionSelect = (exception: any) => {
    setSelectedException(exception.id)
    setShowExceptionReview(true)
  }

  const handleBatchResolve = () => {
    if (selectedExceptions.length > 0) {
      setShowBatchResolution(true)
    }
  }

  const handleExceptionsProcessed = (results: any) => {
    setShowBatchResolution(false)
    setSelectedExceptions([])
    refreshExceptions()
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-6 h-6 text-orange-600" />
                <h1 className="text-xl font-semibold text-slate-900">Exception Management</h1>
              </div>
              <Badge variant="secondary" className="hidden sm:inline-flex">
                {exceptions.length} total
              </Badge>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" onClick={refreshExceptions}>
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
              <Dialog open={showBatchResolution} onOpenChange={setShowBatchResolution}>
                <DialogTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={selectedExceptions.length === 0}
                  >
                    <Layers className="w-4 h-4 mr-2" />
                    Batch Resolve ({selectedExceptions.length})
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
                  <BatchResolution
                    selectedExceptions={selectedExceptions}
                    onExceptionsProcessed={handleExceptionsProcessed}
                    onClose={() => setShowBatchResolution(false)}
                  />
                </DialogContent>
              </Dialog>
              <Button size="sm">
                <Plus className="w-4 h-4 mr-2" />
                New Exception
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Stats Bar */}
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-blue-600 rounded-full" />
              <span className="text-sm text-slate-600">Total:</span>
              <span className="text-sm font-semibold text-slate-900">{exceptions.length}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-orange-600 rounded-full" />
              <span className="text-sm text-slate-600">Open:</span>
              <span className="text-sm font-semibold text-slate-900">
                {exceptions.filter(ex => ex.status === "open").length}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-600 rounded-full" />
              <span className="text-sm text-slate-600">Resolved:</span>
              <span className="text-sm font-semibold text-slate-900">
                {exceptions.filter(ex => ex.status === "resolved").length}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-purple-600 rounded-full" />
              <span className="text-sm text-slate-600">In Progress:</span>
              <span className="text-sm font-semibold text-slate-900">
                {exceptions.filter(ex => ex.status === "in_progress").length}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="dashboard" className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="review" className="flex items-center gap-2">
              <Eye className="w-4 h-4" />
              Review
            </TabsTrigger>
            <TabsTrigger value="batch" className="flex items-center gap-2">
              <Layers className="w-4 h-4" />
              Batch Operations
            </TabsTrigger>
            <TabsTrigger value="analytics" className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Analytics
            </TabsTrigger>
          </TabsList>

          {/* Dashboard Tab */}
          <TabsContent value="dashboard" className="space-y-6">
            <ExceptionDashboard
              onExceptionSelect={handleExceptionSelect}
              selectedExceptions={selectedExceptions}
              onSelectedExceptionsChange={setSelectedExceptions}
            />
          </TabsContent>

          {/* Review Tab */}
          <TabsContent value="review" className="space-y-6">
            {selectedException ? (
              <ExceptionReview
                exceptionId={selectedException}
                onClose={() => setSelectedException(null)}
                onExceptionUpdate={() => {
                  refreshExceptions()
                  setSelectedException(null)
                }}
              />
            ) : (
              <Card>
                <CardContent className="py-12">
                  <div className="text-center space-y-4">
                    <Eye className="w-12 h-12 text-slate-400 mx-auto" />
                    <div>
                      <h3 className="text-lg font-semibold text-slate-900">No Exception Selected</h3>
                      <p className="text-slate-600">
                        Select an exception from the dashboard to review its details.
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      onClick={() => setActiveTab("dashboard")}
                    >
                      Go to Dashboard
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Batch Operations Tab */}
          <TabsContent value="batch" className="space-y-6">
            {selectedExceptions.length > 0 ? (
              <BatchResolution
                selectedExceptions={selectedExceptions}
                onExceptionsProcessed={handleExceptionsProcessed}
                onClose={() => setSelectedExceptions([])}
              />
            ) : (
              <Card>
                <CardContent className="py-12">
                  <div className="text-center space-y-4">
                    <Layers className="w-12 h-12 text-slate-400 mx-auto" />
                    <div>
                      <h3 className="text-lg font-semibold text-slate-900">No Exceptions Selected</h3>
                      <p className="text-slate-600">
                        Select one or more exceptions from the dashboard to perform batch operations.
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      onClick={() => setActiveTab("dashboard")}
                    >
                      Go to Dashboard
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Analytics Tab */}
          <TabsContent value="analytics" className="space-y-6">
            <ExceptionAnalytics />
          </TabsContent>
        </Tabs>
      </div>

      {/* Exception Review Dialog */}
      <Dialog open={showExceptionReview && !!selectedException} onOpenChange={setShowExceptionReview}>
        <DialogContent className="max-w-6xl max-h-[90vh] overflow-y-auto">
          {selectedException && (
            <ExceptionReview
              exceptionId={selectedException}
              onClose={() => {
                setShowExceptionReview(false)
                setSelectedException(null)
              }}
              onExceptionUpdate={() => {
                refreshExceptions()
                setShowExceptionReview(false)
                setSelectedException(null)
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}