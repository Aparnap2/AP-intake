"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Progress } from "@/components/ui/progress"
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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Diff,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Info,
  Eye,
  EyeOff,
  Filter,
  Download,
  RefreshCw,
  FileText,
  ArrowRightLeft,
  Zap,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Minus
} from "lucide-react"
import { cn } from "@/lib/utils"

// Types
interface DiffChange {
  field_path: string
  change_type: "added" | "removed" | "modified" | "moved"
  old_value: any
  new_value: any
  change_magnitude?: number
  significance: "low" | "medium" | "high" | "critical"
}

interface DiffSummary {
  total_changes: number
  added_fields: number
  removed_fields: number
  modified_fields: number
  critical_changes: number
  high_changes: number
  medium_changes: number
  low_changes: number
  overall_significance: "low" | "medium" | "high" | "critical"
}

interface DiffData {
  comparison_id: string
  comparison_name: string
  timestamp: string
  original_data: any
  modified_data: any
  changes: DiffChange[]
  summary: DiffSummary
  context: any
}

interface DiffViewerProps {
  diffData: DiffData
  showOriginal?: boolean
  showModified?: boolean
  compact?: boolean
  filterSignificance?: string[]
  onApprove?: () => void
  onReject?: () => void
  onRequestChanges?: () => void
}

export function DiffViewer({
  diffData,
  showOriginal = true,
  showModified = true,
  compact = false,
  filterSignificance,
  onApprove,
  onReject,
  onRequestChanges
}: DiffViewerProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [filteredChanges, setFilteredChanges] = useState<DiffChange[]>(diffData.changes)
  const [showOnlySignificant, setShowOnlySignificant] = useState(false)
  const [selectedChange, setSelectedChange] = useState<DiffChange | null>(null)

  // Filter changes based on significance
  const filteredBySignificance = diffData.changes.filter(change => {
    if (filterSignificance && !filterSignificance.includes(change.significance)) {
      return false
    }
    if (showOnlySignificant && change.significance === "low") {
      return false
    }
    return true
  })

  // Group changes by field path sections
  const groupedChanges = filteredBySignificance.reduce((groups, change) => {
    const pathParts = change.field_path.split(".")
    const group = pathParts[0] || "root"

    if (!groups[group]) {
      groups[group] = []
    }
    groups[group].push(change)

    return groups
  }, {} as Record<string, DiffChange[]>)

  const toggleGroup = (group: string) => {
    const newExpanded = new Set(expandedGroups)
    if (newExpanded.has(group)) {
      newExpanded.delete(group)
    } else {
      newExpanded.add(group)
    }
    setExpandedGroups(newExpanded)
  }

  const getSignificanceColor = (significance: string) => {
    switch (significance) {
      case "critical":
        return "bg-red-50 text-red-700 border-red-200"
      case "high":
        return "bg-orange-50 text-orange-700 border-orange-200"
      case "medium":
        return "bg-yellow-50 text-yellow-700 border-yellow-200"
      case "low":
        return "bg-blue-50 text-blue-700 border-blue-200"
      default:
        return "bg-gray-50 text-gray-700 border-gray-200"
    }
  }

  const getChangeTypeIcon = (changeType: string) => {
    switch (changeType) {
      case "added":
        return <TrendingUp className="w-4 h-4 text-green-600" />
      case "removed":
        return <TrendingDown className="w-4 h-4 text-red-600" />
      case "modified":
        return <ArrowRightLeft className="w-4 h-4 text-blue-600" />
      case "moved":
        return <RefreshCw className="w-4 h-4 text-purple-600" />
      default:
        return <Diff className="w-4 h-4 text-gray-600" />
    }
  }

  const getChangeTypeColor = (changeType: string) => {
    switch (changeType) {
      case "added":
        return "text-green-600 bg-green-50"
      case "removed":
        return "text-red-600 bg-red-50"
      case "modified":
        return "text-blue-600 bg-blue-50"
      case "moved":
        return "text-purple-600 bg-purple-50"
      default:
        return "text-gray-600 bg-gray-50"
    }
  }

  const formatValue = (value: any) => {
    if (value === null || value === undefined) {
      return <span className="text-gray-400 italic">null</span>
    }
    if (typeof value === "object") {
      return (
        <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
          {JSON.stringify(value, null, 2)}
        </pre>
      )
    }
    if (typeof value === "string" && value.length > 100) {
      return <span title={value}>{value.substring(0, 100)}...</span>
    }
    return <span>{String(value)}</span>
  }

  const renderChangeValue = (change: DiffChange, type: "old" | "new") => {
    const value = type === "old" ? change.old_value : change.new_value
    const changeType = change.change_type

    if (changeType === "added" && type === "old") {
      return <span className="text-gray-400 italic">N/A</span>
    }
    if (changeType === "removed" && type === "new") {
      return <span className="text-gray-400 italic">N/A</span>
    }

    return formatValue(value)
  }

  const getOverallSignificanceIcon = (significance: string) => {
    switch (significance) {
      case "critical":
        return <XCircle className="w-5 h-5 text-red-600" />
      case "high":
        return <AlertTriangle className="w-5 h-5 text-orange-600" />
      case "medium":
        return <AlertCircle className="w-5 h-5 text-yellow-600" />
      case "low":
        return <Info className="w-5 h-5 text-blue-600" />
      default:
        return <CheckCircle2 className="w-5 h-5 text-green-600" />
    }
  }

  if (compact) {
    return (
      <div className="space-y-4">
        {/* Compact Summary */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">{diffData.comparison_name}</CardTitle>
              <div className="flex items-center gap-2">
                {getOverallSignificanceIcon(diffData.summary.overall_significance)}
                <Badge className={getSignificanceColor(diffData.summary.overall_significance)}>
                  {diffData.summary.overall_significance.toUpperCase()}
                </Badge>
              </div>
            </div>
            <CardDescription>
              {diffData.summary.total_changes} changes detected
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4 text-sm">
              <div className="text-center">
                <div className="font-semibold text-green-600">{diffData.summary.added_fields}</div>
                <div className="text-gray-600">Added</div>
              </div>
              <div className="text-center">
                <div className="font-semibold text-red-600">{diffData.summary.removed_fields}</div>
                <div className="text-gray-600">Removed</div>
              </div>
              <div className="text-center">
                <div className="font-semibold text-blue-600">{diffData.summary.modified_fields}</div>
                <div className="text-gray-600">Modified</div>
              </div>
              <div className="text-center">
                <div className="font-semibold text-orange-600">{diffData.summary.critical_changes}</div>
                <div className="text-gray-600">Critical</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Action Buttons */}
        <div className="flex items-center justify-between">
          <Button variant="outline" size="sm">
            <Eye className="w-4 h-4 mr-2" />
            View Details
          </Button>
          <div className="flex items-center gap-2">
            {onReject && (
              <Button variant="destructive" size="sm" onClick={onReject}>
                Reject
              </Button>
            )}
            {onRequestChanges && (
              <Button variant="outline" size="sm" onClick={onRequestChanges}>
                Request Changes
              </Button>
            )}
            {onApprove && (
              <Button size="sm" onClick={onApprove}>
                Approve
              </Button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with Summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Diff className="w-5 h-5" />
                {diffData.comparison_name}
              </CardTitle>
              <CardDescription>
                Comparison generated on {new Date(diffData.timestamp).toLocaleString()}
              </CardDescription>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                {getOverallSignificanceIcon(diffData.summary.overall_significance)}
                <Badge className={getSignificanceColor(diffData.summary.overall_significance)}>
                  {diffData.summary.overall_significance.toUpperCase()} SIGNIFICANCE
                </Badge>
              </div>
              <Button variant="outline" size="sm">
                <Download className="w-4 h-4 mr-2" />
                Export Diff
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Summary Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Total Changes</p>
                    <p className="text-2xl font-bold">{diffData.summary.total_changes}</p>
                  </div>
                  <Diff className="w-8 h-8 text-blue-600" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Added Fields</p>
                    <p className="text-2xl font-bold text-green-600">{diffData.summary.added_fields}</p>
                  </div>
                  <TrendingUp className="w-8 h-8 text-green-600" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Removed Fields</p>
                    <p className="text-2xl font-bold text-red-600">{diffData.summary.removed_fields}</p>
                  </div>
                  <TrendingDown className="w-8 h-8 text-red-600" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Critical Changes</p>
                    <p className="text-2xl font-bold text-red-600">{diffData.summary.critical_changes}</p>
                  </div>
                  <XCircle className="w-8 h-8 text-red-600" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Filter Controls */}
          <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4" />
              <span className="text-sm font-medium">Filters:</span>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={showOnlySignificant}
                onChange={(e) => setShowOnlySignificant(e.target.checked)}
                className="rounded"
              />
              Hide low significance changes
            </label>
            <div className="flex items-center gap-2">
              <span className="text-sm">Significance:</span>
              {["critical", "high", "medium", "low"].map((sig) => (
                <label key={sig} className="flex items-center gap-1 text-sm">
                  <input
                    type="checkbox"
                    checked={!filterSignificance || filterSignificance.includes(sig)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setFilteredChanges(changes =>
                          changes.filter(c => c.significance === sig)
                        )
                      } else {
                        setFilteredChanges(changes =>
                          changes.filter(c => c.significance !== sig)
                        )
                      }
                    }}
                    className="rounded"
                  />
                  <span className="capitalize">{sig}</span>
                </label>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Changes Grouped by Section */}
      <div className="space-y-4">
        {Object.entries(groupedChanges).map(([group, changes]) => (
          <Card key={group}>
            <Collapsible
              open={expandedGroups.has(group)}
              onOpenChange={() => toggleGroup(group)}
            >
              <CollapsibleTrigger asChild>
                <CardHeader className="cursor-pointer hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {expandedGroups.has(group) ? (
                        <ChevronDown className="w-4 h-4" />
                      ) : (
                        <ChevronRight className="w-4 h-4" />
                      )}
                      <h3 className="font-semibold capitalize">{group}</h3>
                      <Badge variant="outline">{changes.length} changes</Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      {changes.some(c => c.significance === "critical") && (
                        <Badge className="bg-red-50 text-red-700 border-red-200">Critical</Badge>
                      )}
                      {changes.some(c => c.significance === "high") && (
                        <Badge className="bg-orange-50 text-orange-700 border-orange-200">High</Badge>
                      )}
                    </div>
                  </div>
                </CardHeader>
              </CollapsibleTrigger>

              <CollapsibleContent>
                <CardContent className="space-y-3">
                  {changes.map((change, index) => (
                    <div
                      key={index}
                      className={cn(
                        "p-4 border rounded-lg",
                        change.significance === "critical" && "border-red-200 bg-red-50",
                        change.significance === "high" && "border-orange-200 bg-orange-50",
                        change.significance === "medium" && "border-yellow-200 bg-yellow-50",
                        change.significance === "low" && "border-blue-200 bg-blue-50"
                      )}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          {getChangeTypeIcon(change.change_type)}
                          <span className="font-mono text-sm">{change.field_path}</span>
                          <Badge className={getSignificanceColor(change.significance)}>
                            {change.significance}
                          </Badge>
                          <Badge className={getChangeTypeColor(change.change_type)}>
                            {change.change_type}
                          </Badge>
                        </div>
                        {change.change_magnitude !== undefined && (
                          <div className="text-sm text-gray-600">
                            {change.change_magnitude.toFixed(1)}% change
                          </div>
                        )}
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {showOriginal && (
                          <div>
                            <div className="text-sm font-medium text-gray-700 mb-2">Original Value:</div>
                            <div className="p-2 bg-white border rounded text-sm">
                              {renderChangeValue(change, "old")}
                            </div>
                          </div>
                        )}
                        {showModified && (
                          <div>
                            <div className="text-sm font-medium text-gray-700 mb-2">New Value:</div>
                            <div className="p-2 bg-white border rounded text-sm">
                              {renderChangeValue(change, "new")}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        ))}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
        <div className="text-sm text-gray-600">
          {filteredBySignificance.length} of {diffData.changes.length} changes shown
        </div>
        <div className="flex items-center gap-3">
          {onReject && (
            <Button variant="destructive" onClick={onReject}>
              <XCircle className="w-4 h-4 mr-2" />
              Reject Changes
            </Button>
          )}
          {onRequestChanges && (
            <Button variant="outline" onClick={onRequestChanges}>
              <AlertCircle className="w-4 h-4 mr-2" />
              Request Changes
            </Button>
          )}
          {onApprove && (
            <Button onClick={onApprove}>
              <CheckCircle2 className="w-4 h-4 mr-2" />
              Approve Changes
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

// Export a compact version for use in cards
export function CompactDiffViewer({ diffData, onViewDetails }: {
  diffData: DiffData
  onViewDetails?: () => void
}) {
  return (
    <div className="p-4 border rounded-lg">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-semibold text-sm">{diffData.comparison_name}</h4>
        <Badge variant="outline">{diffData.summary.total_changes} changes</Badge>
      </div>
      <div className="flex items-center gap-2 text-xs text-gray-600">
        <span className="text-green-600">+{diffData.summary.added_fields}</span>
        <span className="text-red-600">-{diffData.summary.removed_fields}</span>
        <span className="text-blue-600">~{diffData.summary.modified_fields}</span>
      </div>
      {onViewDetails && (
        <Button variant="link" size="sm" className="p-0 mt-2" onClick={onViewDetails}>
          <Eye className="w-3 h-3 mr-1" />
          View Details
        </Button>
      )}
    </div>
  )
}