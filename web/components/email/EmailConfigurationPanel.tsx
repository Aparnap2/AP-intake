"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Settings,
  Shield,
  Clock,
  Filter,
  Mail,
  Users,
  Ban,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Info,
  Plus,
  X,
  Edit,
  Save,
  RefreshCw,
  Download,
  Upload,
  Eye,
  EyeOff,
  Zap,
  Bell,
  Database,
  Globe,
  Key,
  Lock,
  ChevronDown,
  ChevronUp,
  Copy,
  Trash2,
  TestTube,
  Play,
  Pause,
  Archive,
  Calendar,
  Search,
  MoreHorizontal
} from "lucide-react"
import { cn } from "@/lib/utils"

interface EmailRule {
  id: string
  name: string
  description: string
  conditions: {
    sender?: string[]
    subject?: string[]
    body?: string[]
    hasAttachments?: boolean
    attachmentTypes?: string[]
  }
  actions: {
    autoProcess?: boolean
    priority?: "low" | "medium" | "high"
    requireReview?: boolean
    addToQueue?: boolean
  }
  isActive: boolean
  createdAt: string
  lastUsed?: string
}

interface NotificationSettings {
  emailNotifications: boolean
  slackWebhook?: string
  teamsWebhook?: string
  notifyOnNewInvoice: boolean
  notifyOnProcessingError: boolean
  notifyOnLowConfidence: boolean
  dailyDigest: boolean
  weeklyReport: boolean
}

interface SecuritySettings {
  requireSpfCheck: boolean
  requireDkimCheck: boolean
  blockSuspiciousDomains: boolean
  maxAttachmentSize: number
  allowedAttachmentTypes: string[]
  rateLimitPerMinute: number
  requireManualApproval: boolean
  quarantineSuspicious: boolean
}

export function EmailConfigurationPanel() {
  const [activeTab, setActiveTab] = useState("general")
  const [emailRules, setEmailRules] = useState<EmailRule[]>([
    {
      id: "rule_1",
      name: "High Priority Vendors",
      description: "Auto-process invoices from trusted vendors",
      conditions: {
        sender: ["accounts@acmecorp.com", "billing@techsolutions.com"],
        subject: ["invoice", "bill"],
        hasAttachments: true,
        attachmentTypes: ["pdf", "doc", "docx"]
      },
      actions: {
        autoProcess: true,
        priority: "high",
        requireReview: false,
        addToQueue: true
      },
      isActive: true,
      createdAt: "2024-11-01T10:00:00Z",
      lastUsed: "2024-11-06T14:30:00Z"
    },
    {
      id: "rule_2",
      name: "International Invoices",
      description: "Manual review required for international vendors",
      conditions: {
        subject: ["international", "foreign", "overseas"],
        body: ["currency", "exchange rate"]
      },
      actions: {
        autoProcess: false,
        priority: "medium",
        requireReview: true,
        addToQueue: true
      },
      isActive: true,
      createdAt: "2024-11-02T09:00:00Z",
      lastUsed: "2024-11-05T16:45:00Z"
    }
  ])

  const [generalSettings, setGeneralSettings] = useState({
    defaultProcessingDelay: 5,
    maxEmailsPerBatch: 100,
    enableDuplicateDetection: true,
    retentionPeriod: 365,
    enableAnalytics: true,
    timezone: "UTC",
    defaultConfidenceThreshold: 0.8,
    enableAutoApproval: false,
    backupEnabled: true
  })

  const [notificationSettings, setNotificationSettings] = useState<NotificationSettings>({
    emailNotifications: true,
    slackWebhook: "",
    teamsWebhook: "",
    notifyOnNewInvoice: true,
    notifyOnProcessingError: true,
    notifyOnLowConfidence: true,
    dailyDigest: true,
    weeklyReport: false
  })

  const [securitySettings, setSecuritySettings] = useState<SecuritySettings>({
    requireSpfCheck: true,
    requireDkimCheck: true,
    blockSuspiciousDomains: true,
    maxAttachmentSize: 25, // MB
    allowedAttachmentTypes: ["pdf", "doc", "docx", "xls", "xlsx"],
    rateLimitPerMinute: 60,
    requireManualApproval: false,
    quarantineSuspicious: true
  })

  const [newRule, setNewRule] = useState<Partial<EmailRule>>({
    name: "",
    description: "",
    conditions: {},
    actions: {},
    isActive: true
  })

  const [showNewRuleDialog, setShowNewRuleDialog] = useState(false)
  const [editingRule, setEditingRule] = useState<EmailRule | null>(null)
  const [showTestDialog, setShowTestDialog] = useState(false)

  const handleSaveGeneralSettings = () => {
    // Simulate API call
    setTimeout(() => {
      console.log("General settings saved:", generalSettings)
    }, 1000)
  }

  const handleSaveNotificationSettings = () => {
    // Simulate API call
    setTimeout(() => {
      console.log("Notification settings saved:", notificationSettings)
    }, 1000)
  }

  const handleSaveSecuritySettings = () => {
    // Simulate API call
    setTimeout(() => {
      console.log("Security settings saved:", securitySettings)
    }, 1000)
  }

  const handleCreateRule = () => {
    if (newRule.name && newRule.description) {
      const rule: EmailRule = {
        id: `rule_${Date.now()}`,
        name: newRule.name,
        description: newRule.description,
        conditions: newRule.conditions || {},
        actions: newRule.actions || {},
        isActive: newRule.isActive || true,
        createdAt: new Date().toISOString()
      }
      setEmailRules(prev => [...prev, rule])
      setNewRule({
        name: "",
        description: "",
        conditions: {},
        actions: {},
        isActive: true
      })
      setShowNewRuleDialog(false)
    }
  }

  const handleUpdateRule = () => {
    if (editingRule) {
      setEmailRules(prev => prev.map(rule =>
        rule.id === editingRule.id ? editingRule : rule
      ))
      setEditingRule(null)
    }
  }

  const handleDeleteRule = (ruleId: string) => {
    setEmailRules(prev => prev.filter(rule => rule.id !== ruleId))
  }

  const handleToggleRule = (ruleId: string) => {
    setEmailRules(prev => prev.map(rule =>
      rule.id === ruleId ? { ...rule, isActive: !rule.isActive } : rule
    ))
  }

  const handleTestConfiguration = () => {
    setShowTestDialog(true)
    setTimeout(() => {
      setShowTestDialog(false)
    }, 3000)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Email Configuration</h2>
          <p className="text-slate-600">Manage email processing rules, security settings, and notifications</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleTestConfiguration}>
            <TestTube className="w-4 h-4 mr-2" />
            Test Configuration
          </Button>
          <Button variant="outline">
            <Download className="w-4 h-4 mr-2" />
            Export Config
          </Button>
          <Button variant="outline">
            <Upload className="w-4 h-4 mr-2" />
            Import Config
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="rules">Processing Rules</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="advanced">Advanced</TabsTrigger>
        </TabsList>

        {/* General Settings */}
        <TabsContent value="general" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="w-5 h-5" />
                General Settings
              </CardTitle>
              <CardDescription>
                Basic configuration for email processing
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label htmlFor="processingDelay">Default Processing Delay (seconds)</Label>
                  <Input
                    id="processingDelay"
                    type="number"
                    value={generalSettings.defaultProcessingDelay}
                    onChange={(e) => setGeneralSettings(prev => ({ ...prev, defaultProcessingDelay: parseInt(e.target.value) }))}
                  />
                  <p className="text-sm text-slate-500">Delay before processing new emails</p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="maxEmailsPerBatch">Max Emails Per Batch</Label>
                  <Input
                    id="maxEmailsPerBatch"
                    type="number"
                    value={generalSettings.maxEmailsPerBatch}
                    onChange={(e) => setGeneralSettings(prev => ({ ...prev, maxEmailsPerBatch: parseInt(e.target.value) }))}
                  />
                  <p className="text-sm text-slate-500">Maximum emails to process in one batch</p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="timezone">Timezone</Label>
                  <Select
                    value={generalSettings.timezone}
                    onValueChange={(value) => setGeneralSettings(prev => ({ ...prev, timezone: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="UTC">UTC</SelectItem>
                      <SelectItem value="America/New_York">Eastern Time</SelectItem>
                      <SelectItem value="America/Chicago">Central Time</SelectItem>
                      <SelectItem value="America/Denver">Mountain Time</SelectItem>
                      <SelectItem value="America/Los_Angeles">Pacific Time</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confidenceThreshold">Default Confidence Threshold</Label>
                  <div className="flex items-center gap-4">
                    <input
                      type="range"
                      min="0.5"
                      max="1.0"
                      step="0.05"
                      value={generalSettings.defaultConfidenceThreshold}
                      onChange={(e) => setGeneralSettings(prev => ({ ...prev, defaultConfidenceThreshold: parseFloat(e.target.value) }))}
                      className="flex-1"
                    />
                    <span className="text-sm font-medium w-12">
                      {Math.round(generalSettings.defaultConfidenceThreshold * 100)}%
                    </span>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Enable Duplicate Detection</Label>
                    <p className="text-sm text-slate-500">Check for duplicate invoices across all accounts</p>
                  </div>
                  <Switch
                    checked={generalSettings.enableDuplicateDetection}
                    onCheckedChange={(checked) => setGeneralSettings(prev => ({ ...prev, enableDuplicateDetection: checked }))}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Enable Analytics</Label>
                    <p className="text-sm text-slate-500">Collect processing analytics and metrics</p>
                  </div>
                  <Switch
                    checked={generalSettings.enableAnalytics}
                    onCheckedChange={(checked) => setGeneralSettings(prev => ({ ...prev, enableAnalytics: checked }))}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Enable Auto-approval</Label>
                    <p className="text-sm text-slate-500">Automatically approve high-confidence invoices</p>
                  </div>
                  <Switch
                    checked={generalSettings.enableAutoApproval}
                    onCheckedChange={(checked) => setGeneralSettings(prev => ({ ...prev, enableAutoApproval: checked }))}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Enable Backup</Label>
                    <p className="text-sm text-slate-500">Create automatic backups of email configurations</p>
                  </div>
                  <Switch
                    checked={generalSettings.backupEnabled}
                    onCheckedChange={(checked) => setGeneralSettings(prev => ({ ...prev, backupEnabled: checked }))}
                  />
                </div>
              </div>

              <div className="flex justify-end">
                <Button onClick={handleSaveGeneralSettings}>
                  <Save className="w-4 h-4 mr-2" />
                  Save Settings
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Processing Rules */}
        <TabsContent value="rules" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Filter className="w-5 h-5" />
                    Processing Rules
                  </CardTitle>
                  <CardDescription>
                    Define rules for automatic email processing and routing
                  </CardDescription>
                </div>
                <Button onClick={() => setShowNewRuleDialog(true)}>
                  <Plus className="w-4 h-4 mr-2" />
                  Add Rule
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {emailRules.map((rule) => (
                  <Card key={rule.id} className={cn(!rule.isActive && "opacity-50")}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Switch
                            checked={rule.isActive}
                            onCheckedChange={() => handleToggleRule(rule.id)}
                          />
                          <div>
                            <CardTitle className="text-base">{rule.name}</CardTitle>
                            <CardDescription>{rule.description}</CardDescription>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={rule.actions.priority === "high" ? "destructive" : rule.actions.priority === "medium" ? "default" : "secondary"}>
                            {rule.actions.priority} priority
                          </Badge>
                          <Button variant="ghost" size="sm" onClick={() => setEditingRule(rule)}>
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => handleDeleteRule(rule.id)}>
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <h5 className="text-sm font-medium mb-2">Conditions</h5>
                          <div className="space-y-1 text-sm">
                            {rule.conditions.sender && (
                              <div>• From: {rule.conditions.sender.join(", ")}</div>
                            )}
                            {rule.conditions.subject && (
                              <div>• Subject contains: {rule.conditions.subject.join(", ")}</div>
                            )}
                            {rule.conditions.hasAttachments && (
                              <div>• Has attachments: Yes</div>
                            )}
                            {rule.conditions.attachmentTypes && (
                              <div>• Attachment types: {rule.conditions.attachmentTypes.join(", ")}</div>
                            )}
                          </div>
                        </div>
                        <div>
                          <h5 className="text-sm font-medium mb-2">Actions</h5>
                          <div className="space-y-1 text-sm">
                            {rule.actions.autoProcess && (
                              <div>• Auto-process: Yes</div>
                            )}
                            {rule.actions.requireReview && (
                              <div>• Require review: Yes</div>
                            )}
                            {rule.actions.addToQueue && (
                              <div>• Add to queue: Yes</div>
                            )}
                          </div>
                        </div>
                      </div>
                      {rule.lastUsed && (
                        <div className="text-xs text-slate-500 pt-2 border-t">
                          Last used: {new Date(rule.lastUsed).toLocaleString()}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security Settings */}
        <TabsContent value="security" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="w-5 h-5" />
                Security Settings
              </CardTitle>
              <CardDescription>
                Configure security measures for email processing
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <h4 className="font-medium">Email Authentication</h4>
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Require SPF Check</Label>
                    <p className="text-sm text-slate-500">Verify sender policy framework records</p>
                  </div>
                  <Switch
                    checked={securitySettings.requireSpfCheck}
                    onCheckedChange={(checked) => setSecuritySettings(prev => ({ ...prev, requireSpfCheck: checked }))}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Require DKIM Check</Label>
                    <p className="text-sm text-slate-500">Verify DomainKeys Identified Mail signatures</p>
                  </div>
                  <Switch
                    checked={securitySettings.requireDkimCheck}
                    onCheckedChange={(checked) => setSecuritySettings(prev => ({ ...prev, requireDkimCheck: checked }))}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Block Suspicious Domains</Label>
                    <p className="text-sm text-slate-500">Automatically block known malicious domains</p>
                  </div>
                  <Switch
                    checked={securitySettings.blockSuspiciousDomains}
                    onCheckedChange={(checked) => setSecuritySettings(prev => ({ ...prev, blockSuspiciousDomains: checked }))}
                  />
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Attachment Security</h4>
                <div className="space-y-2">
                  <Label>Max Attachment Size (MB)</Label>
                  <Input
                    type="number"
                    value={securitySettings.maxAttachmentSize}
                    onChange={(e) => setSecuritySettings(prev => ({ ...prev, maxAttachmentSize: parseInt(e.target.value) }))}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Allowed Attachment Types</Label>
                  <div className="flex flex-wrap gap-2">
                    {securitySettings.allowedAttachmentTypes.map((type) => (
                      <Badge key={type} variant="secondary">
                        {type}
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-auto p-0 ml-1"
                          onClick={() => setSecuritySettings(prev => ({
                            ...prev,
                            allowedAttachmentTypes: prev.allowedAttachmentTypes.filter(t => t !== type)
                          }))}
                        >
                          ×
                        </Button>
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Processing Security</h4>
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Rate Limit (emails/minute)</Label>
                    <p className="text-sm text-slate-500">Maximum emails to process per minute</p>
                  </div>
                  <Input
                    type="number"
                    value={securitySettings.rateLimitPerMinute}
                    onChange={(e) => setSecuritySettings(prev => ({ ...prev, rateLimitPerMinute: parseInt(e.target.value) }))}
                    className="w-24"
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Require Manual Approval</Label>
                    <p className="text-sm text-slate-500">All invoices require manual approval</p>
                  </div>
                  <Switch
                    checked={securitySettings.requireManualApproval}
                    onCheckedChange={(checked) => setSecuritySettings(prev => ({ ...prev, requireManualApproval: checked }))}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Quarantine Suspicious</Label>
                    <p className="text-sm text-slate-500">Quarantine suspicious emails for review</p>
                  </div>
                  <Switch
                    checked={securitySettings.quarantineSuspicious}
                    onCheckedChange={(checked) => setSecuritySettings(prev => ({ ...prev, quarantineSuspicious: checked }))}
                  />
                </div>
              </div>

              <div className="flex justify-end">
                <Button onClick={handleSaveSecuritySettings}>
                  <Save className="w-4 h-4 mr-2" />
                  Save Security Settings
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Notification Settings */}
        <TabsContent value="notifications" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="w-5 h-5" />
                Notification Settings
              </CardTitle>
              <CardDescription>
                Configure how and when you receive notifications
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <h4 className="font-medium">Email Notifications</h4>
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Enable Email Notifications</Label>
                    <p className="text-sm text-slate-500">Receive notifications via email</p>
                  </div>
                  <Switch
                    checked={notificationSettings.emailNotifications}
                    onCheckedChange={(checked) => setNotificationSettings(prev => ({ ...prev, emailNotifications: checked }))}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Slack Webhook URL</Label>
                  <Input
                    type="url"
                    value={notificationSettings.slackWebhook}
                    onChange={(e) => setNotificationSettings(prev => ({ ...prev, slackWebhook: e.target.value }))}
                    placeholder="https://hooks.slack.com/..."
                  />
                </div>

                <div className="space-y-2">
                  <Label>Microsoft Teams Webhook URL</Label>
                  <Input
                    type="url"
                    value={notificationSettings.teamsWebhook}
                    onChange={(e) => setNotificationSettings(prev => ({ ...prev, teamsWebhook: e.target.value }))}
                    placeholder="https://outlook.office.com/webhook/..."
                  />
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Notification Triggers</h4>
                <div className="flex items-center justify-between">
                  <div>
                    <Label>New Invoice Found</Label>
                    <p className="text-sm text-slate-500">Notify when new invoices are detected</p>
                  </div>
                  <Switch
                    checked={notificationSettings.notifyOnNewInvoice}
                    onCheckedChange={(checked) => setNotificationSettings(prev => ({ ...prev, notifyOnNewInvoice: checked }))}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Processing Errors</Label>
                    <p className="text-sm text-slate-500">Notify when processing fails</p>
                  </div>
                  <Switch
                    checked={notificationSettings.notifyOnProcessingError}
                    onCheckedChange={(checked) => setNotificationSettings(prev => ({ ...prev, notifyOnProcessingError: checked }))}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Low Confidence Detection</Label>
                    <p className="text-sm text-slate-500">Notify when confidence is below threshold</p>
                  </div>
                  <Switch
                    checked={notificationSettings.notifyOnLowConfidence}
                    onCheckedChange={(checked) => setNotificationSettings(prev => ({ ...prev, notifyOnLowConfidence: checked }))}
                  />
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Scheduled Reports</h4>
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Daily Digest</Label>
                    <p className="text-sm text-slate-500">Receive daily summary of email processing</p>
                  </div>
                  <Switch
                    checked={notificationSettings.dailyDigest}
                    onCheckedChange={(checked) => setNotificationSettings(prev => ({ ...prev, dailyDigest: checked }))}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Weekly Report</Label>
                    <p className="text-sm text-slate-500">Receive weekly analytics report</p>
                  </div>
                  <Switch
                    checked={notificationSettings.weeklyReport}
                    onCheckedChange={(checked) => setNotificationSettings(prev => ({ ...prev, weeklyReport: checked }))}
                  />
                </div>
              </div>

              <div className="flex justify-end">
                <Button onClick={handleSaveNotificationSettings}>
                  <Save className="w-4 h-4 mr-2" />
                  Save Notification Settings
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Advanced Settings */}
        <TabsContent value="advanced" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="w-5 h-5" />
                Advanced Configuration
              </CardTitle>
              <CardDescription>
                Advanced settings for power users
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Advanced Settings</AlertTitle>
                <AlertDescription>
                  These settings are intended for advanced users. Incorrect configuration may affect system performance.
                </AlertDescription>
              </Alert>

              <div className="space-y-4">
                <h4 className="font-medium">API Configuration</h4>
                <div className="space-y-2">
                  <Label>API Endpoint</Label>
                  <Input defaultValue="http://localhost:8000/api/v1" />
                </div>
                <div className="space-y-2">
                  <Label>API Key</Label>
                  <div className="flex gap-2">
                    <Input type="password" defaultValue="sk-xxxxx" className="flex-1" />
                    <Button variant="outline" size="sm">
                      <Eye className="w-4 h-4" />
                    </Button>
                    <Button variant="outline" size="sm">
                      <RefreshCw className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Database Settings</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Connection Pool Size</Label>
                    <Input type="number" defaultValue="20" />
                  </div>
                  <div className="space-y-2">
                    <Label>Query Timeout (seconds)</Label>
                    <Input type="number" defaultValue="30" />
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <h4 className="font-medium">Logging Configuration</h4>
                <div className="space-y-2">
                  <Label>Log Level</Label>
                  <Select defaultValue="INFO">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="DEBUG">DEBUG</SelectItem>
                      <SelectItem value="INFO">INFO</SelectItem>
                      <SelectItem value="WARNING">WARNING</SelectItem>
                      <SelectItem value="ERROR">ERROR</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Log Retention (days)</Label>
                  <Input type="number" defaultValue="30" />
                </div>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline">Reset to Defaults</Button>
                <Button>Save Advanced Settings</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* New Rule Dialog */}
      <Dialog open={showNewRuleDialog} onOpenChange={setShowNewRuleDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Create New Processing Rule</DialogTitle>
            <DialogDescription>
              Define conditions and actions for automatic email processing
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="ruleName">Rule Name</Label>
                <Input
                  id="ruleName"
                  value={newRule.name}
                  onChange={(e) => setNewRule(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., High Priority Vendors"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ruleDescription">Description</Label>
                <Input
                  id="ruleDescription"
                  value={newRule.description}
                  onChange={(e) => setNewRule(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Brief description of the rule"
                />
              </div>
            </div>

            <div className="space-y-4">
              <h4 className="font-medium">Conditions</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Sender Email (comma-separated)</Label>
                  <Input
                    placeholder="vendor1@company.com, vendor2@company.com"
                    onChange={(e) => setNewRule(prev => ({
                      ...prev,
                      conditions: {
                        ...prev.conditions,
                        sender: e.target.value.split(",").map(s => s.trim()).filter(Boolean)
                      }
                    }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Subject Keywords (comma-separated)</Label>
                  <Input
                    placeholder="invoice, bill, payment"
                    onChange={(e) => setNewRule(prev => ({
                      ...prev,
                      conditions: {
                        ...prev.conditions,
                        subject: e.target.value.split(",").map(s => s.trim()).filter(Boolean)
                      }
                    }))}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <h4 className="font-medium">Actions</h4>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Auto-process</Label>
                    <p className="text-sm text-slate-500">Automatically process matching emails</p>
                  </div>
                  <Switch
                    checked={newRule.actions?.autoProcess || false}
                    onCheckedChange={(checked) => setNewRule(prev => ({
                      ...prev,
                      actions: { ...prev.actions, autoProcess: checked }
                    }))}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Require Review</Label>
                    <p className="text-sm text-slate-500">Require manual review before approval</p>
                  </div>
                  <Switch
                    checked={newRule.actions?.requireReview || false}
                    onCheckedChange={(checked) => setNewRule(prev => ({
                      ...prev,
                      actions: { ...prev.actions, requireReview: checked }
                    }))}
                  />
                </div>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewRuleDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateRule}>
              Create Rule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Test Configuration Dialog */}
      <Dialog open={showTestDialog} onOpenChange={setShowTestDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Testing Configuration</DialogTitle>
            <DialogDescription>
              Running configuration tests...
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
              <span>Testing email connectivity...</span>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-600" />
                <span className="text-sm">SMTP connection successful</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-600" />
                <span className="text-sm">OAuth tokens valid</span>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-600" />
                <span className="text-sm">Processing rules validated</span>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}