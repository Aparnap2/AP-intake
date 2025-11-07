"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  Info,
  Lightbulb,
  MessageSquare,
  Send,
  FileText,
  Search,
  Filter,
  Clock,
  User,
  Building,
  DollarSign,
  Calendar,
  RefreshCw,
  ChevronRight,
  ArrowRight,
  Zap,
  Settings,
  BookOpen,
  ExternalLink,
  Download,
  Upload,
  Mail,
  Phone,
  HelpCircle,
  CheckSquare,
  Square,
  Edit,
  Save,
  X,
  Eye,
  EyeOff,
  Copy,
  Link2,
  Paperclip,
  Bot,
  UserCheck
} from "lucide-react"
import { cn } from "@/lib/utils"

// Types for exception handling
interface ExceptionRule {
  id: string
  name: string
  description: string
  category: "validation" | "business" | "compliance" | "duplicate"
  severity: "low" | "medium" | "high" | "critical"
  condition: string
  action: "auto_reject" | "manual_review" | "request_info" | "auto_approve"
  enabled: boolean
  lastTriggered?: string
  triggerCount: number
}

interface Exception {
  id: string
  invoiceId: string
  ruleId: string
  ruleName: string
  category: string
  severity: "low" | "medium" | "high" | "critical"
  message: string
  field?: string
  currentValue?: string
  expectedValue?: string
  suggestedFix?: string
  autoFixable: boolean
  status: "open" | "in_progress" | "resolved" | "ignored"
  assignedTo?: string
  createdAt: string
  resolvedAt?: string
  resolvedBy?: string
  resolution?: string
  confidence: number
  context?: Record<string, any>
}

interface ResolutionStep {
  id: string
  title: string
  description: string
  type: "input" | "select" | "checkbox" | "radio" | "info" | "action"
  required: boolean
  completed: boolean
  data?: any
}

interface GuidedWorkflow {
  id: string
  name: string
  description: string
  category: string
  steps: ResolutionStep[]
  estimatedTime: number
  successRate: number
}

export function ExceptionResolution({ exceptions }: { exceptions: Exception[] }) {
  const [selectedException, setSelectedException] = useState<Exception | null>(null)
  const [activeWorkflow, setActiveWorkflow] = useState<GuidedWorkflow | null>(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [workflowData, setWorkflowData] = useState<Record<string, any>>({})
  const [showAISuggestions, setShowAISuggestions] = useState(true)
  const [searchTerm, setSearchTerm] = useState("")
  const [filterCategory, setFilterCategory] = useState("all")
  const [filterSeverity, setFilterSeverity] = useState("all")

  // Mock guided workflows
  const guidedWorkflows: GuidedWorkflow[] = [
    {
      id: "vendor-mismatch",
      name: "Vendor Information Mismatch",
      description: "Resolve discrepancies in vendor details",
      category: "validation",
      estimatedTime: 5,
      successRate: 92,
      steps: [
        {
          id: "1",
          title: "Identify the mismatch",
          description: "Review the vendor information that failed validation",
          type: "info",
          required: true,
          completed: false
        },
        {
          id: "2",
          title: "Choose resolution action",
          description: "Select how to resolve the vendor mismatch",
          type: "radio",
          required: true,
          completed: false,
          data: {
            options: [
              { value: "update_master", label: "Update vendor master data" },
              { value: "correct_invoice", label: "Correct invoice details" },
              { value: "create_new", label: "Create new vendor record" },
              { value: "escalate", label: "Escalate to supervisor" }
            ]
          }
        },
        {
          id: "3",
          title: "Provide supporting information",
          description: "Add documentation or comments to support your decision",
          type: "input",
          required: false,
          completed: false
        },
        {
          id: "4",
          title: "Confirm resolution",
          description: "Review and confirm the chosen resolution",
          type: "checkbox",
          required: true,
          completed: false,
          data: {
            label: "I have verified the information and confirm this resolution"
          }
        }
      ]
    },
    {
      id: "amount-discrepancy",
      name: "Amount Discrepancy Resolution",
      description: "Handle invoice total mismatches",
      category: "validation",
      estimatedTime: 8,
      successRate: 88,
      steps: [
        {
          id: "1",
          title: "Review calculation",
          description: "Check line items and calculations",
          type: "info",
          required: true,
          completed: false
        },
        {
          id: "2",
          title: "Identify discrepancy source",
          description: "Where does the amount mismatch occur?",
          type: "select",
          required: true,
          completed: false,
          data: {
            options: [
              { value: "tax_calculation", label: "Tax calculation error" },
              { value: "line_item_total", label: "Line item total mismatch" },
              { value: "currency_conversion", label: "Currency conversion issue" },
              { value: "manual_entry", label: "Manual data entry error" },
              { value: "other", label: "Other (specify)" }
            ]
          }
        },
        {
          id: "3",
          title: "Enter correct amount",
          description: "Provide the correct total amount",
          type: "input",
          required: true,
          completed: false
        }
      ]
    }
  ]

  // Mock AI suggestions
  const aiSuggestions = [
    {
      id: "1",
      type: "vendor_correction",
      title: "Vendor Name Suggestion",
      description: "Based on historical data, this vendor might be 'Acme Corporation Inc.'",
      confidence: 0.94,
      field: "vendorName",
      suggestedValue: "Acme Corporation Inc."
    },
    {
      id: "2",
      type: "po_match",
      title: "Purchase Order Match",
      description: "Found matching PO: PO-2024-0891 with similar amount and vendor",
      confidence: 0.89,
      field: "purchaseOrder",
      suggestedValue: "PO-2024-0891"
    }
  ]

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical":
        return "bg-red-50 text-red-700 border-red-200"
      case "high":
        return "bg-orange-50 text-orange-700 border-orange-200"
      case "medium":
        return "bg-yellow-50 text-yellow-700 border-yellow-200"
      default:
        return "bg-blue-50 text-blue-700 border-blue-200"
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "resolved":
        return "bg-green-50 text-green-700 border-green-200"
      case "in_progress":
        return "bg-blue-50 text-blue-700 border-blue-200"
      case "ignored":
        return "bg-slate-50 text-slate-700 border-slate-200"
      default:
        return "bg-red-50 text-red-700 border-red-200"
    }
  }

  const getWorkflowProgress = () => {
    if (!activeWorkflow) return 0
    const completedSteps = activeWorkflow.steps.filter(step => step.completed).length
    return (completedSteps / activeWorkflow.steps.length) * 100
  }

  const handleStepComplete = (stepId: string, data: any) => {
    if (!activeWorkflow) return

    setWorkflowData(prev => ({ ...prev, [stepId]: data }))

    setActiveWorkflow(prev => prev ? {
      ...prev,
      steps: prev.steps.map(step =>
        step.id === stepId ? { ...step, completed: true, data } : step
      )
    } : null)

    // Move to next step
    const currentStepIndex = activeWorkflow.steps.findIndex(step => step.id === stepId)
    if (currentStepIndex < activeWorkflow.steps.length - 1) {
      setCurrentStep(currentStepIndex + 1)
    }
  }

  const filteredExceptions = exceptions.filter(exception => {
    const matchesSearch = exception.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         exception.ruleName.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesCategory = filterCategory === "all" || exception.category === filterCategory
    const matchesSeverity = filterSeverity === "all" || exception.severity === filterSeverity

    return matchesSearch && matchesCategory && matchesSeverity
  })

  const renderWorkflowStep = (step: ResolutionStep) => {
    switch (step.type) {
      case "info":
        return (
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
            <div className="flex items-start gap-3">
              <Info className="w-5 h-5 text-blue-600 mt-0.5" />
              <div>
                <h4 className="font-semibold text-blue-900">{step.title}</h4>
                <p className="text-blue-700 mt-1">{step.description}</p>
              </div>
            </div>
          </div>
        )

      case "input":
        return (
          <div className="space-y-3">
            <div>
              <Label className="font-semibold">{step.title}</Label>
              <p className="text-sm text-slate-600 mt-1">{step.description}</p>
            </div>
            <Textarea
              placeholder="Enter details..."
              onChange={(e) => handleStepComplete(step.id, e.target.value)}
            />
          </div>
        )

      case "select":
      case "radio":
        return (
          <div className="space-y-3">
            <div>
              <Label className="font-semibold">{step.title}</Label>
              <p className="text-sm text-slate-600 mt-1">{step.description}</p>
            </div>
            <RadioGroup onValueChange={(value) => handleStepComplete(step.id, value)}>
              {step.data?.options?.map((option: any) => (
                <div key={option.value} className="flex items-center space-x-2">
                  <RadioGroupItem value={option.value} id={option.value} />
                  <Label htmlFor={option.value}>{option.label}</Label>
                </div>
              ))}
            </RadioGroup>
          </div>
        )

      case "checkbox":
        return (
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Checkbox
                id={step.id}
                onCheckedChange={(checked) => handleStepComplete(step.id, checked)}
              />
              <Label htmlFor={step.id} className="font-semibold">
                {step.title}
              </Label>
            </div>
            <p className="text-sm text-slate-600 ml-6">{step.description}</p>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Exception Resolution</h1>
          <p className="text-slate-600">Handle invoice processing exceptions and validation issues</p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={() => setShowAISuggestions(!showAISuggestions)}
            className="flex items-center gap-2"
          >
            <Bot className="w-4 h-4" />
            AI Assistant
          </Button>
          <Button variant="outline">
            <Settings className="w-4 h-4 mr-2" />
            Configure Rules
          </Button>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Open Exceptions</CardTitle>
            <AlertTriangle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {exceptions.filter(e => e.status === "open").length}
            </div>
            <p className="text-xs text-muted-foreground">
              {Math.round((exceptions.filter(e => e.status === "open").length / exceptions.length) * 100)}% of total
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">In Progress</CardTitle>
            <Clock className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {exceptions.filter(e => e.status === "in_progress").length}
            </div>
            <p className="text-xs text-muted-foreground">
              Being actively resolved
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Resolved Today</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">12</div>
            <p className="text-xs text-muted-foreground">
              +15% from yesterday
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Auto-Fix Rate</CardTitle>
            <Zap className="h-4 w-4 text-yellow-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">68%</div>
            <p className="text-xs text-muted-foreground">
              Automatically resolved
            </p>
          </CardContent>
        </Card>
      </div>

      {/* AI Suggestions Panel */}
      {showAISuggestions && (
        <Card className="border-blue-200 bg-blue-50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-blue-900">
              <Bot className="w-5 h-5" />
              AI-Powered Suggestions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {aiSuggestions.map((suggestion) => (
                <div key={suggestion.id} className="flex items-start gap-3 p-3 bg-white rounded-lg border border-blue-200">
                  <Lightbulb className="w-5 h-5 text-blue-600 mt-0.5" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <h4 className="font-semibold text-blue-900">{suggestion.title}</h4>
                      <Badge variant="outline" className="text-blue-700 border-blue-200">
                        {Math.round(suggestion.confidence * 100)}% confidence
                      </Badge>
                    </div>
                    <p className="text-sm text-slate-600 mt-1">{suggestion.description}</p>
                    <div className="flex items-center gap-2 mt-2">
                      <Button size="sm" variant="outline" className="text-blue-700 border-blue-200">
                        <CheckSquare className="w-4 h-4 mr-1" />
                        Apply Suggestion
                      </Button>
                      <Button size="sm" variant="ghost">
                        <X className="w-4 h-4 mr-1" />
                        Dismiss
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Exceptions List */}
        <Card>
          <CardHeader>
            <CardTitle>Active Exceptions</CardTitle>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Search exceptions..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Select value={filterCategory} onValueChange={setFilterCategory}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="validation">Validation</SelectItem>
                  <SelectItem value="business">Business</SelectItem>
                  <SelectItem value="compliance">Compliance</SelectItem>
                  <SelectItem value="duplicate">Duplicate</SelectItem>
                </SelectContent>
              </Select>
              <Select value={filterSeverity} onValueChange={setFilterSeverity}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Levels</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {filteredExceptions.map((exception) => (
                <div
                  key={exception.id}
                  className={cn(
                    "p-4 rounded-lg border cursor-pointer transition-all hover:shadow-md",
                    selectedException?.id === exception.id
                      ? "border-blue-300 bg-blue-50"
                      : "border-slate-200 hover:border-slate-300"
                  )}
                  onClick={() => setSelectedException(exception)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge className={getSeverityColor(exception.severity)}>
                          {exception.severity}
                        </Badge>
                        <Badge className={getStatusColor(exception.status)}>
                          {exception.status.replace("_", " ")}
                        </Badge>
                        {exception.autoFixable && (
                          <Badge variant="outline" className="text-green-700 border-green-200">
                            Auto-fixable
                          </Badge>
                        )}
                      </div>
                      <h4 className="font-semibold text-slate-900">{exception.ruleName}</h4>
                      <p className="text-sm text-slate-600 mt-1">{exception.message}</p>
                      {exception.field && (
                        <div className="mt-2 text-sm">
                          <span className="font-medium">Field:</span> {exception.field}
                          {exception.currentValue && (
                            <span className="ml-4">
                              <span className="font-medium">Current:</span> {exception.currentValue}
                            </span>
                          )}
                        </div>
                      )}
                      <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
                        <span>Invoice: {exception.invoiceId}</span>
                        <span>{new Date(exception.createdAt).toLocaleDateString()}</span>
                        {exception.assignedTo && (
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {exception.assignedTo}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Resolution Workflow */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ChevronRight className="w-5 h-5" />
              Resolution Workflow
            </CardTitle>
            <CardDescription>
              {selectedException
                ? `Resolving: ${selectedException.ruleName}`
                : "Select an exception to start resolution"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {selectedException ? (
              <div className="space-y-4">
                {/* Exception Details */}
                <Alert className={getSeverityColor(selectedException.severity)}>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>{selectedException.ruleName}</AlertTitle>
                  <AlertDescription className="mt-2">
                    {selectedException.message}
                    {selectedException.suggestedFix && (
                      <div className="mt-2 p-2 bg-white/50 rounded border">
                        <strong>Suggested Fix:</strong> {selectedException.suggestedFix}
                      </div>
                    )}
                  </AlertDescription>
                </Alert>

                {/* Workflow Selection */}
                {!activeWorkflow && (
                  <div className="space-y-3">
                    <h4 className="font-semibold">Choose Resolution Method</h4>
                    <div className="space-y-2">
                      {guidedWorkflows
                        .filter(wf => wf.category === selectedException.category)
                        .map((workflow) => (
                          <div
                            key={workflow.id}
                            className="p-4 border rounded-lg cursor-pointer hover:bg-slate-50 transition-colors"
                            onClick={() => setActiveWorkflow(workflow)}
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <h5 className="font-semibold">{workflow.name}</h5>
                                <p className="text-sm text-slate-600">{workflow.description}</p>
                                <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                                  <span>~{workflow.estimatedTime} min</span>
                                  <span>{workflow.successRate}% success rate</span>
                                </div>
                              </div>
                              <ArrowRight className="w-5 h-5 text-slate-400" />
                            </div>
                          </div>
                        ))}

                      <Button
                        variant="outline"
                        className="w-full justify-start"
                        onClick={() => setActiveWorkflow(null)}
                      >
                        <Edit className="w-4 h-4 mr-2" />
                        Manual Resolution
                      </Button>
                    </div>
                  </div>
                )}

                {/* Active Workflow */}
                {activeWorkflow && (
                  <div className="space-y-4">
                    {/* Progress Bar */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Progress</span>
                        <span className="text-sm text-slate-600">
                          {currentStep + 1} of {activeWorkflow.steps.length}
                        </span>
                      </div>
                      <Progress value={getWorkflowProgress()} className="h-2" />
                    </div>

                    {/* Current Step */}
                    <div className="space-y-4">
                      {activeWorkflow.steps.map((step, index) => (
                        <div
                          key={step.id}
                          className={cn(
                            "p-4 rounded-lg border",
                            index === currentStep
                              ? "border-blue-300 bg-blue-50"
                              : step.completed
                              ? "border-green-300 bg-green-50"
                              : "border-slate-200 bg-slate-50"
                          )}
                        >
                          <div className="flex items-center gap-3">
                            <div className={cn(
                              "w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold",
                              step.completed
                                ? "bg-green-600 text-white"
                                : index === currentStep
                                ? "bg-blue-600 text-white"
                                : "bg-slate-300 text-slate-600"
                            )}>
                              {step.completed ? "✓" : index + 1}
                            </div>
                            <div className="flex-1">
                              <h5 className="font-semibold">{step.title}</h5>
                              {index === currentStep && (
                                <div className="mt-3">
                                  {renderWorkflowStep(step)}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Workflow Actions */}
                    <div className="flex items-center justify-between pt-4 border-t">
                      <Button
                        variant="outline"
                        onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
                        disabled={currentStep === 0}
                      >
                        Previous
                      </Button>
                      <div className="flex gap-2">
                        <Button variant="outline" onClick={() => setActiveWorkflow(null)}>
                          Cancel
                        </Button>
                        {currentStep === activeWorkflow.steps.length - 1 ? (
                          <Button className="bg-green-600 hover:bg-green-700">
                            <CheckCircle2 className="w-4 h-4 mr-2" />
                            Complete Resolution
                          </Button>
                        ) : (
                          <Button
                            onClick={() => setCurrentStep(Math.min(activeWorkflow.steps.length - 1, currentStep + 1))}
                            disabled={!activeWorkflow.steps[currentStep].completed}
                          >
                            Next Step
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-slate-500">
                <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                <p>Select an exception to start the resolution process</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}