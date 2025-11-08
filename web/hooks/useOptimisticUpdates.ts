/**
 * Optimistic Updates Hook for Improved User Experience
 * Provides immediate UI updates with rollback on error
 */

import { useState, useCallback, useRef } from 'react'
import { invoiceApi, Invoice } from '@/lib/invoice-api'

interface OptimisticAction {
  id: string
  type: 'approve' | 'reject' | 'update' | 'delete' | 'assign'
  invoiceId: string
  optimisticData: Partial<Invoice>
  timestamp: number
}

interface UseOptimisticUpdatesReturn {
  pendingActions: OptimisticAction[]
  isUpdating: boolean
  approveInvoice: (invoiceId: string, notes?: string) => Promise<void>
  rejectInvoice: (invoiceId: string, reason: string) => Promise<void>
  updateInvoice: (invoiceId: string, data: Partial<Invoice>) => Promise<void>
  assignInvoice: (invoiceId: string, userId: string) => Promise<void>
  rollbackAction: (actionId: string) => void
  clearCompletedActions: () => void
}

export const useOptimisticUpdates = (
  onInvoiceUpdate?: (invoiceId: string, data: Partial<Invoice>) => void
): UseOptimisticUpdatesReturn => {
  const [pendingActions, setPendingActions] = useState<OptimisticAction[]>([])
  const [isUpdating, setIsUpdating] = useState(false)
  const originalDataRef = useRef<Map<string, Invoice>>(new Map())

  // Store original data for rollback
  const storeOriginalData = useCallback((invoice: Invoice) => {
    originalDataRef.current.set(invoice.id, { ...invoice })
  }, [])

  // Create optimistic action
  const createAction = useCallback((
    type: OptimisticAction['type'],
    invoiceId: string,
    optimisticData: Partial<Invoice>
  ): OptimisticAction => {
    return {
      id: `${type}-${invoiceId}-${Date.now()}`,
      type,
      invoiceId,
      optimisticData,
      timestamp: Date.now()
    }
  }, [])

  // Add optimistic action to queue
  const addOptimisticAction = useCallback((action: OptimisticAction) => {
    setPendingActions(prev => [...prev, action])

    // Apply optimistic update immediately
    onInvoiceUpdate?.(action.invoiceId, action.optimisticData)

    // Auto-remove completed actions after 5 seconds
    setTimeout(() => {
      setPendingActions(prev => prev.filter(a => a.id !== action.id))
    }, 5000)
  }, [onInvoiceUpdate])

  // Remove action from queue
  const removeAction = useCallback((actionId: string) => {
    setPendingActions(prev => prev.filter(action => action.id !== actionId))
  }, [])

  // Rollback action
  const rollbackAction = useCallback((actionId: string) => {
    const action = pendingActions.find(a => a.id === actionId)
    if (!action) return

    const originalInvoice = originalDataRef.current.get(action.invoiceId)
    if (originalInvoice) {
      onInvoiceUpdate?.(action.invoiceId, originalInvoice)
    }

    removeAction(actionId)
  }, [pendingActions, onInvoiceUpdate, removeAction])

  // Clear completed actions
  const clearCompletedActions = useCallback(() => {
    setPendingActions([])
  }, [])

  // Approve invoice with optimistic update
  const approveInvoice = useCallback(async (invoiceId: string, notes?: string) => {
    setIsUpdating(true)

    // Store original data if not already stored
    // In a real app, you'd get this from your state management
    const originalInvoice = originalDataRef.current.get(invoiceId)
    if (!originalInvoice) {
      // Fallback - in real app, this would come from your state
      console.warn('Original invoice data not found for rollback')
    }

    const optimisticData: Partial<Invoice> = {
      status: 'approved',
      reviewedAt: new Date().toISOString()
    }

    const action = createAction('approve', invoiceId, optimisticData)
    addOptimisticAction(action)

    try {
      await invoiceApi.approveInvoice(invoiceId, notes)
      // Success - action will be auto-removed
    } catch (error) {
      console.error('Failed to approve invoice:', error)
      rollbackAction(action.id)
      throw error
    } finally {
      setIsUpdating(false)
    }
  }, [createAction, addOptimisticAction, rollbackAction])

  // Reject invoice with optimistic update
  const rejectInvoice = useCallback(async (invoiceId: string, reason: string) => {
    setIsUpdating(true)

    const optimisticData: Partial<Invoice> = {
      status: 'rejected',
      reviewedAt: new Date().toISOString()
    }

    const action = createAction('reject', invoiceId, optimisticData)
    addOptimisticAction(action)

    try {
      await invoiceApi.rejectInvoice(invoiceId, reason)
    } catch (error) {
      console.error('Failed to reject invoice:', error)
      rollbackAction(action.id)
      throw error
    } finally {
      setIsUpdating(false)
    }
  }, [createAction, addOptimisticAction, rollbackAction])

  // Update invoice with optimistic update
  const updateInvoice = useCallback(async (invoiceId: string, data: Partial<Invoice>) => {
    setIsUpdating(true)

    const action = createAction('update', invoiceId, data)
    addOptimisticAction(action)

    try {
      await invoiceApi.updateInvoice(invoiceId, data)
    } catch (error) {
      console.error('Failed to update invoice:', error)
      rollbackAction(action.id)
      throw error
    } finally {
      setIsUpdating(false)
    }
  }, [createAction, addOptimisticAction, rollbackAction])

  // Assign invoice with optimistic update
  const assignInvoice = useCallback(async (invoiceId: string, userId: string) => {
    setIsUpdating(true)

    const optimisticData: Partial<Invoice> = {
      assignedTo: userId
    }

    const action = createAction('assign', invoiceId, optimisticData)
    addOptimisticAction(action)

    try {
      await invoiceApi.assignInvoice(invoiceId, userId)
    } catch (error) {
      console.error('Failed to assign invoice:', error)
      rollbackAction(action.id)
      throw error
    } finally {
      setIsUpdating(false)
    }
  }, [createAction, addOptimisticAction, rollbackAction])

  return {
    pendingActions,
    isUpdating,
    approveInvoice,
    rejectInvoice,
    updateInvoice,
    assignInvoice,
    rollbackAction,
    clearCompletedActions
  }
}

// Hook for bulk optimistic updates
export const useBulkOptimisticUpdates = () => {
  const [bulkAction, setBulkAction] = useState<{
    type: string
    invoiceIds: string[]
    status: 'pending' | 'processing' | 'completed' | 'failed'
    progress: number
    errors: string[]
  } | null>(null)

  const executeBulkAction = useCallback(async (
    type: 'approve' | 'reject' | 'assign' | 'delete',
    invoiceIds: string[],
    params?: any
  ) => {
    setBulkAction({
      type,
      invoiceIds,
      status: 'processing',
      progress: 0,
      errors: []
    })

    try {
      let result

      switch (type) {
        case 'approve':
          result = await invoiceApi.bulkApprove(invoiceIds, params?.notes)
          break
        case 'reject':
          result = await invoiceApi.bulkReject(invoiceIds, params?.reason)
          break
        case 'assign':
          result = await invoiceApi.bulkAssign(invoiceIds, params?.userId)
          break
        case 'delete':
          result = await invoiceApi.bulkDelete(invoiceIds)
          break
        default:
          throw new Error(`Unknown bulk action type: ${type}`)
      }

      setBulkAction(prev => prev ? {
        ...prev,
        status: 'completed',
        progress: 100,
        errors: result.failed || []
      } : null)

      return result
    } catch (error) {
      setBulkAction(prev => prev ? {
        ...prev,
        status: 'failed',
        errors: [error instanceof Error ? error.message : 'Unknown error']
      } : null)
      throw error
    }
  }, [])

  const resetBulkAction = useCallback(() => {
    setBulkAction(null)
  }, [])

  return {
    bulkAction,
    executeBulkAction,
    resetBulkAction
  }
}

// Hook for conflict resolution
export const useConflictResolution = () => {
  const [conflicts, setConflicts] = useState<Map<string, {
    local: Invoice
    server: Invoice
    resolution?: 'local' | 'server' | 'merge'
  }>>(new Map())

  const detectConflict = useCallback((localInvoice: Invoice, serverInvoice: Invoice): boolean => {
    // Simple conflict detection - in reality, this would be more sophisticated
    return (
      localInvoice.updated_at !== serverInvoice.updated_at &&
      (localInvoice.status !== serverInvoice.status ||
       localInvoice.assignedTo !== serverInvoice.assignedTo)
    )
  }, [])

  const addConflict = useCallback((localInvoice: Invoice, serverInvoice: Invoice) => {
    if (detectConflict(localInvoice, serverInvoice)) {
      setConflicts(prev => new Map(prev).set(localInvoice.id, {
        local: localInvoice,
        server: serverInvoice
      }))
    }
  }, [detectConflict])

  const resolveConflict = useCallback((invoiceId: string, resolution: 'local' | 'server' | 'merge') => {
    setConflicts(prev => {
      const newConflicts = new Map(prev)
      const conflict = newConflicts.get(invoiceId)
      if (conflict) {
        conflict.resolution = resolution
        newConflicts.set(invoiceId, conflict)
      }
      return newConflicts
    })
  }, [])

  const getResolvedInvoice = useCallback((invoiceId: string): Invoice | null => {
    const conflict = conflicts.get(invoiceId)
    if (!conflict) return null

    switch (conflict.resolution) {
      case 'local':
        return conflict.local
      case 'server':
        return conflict.server
      case 'merge':
        // Simple merge strategy - in reality, this would be more sophisticated
        return {
          ...conflict.server,
          // Preserve user changes
          status: conflict.local.status !== conflict.server.status ? conflict.local.status : conflict.server.status,
          assignedTo: conflict.local.assignedTo !== conflict.server.assignedTo ? conflict.local.assignedTo : conflict.server.assignedTo
        }
      default:
        return null
    }
  }, [conflicts])

  const clearConflict = useCallback((invoiceId: string) => {
    setConflicts(prev => {
      const newConflicts = new Map(prev)
      newConflicts.delete(invoiceId)
      return newConflicts
    })
  }, [])

  return {
    conflicts,
    addConflict,
    resolveConflict,
    getResolvedInvoice,
    clearConflict,
    hasConflicts: conflicts.size > 0
  }
}