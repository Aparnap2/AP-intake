"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Checkbox } from "@/components/ui/checkbox"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Progress } from "@/components/ui/progress"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Mail,
  Plus,
  Search,
  Filter,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  Eye,
  Settings,
  Play,
  Pause,
  Trash2,
  MoreHorizontal,
  Calendar,
  Paperclip,
  Shield,
  TrendingUp,
  TrendingDown,
  Users,
  FileCheck,
  AlertTriangle,
  Link,
  Zap,
  Activity,
  BarChart3,
  Globe,
  Inbox,
  Send,
  Download,
  ExternalLink,
  Lock,
  Unlock,
  CheckSquare,
  Square,
  Archive,
  Copy,
  Share2,
  Wifi,
  WifiOff,
  Database,
  Server,
  Cpu,
  X
} from "lucide-react"
import { cn } from "@/lib/utils"
import { GmailIcon } from "@/components/icons/GmailIcon"
import { GmailOAuthDialog } from "@/components/email/GmailOAuthDialog"
import { EmailProcessingMonitor } from "@/components/email/EmailProcessingMonitor"
import { EmailConfigurationPanel } from "@/components/email/EmailConfigurationPanel"

// Types
interface EmailAccount {
  id: string
  provider: "gmail" | "outlook"
  email: string
  displayName: string
  isActive: boolean
  isConnected: boolean
  lastSync: string
  totalEmails: number
  processedEmails: number
  autoProcessingEnabled: boolean
  securityLevel: "low" | "medium" | "high"
  oauthState?: "connected" | "expired" | "revoked"
}

interface EmailProcessingJob {
  id: string
  accountId: string
  status: "pending" | "running" | "completed" | "failed" | "cancelled"
  startedAt: string
  completedAt?: string
  emailsProcessed: number
  totalEmails: number
  invoicesFound: number
  errors: string[]
  progress: number
}

interface EmailFilter {
  search: string
  status: string[]
  provider: string[]
  securityLevel: string[]
}

const mockEmailAccounts: EmailAccount[] = [
  {
    id: "1",
    provider: "gmail",
    email: "accounts@acmecorp.com",
    displayName: "Acme Corp Accounts",
    isActive: true,
    isConnected: true,
    lastSync: "2024-11-06T14:30:00Z",
    totalEmails: 15420,
    processedEmails: 14850,
    autoProcessingEnabled: true,
    securityLevel: "high",
    oauthState: "connected"
  },
  {
    id: "2",
    provider: "gmail",
    email: "invoices@acmecorp.com",
    displayName: "Invoice Processing",
    isActive: true,
    isConnected: true,
    lastSync: "2024-11-06T14:25:00Z",
    totalEmails: 8230,
    processedEmails: 8100,
    autoProcessingEnabled: true,
    securityLevel: "medium",
    oauthState: "connected"
  },
  {
    id: "3",
    provider: "gmail",
    email: "vendor-relations@acmecorp.com",
    displayName: "Vendor Relations",
    isActive: false,
    isConnected: false,
    lastSync: "2024-11-05T09:15:00Z",
    totalEmails: 5680,
    processedEmails: 5420,
    autoProcessingEnabled: false,
    securityLevel: "low",
    oauthState: "expired"
  }
]

const mockProcessingJobs: EmailProcessingJob[] = [
  {
    id: "job_1",
    accountId: "1",
    status: "running",
    startedAt: "2024-11-06T14:30:00Z",
    emailsProcessed: 45,
    totalEmails: 120,
    invoicesFound: 8,
    errors: [],
    progress: 37.5
  },
  {
    id: "job_2",
    accountId: "2",
    status: "completed",
    startedAt: "2024-11-06T13:45:00Z",
    completedAt: "2024-11-06T14:20:00Z",
    emailsProcessed: 89,
    totalEmails: 89,
    invoicesFound: 12,
    errors: [],
    progress: 100
  },
  {
    id: "job_3",
    accountId: "3",
    status: "failed",
    startedAt: "2024-11-06T12:30:00Z",
    completedAt: "2024-11-06T12:45:00Z",
    emailsProcessed: 15,
    totalEmails: 200,
    invoicesFound: 0,
    errors: ["Authentication failed", "Rate limit exceeded"],
    progress: 7.5
  }
]

export default function EmailIntegrationDashboard() {
  const [emailAccounts, setEmailAccounts] = useState<EmailAccount[]>(mockEmailAccounts)
  const [processingJobs, setProcessingJobs] = useState<EmailProcessingJob[]>(mockProcessingJobs)
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([])
  const [filters, setFilters] = useState<EmailFilter>({
    search: "",
    status: [],
    provider: [],
    securityLevel: []
  })
  const [showFilters, setShowFilters] = useState(false)
  const [showOAuthDialog, setShowOAuthDialog] = useState(false)
  const [activeTab, setActiveTab] = useState("accounts")
  const [loading, setLoading] = useState(false)

  // Calculate statistics
  const stats = {
    totalAccounts: emailAccounts.length,
    activeAccounts: emailAccounts.filter(acc => acc.isActive).length,
    connectedAccounts: emailAccounts.filter(acc => acc.isConnected).length,
    totalEmails: emailAccounts.reduce((sum, acc) => sum + acc.totalEmails, 0),
    processedEmails: emailAccounts.reduce((sum, acc) => sum + acc.processedEmails, 0),
    activeJobs: processingJobs.filter(job => job.status === "running").length,
    completedJobs: processingJobs.filter(job => job.status === "completed").length,
    failedJobs: processingJobs.filter(job => job.status === "failed").length,
    totalInvoicesFound: processingJobs.reduce((sum, job) => sum + job.invoicesFound, 0)
  }

  const getProviderIcon = (provider: string) => {
    switch (provider) {
      case "gmail":
        return <GmailIcon className="w-4 h-4" />
      case "outlook":
        return <Globe className="w-4 h-4" />
      default:
        return <Mail className="w-4 h-4" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running":
        return "bg-blue-50 text-blue-700 border-blue-200"
      case "completed":
        return "bg-green-50 text-green-700 border-green-200"
      case "failed":
        return "bg-red-50 text-red-700 border-red-200"
      case "cancelled":
        return "bg-gray-50 text-gray-700 border-gray-200"
      default:
        return "bg-yellow-50 text-yellow-700 border-yellow-200"
    }
  }

  const getSecurityLevelColor = (level: string) => {
    switch (level) {
      case "high":
        return "bg-green-100 text-green-800"
      case "medium":
        return "bg-yellow-100 text-yellow-800"
      default:
        return "bg-red-100 text-red-800"
    }
  }

  const getOAuthStateIcon = (state?: string) => {
    switch (state) {
      case "connected":
        return <CheckCircle2 className="w-4 h-4 text-green-600" />
      case "expired":
        return <AlertTriangle className="w-4 h-4 text-yellow-600" />
      case "revoked":
        return <X className="w-4 h-4 text-red-600" />
      default:
        return <AlertCircle className="w-4 h-4 text-gray-600" />
    }
  }

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedAccounts(filteredAccounts.map(acc => acc.id))
    } else {
      setSelectedAccounts([])
    }
  }

  const handleSelectAccount = (accountId: string, checked: boolean) => {
    if (checked) {
      setSelectedAccounts(prev => [...prev, accountId])
    } else {
      setSelectedAccounts(prev => prev.filter(id => id !== accountId))
    }
  }

  const handleToggleAccount = (accountId: string) => {
    setEmailAccounts(prev => prev.map(acc =>
      acc.id === accountId ? { ...acc, isActive: !acc.isActive } : acc
    ))
  }

  const handleRefreshAccounts = async () => {
    setLoading(true)
    // Simulate API call
    setTimeout(() => {
      setEmailAccounts(prev => prev.map(acc => ({
        ...acc,
        lastSync: new Date().toISOString()
      })))
      setLoading(false)
    }, 1500)
  }

  const filteredAccounts = emailAccounts.filter(account => {
    if (filters.search && !account.email.toLowerCase().includes(filters.search.toLowerCase()) &&
        !account.displayName.toLowerCase().includes(filters.search.toLowerCase())) {
      return false
    }
    if (filters.provider.length > 0 && !filters.provider.includes(account.provider)) {
      return false
    }
    if (filters.securityLevel.length > 0 && !filters.securityLevel.includes(account.securityLevel)) {
      return false
    }
    return true
  })

  if (loading && activeTab === "accounts") {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="text-center space-y-4">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-blue-600" />
          <p className="text-slate-600">Syncing email accounts...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Email Integration</h1>
          <p className="text-slate-600">Manage email sources and automatic invoice processing</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={handleRefreshAccounts}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={() => setShowOAuthDialog(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Add Email Account
          </Button>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Connected Accounts</CardTitle>
            <Inbox className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.connectedAccounts}/{stats.totalAccounts}</div>
            <p className="text-xs text-muted-foreground">
              {stats.activeAccounts} actively processing
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Emails Processed</CardTitle>
            <Mail className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.processedEmails.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              {Math.round((stats.processedEmails / stats.totalEmails) * 100)}% of total
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Jobs</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.activeJobs}</div>
            <p className="text-xs text-muted-foreground">
              {stats.completedJobs} completed today
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Invoices Found</CardTitle>
            <FileCheck className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.totalInvoicesFound}</div>
            <p className="text-xs text-muted-foreground">
              From recent processing
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="accounts">Email Accounts</TabsTrigger>
          <TabsTrigger value="processing">Processing Queue</TabsTrigger>
          <TabsTrigger value="monitor">Monitor</TabsTrigger>
          <TabsTrigger value="settings">Configuration</TabsTrigger>
        </TabsList>

        {/* Email Accounts Tab */}
        <TabsContent value="accounts" className="space-y-4">
          {/* Filters and Search */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 flex-1">
                  <div className="relative flex-1 max-w-md">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                      placeholder="Search email accounts..."
                      value={filters.search}
                      onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                      className="pl-10"
                    />
                  </div>

                  <Button
                    variant="outline"
                    onClick={() => setShowFilters(!showFilters)}
                    className="flex items-center gap-2"
                  >
                    <Filter className="w-4 h-4" />
                    Filters
                    {(filters.provider.length > 0 || filters.securityLevel.length > 0) && (
                      <Badge variant="secondary" className="ml-1">
                        {filters.provider.length + filters.securityLevel.length}
                      </Badge>
                    )}
                  </Button>
                </div>

                {selectedAccounts.length > 0 && (
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-slate-600">
                      {selectedAccounts.length} selected
                    </span>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="sm">
                          <MoreHorizontal className="w-4 h-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem>
                          <Play className="w-4 h-4 mr-2" />
                          Start Processing
                        </DropdownMenuItem>
                        <DropdownMenuItem>
                          <Pause className="w-4 h-4 mr-2" />
                          Pause Processing
                        </DropdownMenuItem>
                        <DropdownMenuItem>
                          <RefreshCw className="w-4 h-4 mr-2" />
                          Sync Now
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem>
                          <Settings className="w-4 h-4 mr-2" />
                          Configure Settings
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem className="text-red-600">
                          <Trash2 className="w-4 h-4 mr-2" />
                          Remove Account
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                )}
              </div>

              {showFilters && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t">
                  <div>
                    <label className="text-sm font-medium mb-2 block">Provider</label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="All providers" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="gmail">Gmail</SelectItem>
                        <SelectItem value="outlook">Outlook</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <label className="text-sm font-medium mb-2 block">Security Level</label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="All levels" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="high">High</SelectItem>
                        <SelectItem value="medium">Medium</SelectItem>
                        <SelectItem value="low">Low</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <label className="text-sm font-medium mb-2 block">Connection Status</label>
                    <Select>
                      <SelectTrigger>
                        <SelectValue placeholder="All statuses" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="connected">Connected</SelectItem>
                        <SelectItem value="disconnected">Disconnected</SelectItem>
                        <SelectItem value="expired">Expired</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}
            </CardHeader>
          </Card>

          {/* Email Accounts Table */}
          <Card>
            <CardHeader>
              <CardTitle>Email Accounts ({filteredAccounts.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">
                        <Checkbox
                          checked={selectedAccounts.length === filteredAccounts.length}
                          onCheckedChange={handleSelectAll}
                        />
                      </TableHead>
                      <TableHead>Account</TableHead>
                      <TableHead>Provider</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Processing</TableHead>
                      <TableHead>Security</TableHead>
                      <TableHead>Last Sync</TableHead>
                      <TableHead className="w-12"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredAccounts.map((account) => (
                      <TableRow
                        key={account.id}
                        className={cn(
                          "cursor-pointer hover:bg-slate-50",
                          selectedAccounts.includes(account.id) && "bg-blue-50"
                        )}
                      >
                        <TableCell>
                          <Checkbox
                            checked={selectedAccounts.includes(account.id)}
                            onCheckedChange={(checked) => handleSelectAccount(account.id, checked as boolean)}
                          />
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <Avatar className="h-8 w-8">
                              <AvatarImage src={`/avatars/${account.email}.jpg`} />
                              <AvatarFallback>
                                {account.email.substring(0, 2).toUpperCase()}
                              </AvatarFallback>
                            </Avatar>
                            <div>
                              <div className="font-medium">{account.displayName}</div>
                              <div className="text-sm text-slate-500">{account.email}</div>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getProviderIcon(account.provider)}
                            <span className="capitalize">{account.provider}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {account.isConnected ? (
                              <Wifi className="w-4 h-4 text-green-600" />
                            ) : (
                              <WifiOff className="w-4 h-4 text-red-600" />
                            )}
                            <div className="flex items-center gap-1">
                              {getOAuthStateIcon(account.oauthState)}
                              <span className="text-sm">
                                {account.isConnected ? "Connected" : "Disconnected"}
                              </span>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <Switch
                                checked={account.isActive}
                                onCheckedChange={() => handleToggleAccount(account.id)}
                              />
                              <span className="text-sm">
                                {account.isActive ? "Active" : "Paused"}
                              </span>
                            </div>
                            <div className="text-xs text-slate-500">
                              {account.processedEmails.toLocaleString()} / {account.totalEmails.toLocaleString()} emails
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge className={getSecurityLevelColor(account.securityLevel)} variant="secondary">
                            {account.securityLevel}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            {new Date(account.lastSync).toLocaleString()}
                          </div>
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm">
                                <MoreHorizontal className="w-4 h-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem>
                                <Eye className="w-4 h-4 mr-2" />
                                View Details
                              </DropdownMenuItem>
                              <DropdownMenuItem>
                                <RefreshCw className="w-4 h-4 mr-2" />
                                Sync Now
                              </DropdownMenuItem>
                              <DropdownMenuItem>
                                <Settings className="w-4 h-4 mr-2" />
                                Configure
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem>
                                <ExternalLink className="w-4 h-4 mr-2" />
                                Open Gmail
                              </DropdownMenuItem>
                              <DropdownMenuItem className="text-red-600">
                                <Trash2 className="w-4 h-4 mr-2" />
                                Remove
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Processing Queue Tab */}
        <TabsContent value="processing" className="space-y-4">
          <EmailProcessingMonitor jobs={processingJobs} />
        </TabsContent>

        {/* Monitor Tab */}
        <TabsContent value="monitor" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Activity className="w-5 h-5" />
                  Real-time Processing
                </CardTitle>
                <CardDescription>
                  Live monitoring of email processing activities
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <Alert className="border-blue-200 bg-blue-50">
                    <Zap className="h-4 w-4 text-blue-600" />
                    <AlertTitle>Processing Active</AlertTitle>
                    <AlertDescription>
                      3 jobs currently running • 45 emails processed in last hour
                    </AlertDescription>
                  </Alert>

                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">Processing Rate</span>
                      <span className="text-sm text-slate-600">12.5 emails/min</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">Success Rate</span>
                      <span className="text-sm text-green-600">94.2%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">Avg Processing Time</span>
                      <span className="text-sm text-slate-600">2.3s/email</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-sm font-medium">Invoices Found Today</span>
                      <span className="text-sm font-semibold">47</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Server className="w-5 h-5" />
                  System Health
                </CardTitle>
                <CardDescription>
                  Email service infrastructure status
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 rounded-lg bg-green-50 border border-green-200">
                    <div className="flex items-center gap-2">
                      <Database className="w-4 h-4 text-green-600" />
                      <span className="font-medium text-sm">Database</span>
                    </div>
                    <Badge variant="secondary" className="bg-green-100 text-green-800">
                      Healthy
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg bg-green-50 border border-green-200">
                    <div className="flex items-center gap-2">
                      <Cpu className="w-4 h-4 text-green-600" />
                      <span className="font-medium text-sm">Celery Workers</span>
                    </div>
                    <Badge variant="secondary" className="bg-green-100 text-green-800">
                      4 Active
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg bg-yellow-50 border border-yellow-200">
                    <div className="flex items-center gap-2">
                      <Shield className="w-4 h-4 text-yellow-600" />
                      <span className="font-medium text-sm">Gmail API</span>
                    </div>
                    <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">
                      Rate Limited
                    </Badge>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg bg-green-50 border border-green-200">
                    <div className="flex items-center gap-2">
                      <Lock className="w-4 h-4 text-green-600" />
                      <span className="font-medium text-sm">OAuth Tokens</span>
                    </div>
                    <Badge variant="secondary" className="bg-green-100 text-green-800">
                      Valid
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Configuration Tab */}
        <TabsContent value="settings" className="space-y-4">
          <EmailConfigurationPanel />
        </TabsContent>
      </Tabs>

      {/* Gmail OAuth Dialog */}
      <GmailOAuthDialog
        open={showOAuthDialog}
        onOpenChange={setShowOAuthDialog}
        onAccountConnected={(account) => {
          setEmailAccounts(prev => [...prev, account])
          setShowOAuthDialog(false)
        }}
      />
    </div>
  )
}