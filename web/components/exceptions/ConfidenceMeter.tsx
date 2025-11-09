"use client"

import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { getConfidenceColor } from "@/lib/exception-types"

interface ConfidenceMeterProps {
  confidence: number
  threshold?: number
  size?: "sm" | "md" | "lg"
  showLabel?: boolean
  showThreshold?: boolean
  className?: string
}

export function ConfidenceMeter({
  confidence,
  threshold = 0.8,
  size = "md",
  showLabel = true,
  showThreshold = false,
  className
}: ConfidenceMeterProps) {
  const confidencePercent = Math.round(confidence * 100)
  const thresholdPercent = Math.round(threshold * 100)
  const colorClass = getConfidenceColor(confidence)

  const sizeClasses = {
    sm: "h-1 text-xs",
    md: "h-2 text-sm",
    lg: "h-3 text-base"
  }

  const isAboveThreshold = confidence >= threshold

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="flex-1">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="relative">
                <Progress
                  value={confidencePercent}
                  className={cn(
                    sizeClasses[size],
                    "transition-all duration-300",
                    !isAboveThreshold && "opacity-75"
                  )}
                />
                {showThreshold && (
                  <div
                    className="absolute top-0 w-0.5 h-full bg-red-500"
                    style={{ left: `${thresholdPercent}%` }}
                  />
                )}
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <div className="text-sm space-y-1">
                <p>Confidence: {confidencePercent}%</p>
                {showThreshold && (
                  <p>Threshold: {thresholdPercent}%</p>
                )}
                <p className={cn(
                  "font-medium",
                  isAboveThreshold ? "text-green-600" : "text-red-600"
                )}>
                  {isAboveThreshold ? "Above threshold" : "Below threshold"}
                </p>
              </div>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      {showLabel && (
        <div className="flex items-center gap-1">
          <span className={cn(
            "font-medium whitespace-nowrap",
            colorClass,
            size === "sm" ? "text-xs" : size === "lg" ? "text-base" : "text-sm"
          )}>
            {confidencePercent}%
          </span>
          {!isAboveThreshold && (
            <Badge variant="destructive" className="text-xs px-1 py-0">
              Low
            </Badge>
          )}
        </div>
      )}
    </div>
  )
}

interface FieldConfidenceMeterProps {
  fieldName: string
  confidence: number
  threshold?: number
  showFieldName?: boolean
  size?: "sm" | "md"
}

export function FieldConfidenceMeter({
  fieldName,
  confidence,
  threshold = 0.8,
  showFieldName = true,
  size = "sm"
}: FieldConfidenceMeterProps) {
  const colorClass = getConfidenceColor(confidence)
  const isAboveThreshold = confidence >= threshold

  return (
    <div className="flex items-center justify-between py-1">
      {showFieldName && (
        <span className="text-sm text-slate-600 truncate mr-3">
          {fieldName}
        </span>
      )}
      <div className="flex items-center gap-2 min-w-0">
        <div className="flex-1 min-w-0">
          <Progress
            value={confidence * 100}
            className={cn(
              "h-1",
              !isAboveThreshold && "opacity-60"
            )}
          />
        </div>
        <span className={cn(
          "text-xs font-medium whitespace-nowrap",
          colorClass
        )}>
          {Math.round(confidence * 100)}%
        </span>
      </div>
    </div>
  )
}

interface ConfidenceBarProps {
  confidence: number
  threshold?: number
  height?: number
  showValue?: boolean
  animated?: boolean
}

export function ConfidenceBar({
  confidence,
  threshold = 0.8,
  height = 8,
  showValue = true,
  animated = true
}: ConfidenceBarProps) {
  const confidencePercent = Math.round(confidence * 100)
  const isAboveThreshold = confidence >= threshold
  const colorClass = getConfidenceColor(confidence)

  return (
    <div className="flex items-center gap-3">
      <div className="relative flex-1">
        <div
          className={cn(
            "bg-slate-200 rounded-full",
            animated && "transition-all duration-500"
          )}
          style={{ height }}
        >
          <div
            className={cn(
              "rounded-full",
              colorClass.replace('text-', 'bg-'),
              animated && "transition-all duration-500"
            )}
            style={{
              width: `${confidencePercent}%`,
              height
            }}
          />
          {threshold < 1 && (
            <div
              className="absolute top-0 w-0.5 h-full bg-red-500 opacity-75"
              style={{ left: `${threshold * 100}%` }}
            />
          )}
        </div>
      </div>
      {showValue && (
        <span className={cn(
          "text-sm font-medium min-w-12 text-right",
          colorClass
        )}>
          {confidencePercent}%
        </span>
      )}
    </div>
  )
}