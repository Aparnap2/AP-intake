# AP Intake Integration Implementation Guide

## Overview

This guide provides step-by-step instructions for implementing the critical integration improvements identified in the full-stack analysis. The improvements focus on production reliability, real-time updates, error handling, and user experience enhancements.

## Implementation Priority

### Phase 1: Critical Infrastructure (Week 1-2)
1. **Real-time WebSocket Integration** - Immediate processing feedback
2. **Enhanced Error Boundaries** - Graceful error handling
3. **Enhanced API Client** - Retry logic and caching
4. **Processing Status Tracking** - Background task visibility

### Phase 2: User Experience (Week 3-4)
1. **Optimistic Updates** - Responsive UI interactions
2. **Loading States & Skeletons** - Better perceived performance
3. **Request Caching** - Faster data loading
4. **Conflict Resolution** - Handle concurrent edits

## Phase 1: Critical Infrastructure Implementation

### 1. Real-time WebSocket Integration

**Files Created:**
- `/web/hooks/useRealtimeInvoiceUpdates.ts` - Real-time updates hook
- Backend WebSocket endpoint needed: `/api/v1/invoices/updates`

**Implementation Steps:**

#### A. Add WebSocket Endpoint to FastAPI Backend

Add to `/app/api/api_v1/endpoints/websockets.py`:
```python
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
from typing import Dict, Set

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.invoice_subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()
        self.active_connections[client_id].add(websocket)
        self.invoice_subscriptions[websocket] = set()

    def disconnect(self, websocket: WebSocket, client_id: str):
        if client_id in self.active_connections:
            self.active_connections[client_id].discard(websocket)
        if websocket in self.invoice_subscriptions:
            del self.invoice_subscriptions[websocket]

    async def subscribe_to_invoice(self, websocket: WebSocket, invoice_id: str):
        if websocket in self.invoice_subscriptions:
            self.invoice_subscriptions[websocket].add(invoice_id)

    async def broadcast_to_invoice_subscribers(self, invoice_id: str, message: dict):
        for client_connections in self.active_connections.values():
            for connection in client_connections:
                if (connection in self.invoice_subscriptions and
                    invoice_id in self.invoice_subscriptions[connection]):
                    try:
                        await connection.send_text(json.dumps(message))
                    except:
                        # Connection closed, will be cleaned up on disconnect
                        pass

manager = ConnectionManager()

@router.websocket("/invoices/updates")
async def websocket_endpoint(websocket: WebSocket):
    client_id = f"client_{id(websocket)}"
    await manager.connect(websocket, client_id)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "subscribe":
                invoice_id = message.get("invoiceId")
                if invoice_id:
                    await manager.subscribe_to_invoice(websocket, invoice_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id)
```

#### B. Update Invoice Processing to Send Real-time Updates

Modify `/app/workers/invoice_tasks.py`:
```python
from app.api.api_v1.endpoints.websockets import manager

async def send_processing_update(invoice_id: str, status: str, progress: int, stage: str, message: str = None):
    update = {
        "type": "processing_status",
        "invoiceId": invoice_id,
        "data": {
            "status": status,
            "progress": progress,
            "stage": stage,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    await manager.broadcast_to_invoice_subscribers(invoice_id, update)

@celery_app.task
def process_invoice_task(invoice_id: str, file_path: str, file_hash: str):
    try:
        # Send initial status
        asyncio.run(send_processing_update(invoice_id, "processing", 10, "starting"))

        # Processing steps...
        asyncio.run(send_processing_update(invoice_id, "parsing", 30, "extracting data"))

        # Continue with processing...

        # Send completion
        asyncio.run(send_processing_update(invoice_id, "completed", 100, "processing complete"))

    except Exception as e:
        asyncio.run(send_processing_update(invoice_id, "failed", 0, "error", str(e)))
```

#### C. Integrate Real-time Updates in Components

Update `/web/components/invoice/InvoiceDashboard.tsx`:
```typescript
import { useRealtimeInvoiceUpdates } from '@/hooks/useRealtimeInvoiceUpdates'

export function InvoiceDashboard({ onInvoiceSelect }: { onInvoiceSelect?: (invoice: any) => void }) {
  const [invoices, setInvoices] = useState<Invoice[]>([])

  // Real-time updates
  const { isConnected, processingStatus, lastUpdate } = useRealtimeInvoiceUpdates(
    undefined, // Subscribe to all updates
    (update) => {
      if (update.type === 'invoice_updated') {
        // Update invoice in local state
        setInvoices(prev => prev.map(inv =>
          inv.id === update.invoiceId ? { ...inv, ...update.data } : inv
        ))
      }
    }
  )

  // Connection status indicator
  useEffect(() => {
    if (!isConnected) {
      console.warn('Real-time updates disconnected')
    }
  }, [isConnected])

  // Rest of component...
}
```

### 2. Enhanced Error Boundaries

**File Created:**
- `/web/components/ui/error-boundary.tsx` - Error boundary component

**Implementation Steps:**

#### A. Wrap Critical Components

Update `/web/app/invoices/page.tsx`:
```typescript
import { ErrorBoundary } from '@/components/ui/error-boundary'

export default function InvoicesPage() {
  return (
    <ErrorBoundary
      onError={(error, errorInfo) => {
        // Report to monitoring service
        console.error('Invoices page error:', error, errorInfo)
      }}
    >
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
        {/* Rest of page content */}
      </div>
    </ErrorBoundary>
  )
}
```

#### B. Add Error Boundary to Individual Components

Update `/web/components/invoice/InvoiceDashboard.tsx`:
```typescript
import { ErrorBoundary, withErrorBoundary } from '@/components/ui/error-boundary'

// Wrap the entire dashboard
export function InvoiceDashboard({ onInvoiceSelect }: { onInvoiceSelect?: (invoice: any) => void }) {
  return (
    <ErrorBoundary fallback={
      <div className="text-center p-8">
        <h3>Dashboard temporarily unavailable</h3>
        <p>Please refresh the page or try again later.</p>
      </div>
    }>
      {/* Dashboard content */}
    </ErrorBoundary>
  )
}

// Or use HOC for individual components
export const InvoiceTable = withErrorBoundary(function InvoiceTable({ invoices }) {
  // Table implementation
})
```

### 3. Enhanced API Client with Retry Logic

**File Created:**
- `/web/lib/enhanced-invoice-api.ts` - Enhanced API client

**Implementation Steps:**

#### A. Replace API Client Usage

Update `/web/components/invoice/InvoiceDashboard.tsx`:
```typescript
import { enhancedInvoiceApi } from '@/lib/enhanced-invoice-api'

export function InvoiceDashboard({ onInvoiceSelect }: { onInvoiceSelect?: (invoice: any) => void }) {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadInvoices = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await enhancedInvoiceApi.getInvoices(undefined, {
          cache: true,
          retry: true,
          timeout: 10000
        })
        setInvoices(response.invoices)
      } catch (error) {
        console.error('Failed to load invoices:', error)
        setError(error instanceof Error ? error.message : 'Failed to load invoices')
        setInvoices([])
      } finally {
        setLoading(false)
      }
    }

    loadInvoices()
  }, [])

  // Rest of component...
}
```

#### B. Add Connection Status Indicator

Create `/web/components/ui/connection-status.tsx`:
```typescript
import { Badge } from '@/components/ui/badge'
import { Wifi, WifiOff } from 'lucide-react'
import { useState, useEffect } from 'react'

export function ConnectionStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking')

  useEffect(() => {
    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  useEffect(() => {
    const checkApiHealth = async () => {
      try {
        await enhancedInvoiceApi.healthCheck()
        setApiStatus('online')
      } catch (error) {
        setApiStatus('offline')
      }
    }

    checkApiHealth()
    const interval = setInterval(checkApiHealth, 30000) // Check every 30 seconds

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex items-center gap-2">
      <Badge variant={isOnline ? 'default' : 'destructive'} className="text-xs">
        {isOnline ? <Wifi className="w-3 h-3 mr-1" /> : <WifiOff className="w-3 h-3 mr-1" />}
        {isOnline ? 'Online' : 'Offline'}
      </Badge>

      <Badge variant={apiStatus === 'online' ? 'default' : 'destructive'} className="text-xs">
        API: {apiStatus}
      </Badge>
    </div>
  )
}
```

### 4. Processing Status Tracking

**Implementation Steps:**

#### A. Create Processing Status Component

Create `/web/components/invoice/ProcessingStatus.tsx`:
```typescript
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { useProcessingStatus } from '@/hooks/useRealtimeInvoiceUpdates'

interface ProcessingStatusProps {
  taskId: string
  invoiceId: string
}

export function ProcessingStatus({ taskId, invoiceId }: ProcessingStatusProps) {
  const { status, isComplete } = useProcessingStatus(taskId)
  const { processingStatus } = useRealtimeInvoiceUpdates(invoiceId)

  const currentStatus = processingStatus[invoiceId] || status

  if (!currentStatus) {
    return null
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'default'
      case 'failed': return 'destructive'
      case 'processing': return 'secondary'
      default: return 'secondary'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle2 className="h-4 w-4" />
      case 'failed': return <AlertCircle className="h-4 w-4" />
      case 'processing': return <Loader2 className="h-4 w-4 animate-spin" />
      default: return <Loader2 className="h-4 w-4" />
    }
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {getStatusIcon(currentStatus.status)}
          Processing Status
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">{currentStatus.stage}</span>
          <Badge variant={getStatusColor(currentStatus.status)}>
            {currentStatus.status}
          </Badge>
        </div>

        {(currentStatus.status === 'processing' || currentStatus.status === 'parsing' || currentStatus.status === 'validating') && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Progress</span>
              <span>{currentStatus.progress}%</span>
            </div>
            <Progress value={currentStatus.progress} className="h-2" />
          </div>
        )}

        {currentStatus.message && (
          <Alert>
            <AlertDescription>{currentStatus.message}</AlertDescription>
          </Alert>
        )}

        {currentStatus.error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{currentStatus.error}</AlertDescription>
          </Alert>
        )}

        {currentStatus.status === 'completed' && (
          <Alert>
            <CheckCircle2 className="h-4 w-4" />
            <AlertDescription>
              Invoice processed successfully! You can now review the extracted data.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  )
}
```

#### B. Integrate Processing Status in Upload Flow

Update `/web/components/invoice/UploadModal.tsx`:
```typescript
import { ProcessingStatus } from './ProcessingStatus'

// In the upload success handling:
const handleUploadSuccess = async (uploadResults: any[]) => {
  const uploadedInvoices = []

  for (const result of uploadResults) {
    if (result.id) {
      uploadedInvoices.push({
        id: result.id,
        taskId: result.taskId,
        status: 'processing'
      })
    }
  }

  setUploadedInvoices(uploadedInvoices)
  setShowProcessingStatus(true)
}

// Add processing status display
{uploadedInvoices.map(invoice => (
  <ProcessingStatus
    key={invoice.id}
    taskId={invoice.taskId}
    invoiceId={invoice.id}
  />
))}
```

## Phase 2: User Experience Implementation

### 1. Optimistic Updates

**File Created:**
- `/web/hooks/useOptimisticUpdates.ts` - Optimistic updates hook

**Implementation Steps:**

#### A. Add Optimistic Updates to Invoice Actions

Update `/web/components/invoice/InvoiceReview.tsx`:
```typescript
import { useOptimisticUpdates } from '@/hooks/useOptimisticUpdates'

export function InvoiceReview({ invoice, onApprovalComplete }) {
  const { approveInvoice, rejectInvoice, isUpdating, pendingActions } = useOptimisticUpdates(
    (invoiceId, data) => {
      // Update local state optimistically
      if (invoiceId === invoice.id) {
        setInvoice(prev => ({ ...prev, ...data }))
      }
    }
  )

  const handleApprove = async () => {
    try {
      await approveInvoice(invoice.id, "Approved after review")
      onApprovalComplete({ ...invoice, status: 'approved' })
    } catch (error) {
      console.error('Failed to approve invoice:', error)
    }
  }

  const handleReject = async (reason: string) => {
    try {
      await rejectInvoice(invoice.id, reason)
      onApprovalComplete({ ...invoice, status: 'rejected' })
    } catch (error) {
      console.error('Failed to reject invoice:', error)
    }
  }

  return (
    <div>
      {/* Review content */}

      <div className="flex gap-2">
        <Button
          onClick={handleApprove}
          disabled={isUpdating}
        >
          {isUpdating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
          Approve
        </Button>

        <Button
          variant="destructive"
          onClick={() => handleReject('Rejected after review')}
          disabled={isUpdating}
        >
          {isUpdating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
          Reject
        </Button>
      </div>

      {/* Show pending actions indicator */}
      {pendingActions.length > 0 && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {pendingActions.length} action(s) pending sync with server...
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}
```

### 2. Loading States and Skeletons

**Implementation Steps:**

#### A. Create Skeleton Components

Create `/web/components/ui/skeleton.tsx`:
```typescript
import { cn } from '@/lib/utils'

function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-muted', className)}
      {...props}
    />
  )
}

// Invoice table skeleton
export function InvoiceTableSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center space-x-4 p-4 border rounded">
          <Skeleton className="h-4 w-4" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-6 w-16 rounded-full" />
        </div>
      ))}
    </div>
  )
}

// Dashboard stats skeleton
export function DashboardStatsSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-4" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-8 w-16 mb-2" />
            <Skeleton className="h-3 w-24" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
```

#### B. Implement Loading States

Update `/web/components/invoice/InvoiceDashboard.tsx`:
```typescript
import { InvoiceTableSkeleton, DashboardStatsSkeleton } from '@/components/ui/skeleton'

export function InvoiceDashboard({ onInvoiceSelect }: { onInvoiceSelect?: (invoice: any) => void }) {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading] = useState(true)
  const [initialLoad, setInitialLoad] = useState(true)

  useEffect(() => {
    const loadInvoices = async () => {
      try {
        if (initialLoad) {
          setLoading(true)
        }

        const response = await enhancedInvoiceApi.getInvoices()
        setInvoices(response.invoices)
      } catch (error) {
        console.error('Failed to load invoices:', error)
      } finally {
        setLoading(false)
        setInitialLoad(false)
      }
    }

    loadInvoices()
  }, [initialLoad])

  if (initialLoad && loading) {
    return (
      <div className="space-y-6">
        <DashboardStatsSkeleton />
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent>
            <InvoiceTableSkeleton />
          </CardContent>
        </Card>
      </div>
    )
  }

  // Rest of component...
}
```

### 3. Request Caching with React Query

**Implementation Steps:**

#### A. Add React Query

Install dependencies:
```bash
npm install @tanstack/react-query
```

#### B. Setup Query Client

Create `/web/lib/query-client.tsx`:
```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { useState } from 'react'

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000, // 5 minutes
        cacheTime: 10 * 60 * 1000, // 10 minutes
        retry: 3,
        retryDelay: attemptIndex => Math.min(1000 * 2 ** attemptIndex, 30000),
        refetchOnWindowFocus: false,
      },
    },
  }))

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === 'development' && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  )
}
```

#### C. Update App to Use Query Provider

Update `/web/app/layout.tsx`:
```typescript
import { QueryProvider } from '@/lib/query-client'

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          {children}
        </QueryProvider>
      </body>
    </html>
  )
}
```

#### D. Convert Components to Use React Query

Update `/web/hooks/useInvoices.ts`:
```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { enhancedInvoiceApi } from '@/lib/enhanced-invoice-api'

export function useInvoices(filters?: InvoiceFilters) {
  return useQuery({
    queryKey: ['invoices', filters],
    queryFn: () => enhancedInvoiceApi.getInvoices(filters),
    staleTime: 2 * 60 * 1000, // 2 minutes for invoice list
  })
}

export function useInvoice(id: string) {
  return useQuery({
    queryKey: ['invoice', id],
    queryFn: () => enhancedInvoiceApi.getInvoice(id),
    enabled: !!id,
  })
}

export function useApproveInvoice() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      enhancedInvoiceApi.approveInvoice(id, notes),
    onSuccess: (data, variables) => {
      // Update cache
      queryClient.setQueryData(['invoice', variables.id], data)
      queryClient.invalidateQueries(['invoices'])
    },
    onError: (error) => {
      console.error('Failed to approve invoice:', error)
    },
  })
}

export function useRejectInvoice() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      enhancedInvoiceApi.rejectInvoice(id, reason),
    onSuccess: (data, variables) => {
      // Update cache
      queryClient.setQueryData(['invoice', variables.id], data)
      queryClient.invalidateQueries(['invoices'])
    },
    onError: (error) => {
      console.error('Failed to reject invoice:', error)
    },
  })
}
```

### 4. Conflict Resolution

**Implementation Steps:**

#### A. Add Conflict Detection

Update `/web/hooks/useInvoices.ts`:
```typescript
export function useUpdateInvoice() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Invoice> }) =>
      enhancedInvoiceApi.updateInvoice(id, data),
    onMutate: async ({ id, data }) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries(['invoice', id])

      // Snapshot the previous value
      const previousInvoice = queryClient.getQueryData(['invoice', id])

      // Optimistically update to the new value
      queryClient.setQueryData(['invoice', id], (old: Invoice) => ({
        ...old,
        ...data,
        updated_at: new Date().toISOString(),
      }))

      return { previousInvoice }
    },
    onError: (err, variables, context) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      if (context?.previousInvoice) {
        queryClient.setQueryData(['invoice', variables.id], context.previousInvoice)
      }
    },
    onSettled: (data, error, variables) => {
      // Always refetch after error or success
      queryClient.invalidateQueries(['invoice', variables.id])
    },
  })
}
```

#### B. Create Conflict Resolution Dialog

Create `/web/components/invoice/ConflictResolutionDialog.tsx`:
```typescript
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'

interface ConflictResolutionDialogProps {
  isOpen: boolean
  onClose: () => void
  localInvoice: Invoice
  serverInvoice: Invoice
  onResolve: (resolution: 'local' | 'server' | 'merge') => void
}

export function ConflictResolutionDialog({
  isOpen,
  onClose,
  localInvoice,
  serverInvoice,
  onResolve
}: ConflictResolutionDialogProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Resolve Conflicts</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              This invoice was modified by another user. Please choose which version to keep.
            </AlertDescription>
          </Alert>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <h4 className="font-medium">Your Changes</h4>
              <div className="p-3 border rounded">
                <Badge variant="outline" className="mb-2">
                  Status: {localInvoice.status}
                </Badge>
                {localInvoice.assignedTo && (
                  <p className="text-sm">Assigned to: {localInvoice.assignedTo}</p>
                )}
                <p className="text-xs text-gray-500 mt-2">
                  Last modified: {new Date(localInvoice.updated_at).toLocaleString()}
                </p>
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="font-medium">Server Version</h4>
              <div className="p-3 border rounded">
                <Badge variant="outline" className="mb-2">
                  Status: {serverInvoice.status}
                </Badge>
                {serverInvoice.assignedTo && (
                  <p className="text-sm">Assigned to: {serverInvoice.assignedTo}</p>
                )}
                <p className="text-xs text-gray-500 mt-2">
                  Last modified: {new Date(serverInvoice.updated_at).toLocaleString()}
                </p>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onResolve('server')}>
              Use Server Version
            </Button>
            <Button variant="outline" onClick={() => onResolve('merge')}>
              Merge Changes
            </Button>
            <Button onClick={() => onResolve('local')}>
              Keep My Changes
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

## Testing and Validation

### 1. Integration Testing

Create `/web/tests/integration/real-time-updates.spec.ts`:
```typescript
import { test, expect } from '@playwright/test'

test.describe('Real-time Invoice Updates', () => {
  test('should receive real-time updates for invoice processing', async ({ page }) => {
    await page.goto('/invoices')

    // Monitor WebSocket connections
    const wsMessages: any[] = []
    page.on('websocket', ws => {
      ws.on('framereceived', event => {
        try {
          wsMessages.push(JSON.parse(event.payload as string))
        } catch (e) {
          // Ignore parsing errors
        }
      })
    })

    // Upload an invoice
    await page.click('[data-testid="upload-button"]')
    await page.setInputFiles('input[type="file"]', 'test-invoice.pdf')
    await page.click('[data-testid="upload-submit"]')

    // Wait for processing updates
    await expect(async () => {
      const processingMessages = wsMessages.filter(m => m.type === 'processing_status')
      expect(processingMessages.length).toBeGreaterThan(0)
    }).toPass({ timeout: 30000 })

    // Verify final status
    const completedMessage = wsMessages.find(m =>
      m.type === 'processing_status' && m.data.status === 'completed'
    )
    expect(completedMessage).toBeTruthy()
  })

  test('should handle connection failures gracefully', async ({ page }) => {
    // Simulate connection failure
    await page.route('**/invoices/updates', route => route.abort())

    await page.goto('/invoices')

    // Should show connection status indicator
    await expect(page.locator('[data-testid="connection-status"]')).toContainText('Offline')

    // Should still load invoices via HTTP
    await expect(page.locator('[data-testid="invoice-table"]')).toBeVisible()
  })
})
```

### 2. Error Boundary Testing

Create `/web/tests/integration/error-handling.spec.ts`:
```typescript
test.describe('Error Boundaries', () => {
  test('should show error boundary when API fails', async ({ page }) => {
    // Mock API failure
    await page.route('**/invoices', route =>
      route.fulfill({ status: 500, body: '{"error": "Internal server error"}' })
    )

    await page.goto('/invoices')

    // Should show error boundary instead of crashing
    await expect(page.locator('[data-testid="error-boundary"]')).toBeVisible()
    await expect(page.locator('text=Something went wrong')).toBeVisible()

    // Should provide retry option
    await expect(page.locator('button:has-text("Try Again")')).toBeVisible()
  })

  test('should recover from errors after retry', async ({ page }) => {
    let callCount = 0
    await page.route('**/invoices', route => {
      callCount++
      if (callCount === 1) {
        route.fulfill({ status: 500, body: '{"error": "Internal server error"}' })
      } else {
        route.fulfill({ status: 200, body: '{"invoices": [], "total": 0}' })
      }
    })

    await page.goto('/invoices')

    // Wait for error boundary
    await expect(page.locator('[data-testid="error-boundary"]')).toBeVisible()

    // Click retry
    await page.click('button:has-text("Try Again")')

    // Should recover and show content
    await expect(page.locator('[data-testid="invoice-table"]')).toBeVisible()
    await expect(page.locator('[data-testid="error-boundary"]')).not.toBeVisible()
  })
})
```

### 3. Performance Testing

Create `/web/tests/performance/api-response-times.spec.ts`:
```typescript
test.describe('API Performance', () => {
  test('should load invoices within acceptable time limits', async ({ page }) => {
    const startTime = Date.now()

    await page.goto('/invoices')
    await page.waitForLoadState('networkidle')

    const loadTime = Date.now() - startTime
    expect(loadTime).toBeLessThan(3000) // 3 seconds max
  })

  test('should cache responses and avoid duplicate requests', async ({ page }) => {
    let requestCount = 0
    await page.route('**/invoices', route => {
      requestCount++
      route.fulfill({ status: 200, body: '{"invoices": [], "total": 0}' })
    })

    await page.goto('/invoices')
    await page.waitForLoadState('networkidle')

    // Navigate away and back
    await page.click('[data-testid="analytics-tab"]')
    await page.waitForTimeout(1000)
    await page.click('[data-testid="dashboard-tab"]')
    await page.waitForLoadState('networkidle')

    // Should use cached response, not make new request
    expect(requestCount).toBe(1)
  })
})
```

## Monitoring and Observability

### 1. Performance Metrics

Add to `/web/lib/analytics.ts`:
```typescript
interface PerformanceMetrics {
  apiResponseTime: number
  websocketLatency: number
  cacheHitRate: number
  errorRate: number
  userEngagement: {
    sessionDuration: number
    actionsPerSession: number
    bounceRate: number
  }
}

class PerformanceMonitor {
  private metrics: PerformanceMetrics = {
    apiResponseTime: 0,
    websocketLatency: 0,
    cacheHitRate: 0,
    errorRate: 0,
    userEngagement: {
      sessionDuration: 0,
      actionsPerSession: 0,
      bounceRate: 0
    }
  }

  trackApiResponse(endpoint: string, duration: number, success: boolean) {
    this.metrics.apiResponseTime = duration

    if (!success) {
      this.metrics.errorRate += 1
    }

    // Send to monitoring service
    this.sendMetrics({
      type: 'api_performance',
      endpoint,
      duration,
      success,
      timestamp: Date.now()
    })
  }

  trackWebSocketLatency(latency: number) {
    this.metrics.websocketLatency = latency
    this.sendMetrics({
      type: 'websocket_performance',
      latency,
      timestamp: Date.now()
    })
  }

  private sendMetrics(data: any) {
    // Send to monitoring service (e.g., Sentry, New Relic, custom endpoint)
    if (process.env.NODE_ENV === 'production') {
      fetch('/api/v1/metrics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      }).catch(err => console.error('Failed to send metrics:', err))
    }
  }
}

export const performanceMonitor = new PerformanceMonitor()
```

### 2. Error Monitoring

Update `/web/lib/enhanced-invoice-api.ts`:
```typescript
// Add error tracking
private trackError(error: Error, context: any) {
  performanceMonitor.trackError(error, context)

  // Send to error monitoring service
  if (process.env.NODE_ENV === 'production' && typeof window !== 'undefined' && (window as any).Sentry) {
    (window as any).Sentry.captureException(error, {
      extra: context
    })
  }
}
```

## Deployment Checklist

### Pre-deployment

- [ ] All integration tests passing
- [ ] Error boundaries tested
- [ ] WebSocket connection tested
- [ ] Performance benchmarks met
- [ ] Security review completed
- [ ] Documentation updated

### Post-deployment

- [ ] Monitor error rates
- [ ] Check WebSocket connection success rate
- [ ] Verify API response times
- [ ] Monitor cache hit rates
- [ ] Track user engagement metrics
- [ ] Set up alerts for degraded performance

## Summary

This implementation guide provides comprehensive improvements to the AP Intake system's frontend-backend integration:

**Critical Infrastructure (Week 1-2):**
- Real-time WebSocket integration for live processing updates
- Enhanced error boundaries for graceful failure handling
- Retry logic and caching in the API client
- Processing status tracking for background tasks

**User Experience (Week 3-4):**
- Optimistic updates for responsive interactions
- Loading states and skeletons for better perceived performance
- Request caching with React Query
- Conflict resolution for concurrent edits

**Testing & Monitoring:**
- Comprehensive integration tests
- Performance monitoring and metrics
- Error tracking and alerting
- Production deployment checklist

These improvements will significantly enhance the system's reliability, user experience, and production readiness. The implementation follows modern React patterns and integrates seamlessly with the existing FastAPI backend.

---

**Implementation Timeline:** 4 weeks
**Testing Coverage:** >90%
**Performance Target:** <3 second load times, <500ms API responses
**Reliability Target:** 99.9% uptime, <1% error rate