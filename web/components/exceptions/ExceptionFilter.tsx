"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Calendar, Filter, X, Search, RotateCcw } from "lucide-react"
import { cn } from "@/lib/utils"
import { ExceptionFilterOptions, ExceptionStatus, ExceptionSeverity, ExceptionReasonCode } from "@/lib/exception-types"

interface ExceptionFilterProps {
  filters: ExceptionFilterOptions
  onFiltersChange: (filters: ExceptionFilterOptions) => void
  onClearFilters: () => void
  className?: string
}

export function ExceptionFilter({
  filters,
  onFiltersChange,
  onClearFilters,
  className
}: ExceptionFilterProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const statusOptions: { value: ExceptionStatus; label: string }[] = [
    { value: "open", label: "Open" },
    { value: "in_progress", label: "In Progress" },
    { value: "resolved", label: "Resolved" },
    { value: "escalated", label: "Escalated" },
    { value: "closed", label: "Closed" },
  ]

  const severityOptions: { value: ExceptionSeverity; label: string }[] = [
    { value: "low", label: "Low" },
    { value: "medium", label: "Medium" },
    { value: "high", label: "High" },
    { value: "critical", label: "Critical" },
  ]

  const reasonCodeOptions: { value: ExceptionReasonCode; label: string }[] = [
    { value: "low_confidence_extraction", label: "Low Confidence Extraction" },
    { value: "missing_required_fields", label: "Missing Required Fields" },
    { value: "vendor_not_found", label: "Vendor Not Found" },
    { value: "amount_mismatch", label: "Amount Mismatch" },
    { value: "date_validation_failed", label: "Date Validation Failed" },
    { value: "duplicate_invoice", label: "Duplicate Invoice" },
    { value: "business_rule_violation", label: "Business Rule Violation" },
    { value: "document_quality_poor", label: "Poor Document Quality" },
    { value: "currency_mismatch", label: "Currency Mismatch" },
    { value: "tax_calculation_error", label: "Tax Calculation Error" },
    { value: "invalid_invoice_format", label: "Invalid Invoice Format" },
    { value: "reference_data_mismatch", label: "Reference Data Mismatch" },
    { value: "payment_terms_invalid", label: "Invalid Payment Terms" },
    { value: "po_number_mismatch", label: "PO Number Mismatch" },
    { value: "accounting_period_closed", label: "Accounting Period Closed" },
    { value: "approval_required", label: "Approval Required" },
    { value: "custom_validation_failed", label: "Custom Validation Failed" },
  ]

  const handleSearchChange = (value: string) => {
    onFiltersChange({ ...filters, search: value })
  }

  const handleStatusChange = (status: ExceptionStatus, checked: boolean) => {
    const currentStatuses = filters.status || []
    const newStatuses = checked
      ? [...currentStatuses, status]
      : currentStatuses.filter(s => s !== status)
    onFiltersChange({ ...filters, status: newStatuses })
  }

  const handleSeverityChange = (severity: ExceptionSeverity, checked: boolean) => {
    const currentSeverities = filters.severity || []
    const newSeverities = checked
      ? [...currentSeverities, severity]
      : currentSeverities.filter(s => s !== severity)
    onFiltersChange({ ...filters, severity: newSeverities })
  }

  const handleReasonCodeChange = (reasonCode: ExceptionReasonCode, checked: boolean) => {
    const currentReasonCodes = filters.reason_code || []
    const newReasonCodes = checked
      ? [...currentReasonCodes, reasonCode]
      : currentReasonCodes.filter(r => r !== reasonCode)
    onFiltersChange({ ...filters, reason_code: newReasonCodes })
  }

  const handleDateRangeChange = (range: string) => {
    let dateRange = undefined
    const now = new Date()

    switch (range) {
      case "today":
        dateRange = {
          start: new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString(),
          end: now.toISOString()
        }
        break
      case "week":
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
        dateRange = { start: weekAgo.toISOString(), end: now.toISOString() }
        break
      case "month":
        const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
        dateRange = { start: monthAgo.toISOString(), end: now.toISOString() }
        break
      case "quarter":
        const quarterAgo = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000)
        dateRange = { start: quarterAgo.toISOString(), end: now.toISOString() }
        break
    }

    onFiltersChange({ ...filters, date_range: dateRange })
  }

  const handleConfidenceRangeChange = (field: 'min' | 'max', value: string) => {
    const numValue = parseFloat(value)
    if (isNaN(numValue)) return

    const currentRange = filters.confidence_range || {}
    const newRange = { ...currentRange, [field]: numValue }

    // Ensure min <= max
    if (field === 'min' && currentRange.max !== undefined && numValue > currentRange.max) {
      newRange.max = numValue
    } else if (field === 'max' && currentRange.min !== undefined && numValue < currentRange.min) {
      newRange.min = numValue
    }

    onFiltersChange({ ...filters, confidence_range: newRange })
  }

  const getActiveFilterCount = () => {
    let count = 0
    if (filters.search) count++
    if (filters.status?.length) count++
    if (filters.severity?.length) count++
    if (filters.reason_code?.length) count++
    if (filters.date_range) count++
    if (filters.confidence_range?.min !== undefined || filters.confidence_range?.max !== undefined) count++
    if (filters.assigned_to?.length) count++
    if (filters.tags?.length) count++
    return count
  }

  const activeFilterCount = getActiveFilterCount()

  return (
    <Card className={cn("", className)}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CardTitle className="text-lg">Filters</CardTitle>
            {activeFilterCount > 0 && (
              <Badge variant="secondary">
                {activeFilterCount} active
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            {activeFilterCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onClearFilters}
                className="text-slate-600"
              >
                <RotateCcw className="w-4 h-4 mr-1" />
                Clear All
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
            >
              <Filter className="w-4 h-4 mr-1" />
              {isExpanded ? "Hide" : "Show"}
            </Button>
          </div>
        </div>
      </CardHeader>

      {/* Quick Search - Always Visible */}
      <CardContent className="pt-0">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search exceptions..."
            value={filters.search || ""}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-10"
          />
        </div>
      </CardContent>

      {/* Detailed Filters - Expandable */}
      {isExpanded && (
        <CardContent className="space-y-6 border-t pt-6">
          {/* Status Filter */}
          <div>
            <h4 className="font-medium mb-3">Status</h4>
            <div className="flex flex-wrap gap-3">
              {statusOptions.map((option) => (
                <div key={option.value} className="flex items-center space-x-2">
                  <Checkbox
                    id={`status-${option.value}`}
                    checked={filters.status?.includes(option.value) || false}
                    onCheckedChange={(checked) => handleStatusChange(option.value, checked as boolean)}
                  />
                  <label
                    htmlFor={`status-${option.value}`}
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                  >
                    {option.label}
                  </label>
                </div>
              ))}
            </div>
          </div>

          {/* Severity Filter */}
          <div>
            <h4 className="font-medium mb-3">Severity</h4>
            <div className="flex flex-wrap gap-3">
              {severityOptions.map((option) => (
                <div key={option.value} className="flex items-center space-x-2">
                  <Checkbox
                    id={`severity-${option.value}`}
                    checked={filters.severity?.includes(option.value) || false}
                    onCheckedChange={(checked) => handleSeverityChange(option.value, checked as boolean)}
                  />
                  <label
                    htmlFor={`severity-${option.value}`}
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                  >
                    {option.label}
                  </label>
                </div>
              ))}
            </div>
          </div>

          {/* Date Range Filter */}
          <div>
            <h4 className="font-medium mb-3">Date Range</h4>
            <Select onValueChange={handleDateRangeChange}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select date range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="today">Today</SelectItem>
                <SelectItem value="week">Last 7 Days</SelectItem>
                <SelectItem value="month">Last 30 Days</SelectItem>
                <SelectItem value="quarter">Last 90 Days</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Confidence Range Filter */}
          <div>
            <h4 className="font-medium mb-3">Confidence Range</h4>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <label className="text-xs text-slate-600 block mb-1">Min</label>
                <Input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  placeholder="0.0"
                  value={filters.confidence_range?.min ?? ""}
                  onChange={(e) => handleConfidenceRangeChange('min', e.target.value)}
                  className="text-sm"
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-slate-600 block mb-1">Max</label>
                <Input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  placeholder="1.0"
                  value={filters.confidence_range?.max ?? ""}
                  onChange={(e) => handleConfidenceRangeChange('max', e.target.value)}
                  className="text-sm"
                />
              </div>
            </div>
          </div>

          {/* Reason Codes Filter */}
          <div>
            <h4 className="font-medium mb-3">Exception Reasons</h4>
            <div className="max-h-48 overflow-y-auto space-y-2">
              {reasonCodeOptions.map((option) => (
                <div key={option.value} className="flex items-center space-x-2">
                  <Checkbox
                    id={`reason-${option.value}`}
                    checked={filters.reason_code?.includes(option.value) || false}
                    onCheckedChange={(checked) => handleReasonCodeChange(option.value, checked as boolean)}
                  />
                  <label
                    htmlFor={`reason-${option.value}`}
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                  >
                    {option.label}
                  </label>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}