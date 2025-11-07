"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
import {
  ExternalLink,
  Shield,
  Lock,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Eye,
  EyeOff,
  Key,
  User,
  Mail,
  Settings,
  Zap,
  Clock,
  FileText,
  Filter,
  Users,
  Ban,
  CheckSquare,
  Info
} from "lucide-react"
import { GmailIcon } from "@/components/icons/GmailIcon"
import { Progress } from "@/components/ui/progress"

interface GmailOAuthDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAccountConnected: (account: any) => void
}

interface OAuthState {
  step: "initial" | "authorizing" | "callback" | "configuring" | "completed" | "error"
  authorizationUrl?: string
  state?: string
  error?: string
  accountInfo?: any
}

interface EmailConfiguration {
  displayName: string
  securityLevel: "low" | "medium" | "high"
  autoProcessingEnabled: boolean
  monitoringInterval: number
  daysToProcess: number
  trustedSenders: string[]
  blockedSenders: string[]
  invoiceDetection: {
    keywords: string[]
    attachmentTypes: string[]
    minConfidence: number
  }
  processingRules: {
    autoApproveHighConfidence: boolean
    requireHumanReview: boolean
    duplicateDetection: boolean
  }
}

export function GmailOAuthDialog({ open, onOpenChange, onAccountConnected }: GmailOAuthDialogProps) {
  const [oauthState, setOAuthState] = useState<OAuthState>({ step: "initial" })
  const [configuration, setConfiguration] = useState<EmailConfiguration>({
    displayName: "",
    securityLevel: "medium",
    autoProcessingEnabled: true,
    monitoringInterval: 15,
    daysToProcess: 30,
    trustedSenders: [],
    blockedSenders: [],
    invoiceDetection: {
      keywords: ["invoice", "bill", "payment", "due", "receipt"],
      attachmentTypes: ["pdf", "doc", "docx"],
      minConfidence: 0.8
    },
    processingRules: {
      autoApproveHighConfidence: true,
      requireHumanReview: true,
      duplicateDetection: true
    }
  })
  const [newSender, setNewSender] = useState("")
  const [newKeyword, setNewKeyword] = useState("")
  const [showPassword, setShowPassword] = useState(false)

  useEffect(() => {
    if (open) {
      setOAuthState({ step: "initial" })
      setConfiguration({
        displayName: "",
        securityLevel: "medium",
        autoProcessingEnabled: true,
        monitoringInterval: 15,
        daysToProcess: 30,
        trustedSenders: [],
        blockedSenders: [],
        invoiceDetection: {
          keywords: ["invoice", "bill", "payment", "due", "receipt"],
          attachmentTypes: ["pdf", "doc", "docx"],
          minConfidence: 0.8
        },
        processingRules: {
          autoApproveHighConfidence: true,
          requireHumanReview: true,
          duplicateDetection: true
        }
      })
    }
  }, [open])

  const handleStartAuthorization = async () => {
    setOAuthState({ step: "authorizing" })

    // Simulate API call to get authorization URL
    setTimeout(() => {
      const mockAuthUrl = "https://accounts.google.com/oauth/authorize?client_id=mock&redirect_uri=http://localhost:8000/api/v1/gmail/callback&response_type=code&scope=https://www.googleapis.com/auth/gmail.readonly&state=mock_state_123"
      setOAuthState({
        step: "authorizing",
        authorizationUrl: mockAuthUrl,
        state: "mock_state_123"
      })
    }, 1500)
  }

  const handleOpenGoogleAuth = () => {
    if (oauthState.authorizationUrl) {
      // In a real app, this would open the OAuth URL
      // For demo purposes, we'll simulate the callback
      setTimeout(() => {
        setOAuthState({
          step: "callback",
          accountInfo: {
            email: "demo@acmecorp.com",
            name: "Demo Account",
            picture: "https://ui-avatars.com/api/?name=Demo+Account&background=0d8abc&color=fff"
          }
        })

        // Auto-advance to configuring step after callback
        setTimeout(() => {
          setOAuthState(prev => ({
            ...prev,
            step: "configuring",
            accountInfo: {
              ...prev.accountInfo!,
              email: "demo@acmecorp.com"
            }
          }))
          setConfiguration(prev => ({
            ...prev,
            displayName: "Demo Account"
          }))
        }, 2000)
      }, 1000)
    }
  }

  const handleAddSender = (type: "trusted" | "blocked") => {
    if (newSender && newSender.includes("@")) {
      setConfiguration(prev => ({
        ...prev,
        [type === "trusted" ? "trustedSenders" : "blockedSenders"]: [
          ...prev[type === "trusted" ? "trustedSenders" : "blockedSenders"],
          newSender
        ]
      }))
      setNewSender("")
    }
  }

  const handleRemoveSender = (type: "trusted" | "blocked", sender: string) => {
    setConfiguration(prev => ({
      ...prev,
      [type === "trusted" ? "trustedSenders" : "blockedSenders"]: prev[
        type === "trusted" ? "trustedSenders" : "blockedSenders"
      ].filter(s => s !== sender)
    }))
  }

  const handleAddKeyword = () => {
    if (newKeyword.trim()) {
      setConfiguration(prev => ({
        ...prev,
        invoiceDetection: {
          ...prev.invoiceDetection,
          keywords: [...prev.invoiceDetection.keywords, newKeyword.trim()]
        }
      }))
      setNewKeyword("")
    }
  }

  const handleRemoveKeyword = (keyword: string) => {
    setConfiguration(prev => ({
      ...prev,
      invoiceDetection: {
        ...prev.invoiceDetection,
        keywords: prev.invoiceDetection.keywords.filter(k => k !== keyword)
      }
    }))
  }

  const handleCompleteSetup = () => {
    setOAuthState({ step: "completed" })

    const newAccount = {
      id: Date.now().toString(),
      provider: "gmail",
      email: oauthState.accountInfo?.email || "demo@acmecorp.com",
      displayName: configuration.displayName,
      isActive: configuration.autoProcessingEnabled,
      isConnected: true,
      lastSync: new Date().toISOString(),
      totalEmails: Math.floor(Math.random() * 10000) + 1000,
      processedEmails: 0,
      autoProcessingEnabled: configuration.autoProcessingEnabled,
      securityLevel: configuration.securityLevel,
      oauthState: "connected" as const
    }

    setTimeout(() => {
      onAccountConnected(newAccount)
      onOpenChange(false)
    }, 2000)
  }

  const getStepIcon = (step: string) => {
    switch (step) {
      case "initial":
        return <Key className="w-5 h-5" />
      case "authorizing":
        return <Lock className="w-5 h-5" />
      case "callback":
        return <RefreshCw className="w-5 h-5 animate-spin" />
      case "configuring":
        return <Settings className="w-5 h-5" />
      case "completed":
        return <CheckCircle2 className="w-5 h-5" />
      case "error":
        return <AlertTriangle className="w-5 h-5" />
      default:
        return <Info className="w-5 h-5" />
    }
  }

  const getProgressPercentage = () => {
    const steps = ["initial", "authorizing", "callback", "configuring", "completed"]
    const currentIndex = steps.indexOf(oauthState.step)
    return currentIndex >= 0 ? ((currentIndex + 1) / steps.length) * 100 : 0
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GmailIcon className="w-6 h-6" />
            Connect Gmail Account
          </DialogTitle>
          <DialogDescription>
            Set up automatic invoice detection and processing from your Gmail inbox
          </DialogDescription>
        </DialogHeader>

        {/* Progress Indicator */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-slate-600">
            <span>Step {oauthState.step === "initial" ? "1" : oauthState.step === "authorizing" ? "2" : oauthState.step === "callback" ? "3" : oauthState.step === "configuring" ? "4" : "5"} of 5</span>
            <span>{Math.round(getProgressPercentage())}% Complete</span>
          </div>
          <Progress value={getProgressPercentage()} className="h-2" />
        </div>

        {/* Initial Step */}
        {oauthState.step === "initial" && (
          <div className="space-y-6">
            <Alert>
              <Shield className="h-4 w-4" />
              <AlertTitle>Secure OAuth Connection</AlertTitle>
              <AlertDescription>
                We use Google's OAuth 2.0 protocol for secure, read-only access to your Gmail inbox.
                Your credentials are never stored on our servers.
              </AlertDescription>
            </Alert>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card className="border-blue-200 bg-blue-50">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <FileText className="w-4 h-4 text-blue-600" />
                    Automatic Detection
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="text-sm text-slate-700">
                    AI-powered detection of invoice emails with 95%+ accuracy
                  </p>
                  <div className="flex flex-wrap gap-1">
                    <Badge variant="secondary" className="text-xs">PDF attachments</Badge>
                    <Badge variant="secondary" className="text-xs">Subject analysis</Badge>
                    <Badge variant="secondary" className="text-xs">Sender verification</Badge>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-green-200 bg-green-50">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Zap className="w-4 h-4 text-green-600" />
                    Real-time Processing
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="text-sm text-slate-700">
                    Process new emails within minutes of receipt
                  </p>
                  <div className="flex flex-wrap gap-1">
                    <Badge variant="secondary" className="text-xs">15-min intervals</Badge>
                    <Badge variant="secondary" className="text-xs">Instant alerts</Badge>
                    <Badge variant="secondary" className="text-xs">Queue management</Badge>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="flex justify-end">
              <Button onClick={handleStartAuthorization} className="bg-red-600 hover:bg-red-700">
                <GmailIcon className="w-4 h-4 mr-2" />
                Connect with Google
              </Button>
            </div>
          </div>
        )}

        {/* Authorizing Step */}
        {oauthState.step === "authorizing" && (
          <div className="space-y-6">
            <div className="text-center space-y-4">
              <RefreshCw className="w-12 h-12 animate-spin mx-auto text-blue-600" />
              <div>
                <h3 className="text-lg font-semibold">Initiating OAuth Flow</h3>
                <p className="text-slate-600">Preparing secure authorization request...</p>
              </div>
            </div>
          </div>
        )}

        {/* Callback Step */}
        {oauthState.step === "callback" && (
          <div className="space-y-6">
            <div className="text-center space-y-4">
              <RefreshCw className="w-12 h-12 animate-spin mx-auto text-green-600" />
              <div>
                <h3 className="text-lg font-semibold">Authorizing with Google</h3>
                <p className="text-slate-600">Please complete the authorization in your browser...</p>
              </div>
              <Button onClick={handleOpenGoogleAuth} variant="outline">
                <ExternalLink className="w-4 h-4 mr-2" />
                Open Google Authorization
              </Button>
            </div>
          </div>
        )}

        {/* Configuration Step */}
        {oauthState.step === "configuring" && oauthState.accountInfo && (
          <div className="space-y-6">
            <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
              <CheckCircle2 className="w-6 h-6 text-green-600" />
              <div>
                <h3 className="font-semibold text-green-900">Successfully Connected</h3>
                <p className="text-green-700">{oauthState.accountInfo.email}</p>
              </div>
            </div>

            <Tabs defaultValue="basic" className="space-y-4">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="basic">Basic Settings</TabsTrigger>
                <TabsTrigger value="security">Security</TabsTrigger>
                <TabsTrigger value="processing">Processing Rules</TabsTrigger>
              </TabsList>

              <TabsContent value="basic" className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="displayName">Display Name</Label>
                    <Input
                      id="displayName"
                      value={configuration.displayName}
                      onChange={(e) => setConfiguration(prev => ({ ...prev, displayName: e.target.value }))}
                      placeholder="e.g., Company Accounts"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="monitoringInterval">Check Interval (minutes)</Label>
                    <Select
                      value={configuration.monitoringInterval.toString()}
                      onValueChange={(value) => setConfiguration(prev => ({ ...prev, monitoringInterval: parseInt(value) }))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="5">5 minutes</SelectItem>
                        <SelectItem value="15">15 minutes</SelectItem>
                        <SelectItem value="30">30 minutes</SelectItem>
                        <SelectItem value="60">1 hour</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="daysToProcess">Process emails from last</Label>
                    <Select
                      value={configuration.daysToProcess.toString()}
                      onValueChange={(value) => setConfiguration(prev => ({ ...prev, daysToProcess: parseInt(value) }))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="7">7 days</SelectItem>
                        <SelectItem value="30">30 days</SelectItem>
                        <SelectItem value="90">90 days</SelectItem>
                        <SelectItem value="365">1 year</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Auto Processing</Label>
                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={configuration.autoProcessingEnabled}
                        onCheckedChange={(checked) => setConfiguration(prev => ({ ...prev, autoProcessingEnabled: checked }))}
                      />
                      <Label className="text-sm">Enable automatic invoice processing</Label>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Invoice Detection Keywords</Label>
                  <div className="flex gap-2">
                    <Input
                      value={newKeyword}
                      onChange={(e) => setNewKeyword(e.target.value)}
                      placeholder="Add keyword..."
                      onKeyPress={(e) => e.key === "Enter" && handleAddKeyword()}
                    />
                    <Button onClick={handleAddKeyword} variant="outline">
                      Add
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {configuration.invoiceDetection.keywords.map((keyword) => (
                      <Badge key={keyword} variant="secondary" className="cursor-pointer" onClick={() => handleRemoveKeyword(keyword)}>
                        {keyword} ×
                      </Badge>
                    ))}
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="security" className="space-y-4">
                <div className="space-y-2">
                  <Label>Security Level</Label>
                  <Select
                    value={configuration.securityLevel}
                    onValueChange={(value: "low" | "medium" | "high") => setConfiguration(prev => ({ ...prev, securityLevel: value }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Low - Basic validation</SelectItem>
                      <SelectItem value="medium">Medium - Standard security checks</SelectItem>
                      <SelectItem value="high">High - Maximum security</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Trusted Senders</Label>
                  <div className="flex gap-2">
                    <Input
                      type="email"
                      value={newSender}
                      onChange={(e) => setNewSender(e.target.value)}
                      placeholder="Add trusted email..."
                      onKeyPress={(e) => e.key === "Enter" && handleAddSender("trusted")}
                    />
                    <Button onClick={() => handleAddSender("trusted")} variant="outline">
                      <Users className="w-4 h-4 mr-1" />
                      Add
                    </Button>
                  </div>
                  <div className="space-y-1">
                    {configuration.trustedSenders.map((sender) => (
                      <div key={sender} className="flex items-center justify-between p-2 bg-green-50 border border-green-200 rounded">
                        <span className="text-sm">{sender}</span>
                        <Button variant="ghost" size="sm" onClick={() => handleRemoveSender("trusted", sender)}>
                          ×
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Blocked Senders</Label>
                  <div className="flex gap-2">
                    <Input
                      type="email"
                      value={newSender}
                      onChange={(e) => setNewSender(e.target.value)}
                      placeholder="Add blocked email..."
                      onKeyPress={(e) => e.key === "Enter" && handleAddSender("blocked")}
                    />
                    <Button onClick={() => handleAddSender("blocked")} variant="outline">
                      <Ban className="w-4 h-4 mr-1" />
                      Add
                    </Button>
                  </div>
                  <div className="space-y-1">
                    {configuration.blockedSenders.map((sender) => (
                      <div key={sender} className="flex items-center justify-between p-2 bg-red-50 border border-red-200 rounded">
                        <span className="text-sm">{sender}</span>
                        <Button variant="ghost" size="sm" onClick={() => handleRemoveSender("blocked", sender)}>
                          ×
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="processing" className="space-y-4">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Auto-approve High Confidence</Label>
                      <p className="text-sm text-slate-500">Automatically approve invoices with confidence ≥ 95%</p>
                    </div>
                    <Switch
                      checked={configuration.processingRules.autoApproveHighConfidence}
                      onCheckedChange={(checked) => setConfiguration(prev => ({
                        ...prev,
                        processingRules: { ...prev.processingRules, autoApproveHighConfidence: checked }
                      }))}
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Require Human Review</Label>
                      <p className="text-sm text-slate-500">All invoices require manual review before approval</p>
                    </div>
                    <Switch
                      checked={configuration.processingRules.requireHumanReview}
                      onCheckedChange={(checked) => setConfiguration(prev => ({
                        ...prev,
                        processingRules: { ...prev.processingRules, requireHumanReview: checked }
                      }))}
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Duplicate Detection</Label>
                      <p className="text-sm text-slate-500">Check for duplicate invoices across all accounts</p>
                    </div>
                    <Switch
                      checked={configuration.processingRules.duplicateDetection}
                      onCheckedChange={(checked) => setConfiguration(prev => ({
                        ...prev,
                        processingRules: { ...prev.processingRules, duplicateDetection: checked }
                      }))}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Minimum Confidence Threshold</Label>
                    <div className="flex items-center gap-4">
                      <input
                        type="range"
                        min="0.5"
                        max="1.0"
                        step="0.05"
                        value={configuration.invoiceDetection.minConfidence}
                        onChange={(e) => setConfiguration(prev => ({
                          ...prev,
                          invoiceDetection: { ...prev.invoiceDetection, minConfidence: parseFloat(e.target.value) }
                        }))}
                        className="flex-1"
                      />
                      <span className="text-sm font-medium w-12">
                        {Math.round(configuration.invoiceDetection.minConfidence * 100)}%
                      </span>
                    </div>
                  </div>
                </div>
              </TabsContent>
            </Tabs>

            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button onClick={handleCompleteSetup}>
                Complete Setup
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Completed Step */}
        {oauthState.step === "completed" && (
          <div className="space-y-6">
            <div className="text-center space-y-4">
              <CheckCircle2 className="w-16 h-16 mx-auto text-green-600" />
              <div>
                <h3 className="text-xl font-semibold text-green-900">Setup Complete!</h3>
                <p className="text-slate-600">Your Gmail account has been successfully connected and configured.</p>
              </div>
              <div className="space-y-2 text-sm text-slate-600">
                <p>• Automatic email monitoring is now active</p>
                <p>• Invoice detection will run every {configuration.monitoringInterval} minutes</p>
                <p>• Security level set to: {configuration.securityLevel}</p>
              </div>
            </div>
          </div>
        )}

        {/* Error Step */}
        {oauthState.step === "error" && (
          <div className="space-y-6">
            <Alert className="border-red-200 bg-red-50">
              <AlertTriangle className="h-4 w-4 text-red-600" />
              <AlertTitle>Connection Failed</AlertTitle>
              <AlertDescription>
                {oauthState.error || "Unable to connect to your Gmail account. Please try again."}
              </AlertDescription>
            </Alert>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOAuthState({ step: "initial" })}>
                Try Again
              </Button>
              <Button onClick={() => onOpenChange(false)}>
                Close
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}