"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Bell,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Info,
  FileText,
  MessageSquare,
  User,
  DollarSign,
  Clock,
  Settings,
  Archive,
  MarkAsUnread,
  Eye,
  EyeOff,
  Filter,
  Search,
  RefreshCw,
  Wifi,
  WifiOff,
  Volume2,
  VolumeX,
  Mail,
  Phone,
  Calendar,
  Download,
  Upload,
  Star,
  MoreHorizontal,
  ChevronRight,
  Zap,
  Target,
  TrendingUp,
  BarChart3,
  Users,
  Shield,
  Key,
  Activity,
  CheckSquare,
  Square
} from "lucide-react"
import { cn } from "@/lib/utils"

// Types
interface Notification {
  id: string
  type: "invoice" | "approval" | "exception" | "system" | "export" | "reminder"
  title: string
  message: string
  severity: "low" | "medium" | "high" | "urgent"
  timestamp: string
  read: boolean
  actionUrl?: string
  actionText?: string
  metadata?: Record<string, any>
  source: string
  category: string
}

interface NotificationSettings {
  enabled: boolean
  email: boolean
  push: boolean
  sound: boolean
  desktop: boolean
  quietHours: {
    enabled: boolean
    start: string
    end: string
  }
  categories: Record<string, boolean>
}

export function NotificationCenter() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [isConnected, setIsConnected] = useState(true)
  const [settings, setSettings] = useState<NotificationSettings>({
    enabled: true,
    email: true,
    push: true,
    sound: true,
    desktop: true,
    quietHours: {
      enabled: false,
      start: "22:00",
      end: "08:00"
    },
    categories: {
      invoice: true,
      approval: true,
      exception: true,
      system: true,
      export: false,
      reminder: true
    }
  })
  const [filter, setFilter] = useState("all")
  const [searchTerm, setSearchTerm] = useState("")

  // Mock notifications
  const mockNotifications: Notification[] = [
    {
      id: "1",
      type: "invoice",
      title: "New Invoice Ready for Review",
      message: "Invoice INV-2024-5647 from Acme Corp requires your review",
      severity: "medium",
      timestamp: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      read: false,
      actionUrl: "/invoices?tab=review&invoice=INV-2024-5647",
      actionText: "Review Now",
      metadata: {
        invoiceId: "INV-2024-5647",
        vendorName: "Acme Corp",
        amount: 12450.50
      },
      source: "Document Processing",
      category: "invoice"
    },
    {
      id: "2",
      type: "approval",
      title: "Approval Required",
      message: "Invoice amount exceeds your approval limit ($15,000 > $10,000)",
      severity: "high",
      timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
      read: false,
      actionUrl: "/invoices?tab=approvals&request=REQ-1234",
      actionText: "View Request",
      metadata: {
        requestId: "REQ-1234",
        requester: "Mike Davis",
        amount: 15000
      },
      source: "Approval Workflow",
      category: "approval"
    },
    {
      id: "3",
      type: "exception",
      title: "Exception Detected",
      message: "Vendor information mismatch detected in invoice INV-2024-5648",
      severity: "urgent",
      timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
      read: false,
      actionUrl: "/invoices?tab=exceptions&exception=EX-5678",
      actionText: "Resolve Exception",
      metadata: {
        exceptionId: "EX-5678",
        invoiceId: "INV-2024-5648",
        ruleName: "Vendor Mismatch"
      },
      source: "Validation Engine",
      category: "exception"
    },
    {
      id: "4",
      type: "export",
      title: "Export Completed",
      message: "Daily invoice export completed successfully (23 records)",
      severity: "low",
      timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
      read: true,
      actionUrl: "/invoices?tab=exports&job=JOB-9876",
      actionText: "Download File",
      metadata: {
        jobId: "JOB-9876",
        recordCount: 23,
        fileSize: "156KB"
      },
      source: "Export Service",
      category: "export"
    },
    {
      id: "5",
      type: "system",
      title: "System Update",
      message: "Invoice processing system will be updated tonight at 2 AM EST",
      severity: "low",
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
      read: true,
      metadata: {
        scheduledTime: "2024-11-07T02:00:00Z",
        duration: "30 minutes"
      },
      source: "System Administration",
      category: "system"
    }
  ]

  useEffect(() => {
    setNotifications(mockNotifications)
    setUnreadCount(mockNotifications.filter(n => !n.read).length)

    // Simulate real-time updates
    const interval = setInterval(() => {
      const newNotification: Notification = {
        id: Date.now().toString(),
        type: "invoice",
        title: "New Invoice Uploaded",
        message: `Invoice INV-${Math.floor(Math.random() * 9000) + 1000} has been uploaded and is being processed`,
        severity: "low",
        timestamp: new Date().toISOString(),
        read: false,
        source: "Document Upload",
        category: "invoice"
      }

      if (settings.categories[newNotification.type]) {
        setNotifications(prev => [newNotification, ...prev].slice(0, 50))
        setUnreadCount(prev => prev + 1)
      }
    }, 30000) // Every 30 seconds

    return () => clearInterval(interval)
  }, [settings.categories])

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "urgent":
        return "bg-red-50 text-red-700 border-red-200"
      case "high":
        return "bg-orange-50 text-orange-700 border-orange-200"
      case "medium":
        return "bg-yellow-50 text-yellow-700 border-yellow-200"
      default:
        return "bg-blue-50 text-blue-700 border-blue-200"
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "invoice":
        return <FileText className="w-4 h-4" />
      case "approval":
        return <CheckCircle2 className="w-4 h-4" />
      case "exception":
        return <AlertTriangle className="w-4 h-4" />
      case "export":
        return <Download className="w-4 h-4" />
      case "system":
        return <Info className="w-4 h-4" />
      default:
        return <Bell className="w-4 h-4" />
    }
  }

  const markAsRead = (notificationId: string) => {
    setNotifications(prev =>
      prev.map(n =>
        n.id === notificationId ? { ...n, read: true } : n
      )
    )
    setUnreadCount(prev => Math.max(0, prev - 1))
  }

  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })))
    setUnreadCount(0)
  }

  const deleteNotification = (notificationId: string) => {
    const notification = notifications.find(n => n.id === notificationId)
    setNotifications(prev => prev.filter(n => n.id !== notificationId))
    if (notification && !notification.read) {
      setUnreadCount(prev => Math.max(0, prev - 1))
    }
  }

  const filteredNotifications = notifications.filter(notification => {
    const matchesSearch = notification.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         notification.message.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesFilter = filter === "all" || notification.type === filter
    return matchesSearch && matchesFilter
  })

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)

    if (diffMins < 1) return "Just now"
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="flex items-center gap-4">
      {/* Connection Status */}
      <div className="flex items-center gap-2">
        {isConnected ? (
          <div className="flex items-center gap-1 text-green-600">
            <Wifi className="w-4 h-4" />
            <span className="text-xs font-medium">Connected</span>
          </div>
        ) : (
          <div className="flex items-center gap-1 text-red-600">
            <WifiOff className="w-4 h-4" />
            <span className="text-xs font-medium">Offline</span>
          </div>
        )}
      </div>

      {/* Notifications Dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="relative">
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <Badge
                variant="destructive"
                className="absolute -top-2 -right-2 h-5 w-5 rounded-full p-0 text-xs flex items-center justify-center"
              >
                {unreadCount > 99 ? "99+" : unreadCount}
              </Badge>
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-96">
          <DropdownMenuLabel className="flex items-center justify-between">
            <span>Notifications</span>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={markAllAsRead}
                  className="text-xs h-auto p-1"
                >
                  Mark all read
                </Button>
              )}
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="text-xs h-auto p-1">
                  <Settings className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />

          {/* Filter and Search */}
          <div className="p-3 space-y-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search notifications..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm border rounded-md"
              />
            </div>
            <div className="flex gap-1">
              {["all", "invoice", "approval", "exception", "export", "system"].map((type) => (
                <Button
                  key={type}
                  variant={filter === type ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setFilter(type)}
                  className="text-xs h-auto p-1 capitalize"
                >
                  {type}
                </Button>
              ))}
            </div>
          </div>

          <DropdownMenuSeparator />

          {/* Notifications List */}
          <ScrollArea className="h-80">
            {filteredNotifications.length === 0 ? (
              <div className="p-8 text-center text-slate-500">
                <Bell className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                <p className="text-sm">No notifications</p>
              </div>
            ) : (
              <div className="space-y-1">
                {filteredNotifications.map((notification) => (
                  <div
                    key={notification.id}
                    className={cn(
                      "p-3 hover:bg-slate-50 cursor-pointer transition-colors",
                      !notification.read && "bg-blue-50"
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <div className={cn(
                        "mt-1",
                        !notification.read && "text-blue-600"
                      )}>
                        {getTypeIcon(notification.type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <h4 className={cn(
                              "text-sm font-medium truncate",
                              !notification.read && "font-semibold"
                            )}>
                              {notification.title}
                            </h4>
                            <p className="text-xs text-slate-600 mt-1 line-clamp-2">
                              {notification.message}
                            </p>
                            <div className="flex items-center gap-2 mt-2">
                              <span className="text-xs text-slate-500">
                                {formatTimestamp(notification.timestamp)}
                              </span>
                              <Badge className={getSeverityColor(notification.severity)}>
                                {notification.severity}
                              </Badge>
                              <span className="text-xs text-slate-400">
                                {notification.source}
                              </span>
                            </div>
                            {notification.actionText && (
                              <Button
                                variant="link"
                                size="sm"
                                className="p-0 h-auto text-xs mt-2"
                                onClick={() => markAsRead(notification.id)}
                              >
                                {notification.actionText}
                                <ChevronRight className="w-3 h-3 ml-1" />
                              </Button>
                            )}
                          </div>
                          <div className="flex items-center gap-1 ml-2">
                            {!notification.read && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => markAsRead(notification.id)}
                                className="h-auto p-1"
                              >
                                <Eye className="w-3 h-3" />
                              </Button>
                            )}
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm" className="h-auto p-1">
                                <MoreHorizontal className="w-3 h-3" />
                              </Button>
                            </DropdownMenuTrigger>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>

          <DropdownMenuSeparator />
          <div className="p-2">
            <Button variant="ghost" size="sm" className="w-full justify-start">
              <Eye className="w-4 h-4 mr-2" />
              View All Notifications
            </Button>
          </div>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Notification Settings Dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm">
            <Settings className="w-4 h-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-80">
          <DropdownMenuLabel>Notification Settings</DropdownMenuLabel>
          <DropdownMenuSeparator />

          <div className="p-3 space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Enable Notifications</span>
                <button
                  onClick={() => setSettings(prev => ({ ...prev, enabled: !prev.enabled }))}
                  className={cn(
                    "w-10 h-6 rounded-full transition-colors",
                    settings.enabled ? "bg-blue-600" : "bg-slate-300"
                  )}
                >
                  <div className={cn(
                    "w-4 h-4 bg-white rounded-full transition-transform",
                    settings.enabled ? "translate-x-5" : "translate-x-1"
                  )} />
                </button>
              </div>

              <div className="space-y-2">
                <h4 className="text-sm font-medium">Notification Channels</h4>
                {[
                  { key: "email", label: "Email", icon: Mail },
                  { key: "push", label: "Push", icon: Bell },
                  { key: "sound", label: "Sound", icon: Volume2 },
                  { key: "desktop", label: "Desktop", icon: Monitor }
                ].map(({ key, label, icon: Icon }) => (
                  <div key={key} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Icon className="w-4 h-4 text-slate-600" />
                      <span className="text-sm">{label}</span>
                    </div>
                    <button
                      onClick={() => setSettings(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }))}
                      className={cn(
                        "w-8 h-5 rounded-full transition-colors",
                        settings[key as keyof typeof prev] ? "bg-blue-600" : "bg-slate-300"
                      )}
                    >
                      <div className={cn(
                        "w-3 h-3 bg-white rounded-full transition-transform",
                        settings[key as keyof typeof prev] ? "translate-x-4" : "translate-x-1"
                      )} />
                    </button>
                  </div>
                ))}
              </div>

              <div className="space-y-2">
                <h4 className="text-sm font-medium">Categories</h4>
                {Object.entries(settings.categories).map(([key, enabled]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-sm capitalize">{key}</span>
                    <button
                      onClick={() => setSettings(prev => ({
                        ...prev,
                        categories: {
                          ...prev.categories,
                          [key]: !prev.categories[key]
                        }
                      }))}
                      className={cn(
                        "w-8 h-5 rounded-full transition-colors",
                        enabled ? "bg-blue-600" : "bg-slate-300"
                      )}
                    >
                      <div className={cn(
                        "w-3 h-3 bg-white rounded-full transition-transform",
                        enabled ? "translate-x-4" : "translate-x-1"
                      )} />
                    </button>
                  </div>
                ))}
              </div>

              <div className="space-y-2">
                <h4 className="text-sm font-medium">Quiet Hours</h4>
                <div className="flex items-center justify-between">
                  <span className="text-sm">Enable quiet hours</span>
                  <button
                    onClick={() => setSettings(prev => ({
                      ...prev,
                      quietHours: {
                        ...prev.quietHours,
                        enabled: !prev.quietHours.enabled
                      }
                    }))}
                    className={cn(
                      "w-8 h-5 rounded-full transition-colors",
                      settings.quietHours.enabled ? "bg-blue-600" : "bg-slate-300"
                    )}
                  >
                    <div className={cn(
                      "w-3 h-3 bg-white rounded-full transition-transform",
                      settings.quietHours.enabled ? "translate-x-4" : "translate-x-1"
                    )} />
                  </button>
                </div>
                {settings.quietHours.enabled && (
                  <div className="flex items-center gap-2 text-sm">
                    <input
                      type="time"
                      value={settings.quietHours.start}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        quietHours: { ...prev.quietHours, start: e.target.value }
                      }))}
                      className="px-2 py-1 border rounded"
                    />
                    <span>to</span>
                    <input
                      type="time"
                      value={settings.quietHours.end}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        quietHours: { ...prev.quietHours, end: e.target.value }
                      }))}
                      className="px-2 py-1 border rounded"
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

// Add Monitor icon import
const Monitor = ({ className }: { className?: string }) => (
  <svg
    className={className}
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
    <line x1="8" y1="21" x2="16" y2="21" />
    <line x1="12" y1="17" x2="12" y2="21" />
  </svg>
)