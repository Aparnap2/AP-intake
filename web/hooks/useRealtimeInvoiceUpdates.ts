/**
 * Real-time invoice updates hook using WebSocket
 * Provides live updates for invoice processing status and state changes
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { invoiceApi } from '@/lib/invoice-api'

interface InvoiceUpdate {
  type: 'invoice_updated' | 'processing_status' | 'validation_complete' | 'exception_raised'
  invoiceId: string
  data: any
  timestamp: string
}

interface ProcessingStatus {
  taskId: string
  status: 'pending' | 'processing' | 'parsing' | 'validating' | 'completed' | 'failed'
  progress: number
  stage: string
  message?: string
  error?: string
}

interface UseRealtimeInvoiceUpdatesReturn {
  isConnected: boolean
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'error'
  lastUpdate: InvoiceUpdate | null
  processingStatus: Record<string, ProcessingStatus>
  error: string | null
  reconnect: () => void
  disconnect: () => void
}

export const useRealtimeInvoiceUpdates = (
  invoiceId?: string,
  onInvoiceUpdate?: (update: InvoiceUpdate) => void
): UseRealtimeInvoiceUpdatesReturn => {
  const [isConnected, setIsConnected] = useState(false)
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('connecting')
  const [lastUpdate, setLastUpdate] = useState<InvoiceUpdate | null>(null)
  const [processingStatus, setProcessingStatus] = useState<Record<string, ProcessingStatus>>({})
  const [error, setError] = useState<string | null>(null)

  const websocketRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5

  const connect = useCallback(() => {
    if (websocketRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'}/api/v1/invoices/updates`
      websocketRef.current = new WebSocket(wsUrl)
      setConnectionState('connecting')
      setError(null)

      websocketRef.current.onopen = () => {
        console.log('WebSocket connected for invoice updates')
        setIsConnected(true)
        setConnectionState('connected')
        reconnectAttempts.current = 0

        // Subscribe to specific invoice if provided
        if (invoiceId) {
          websocketRef.current?.send(JSON.stringify({
            type: 'subscribe',
            invoiceId: invoiceId
          }))
        }
      }

      websocketRef.current.onmessage = (event) => {
        try {
          const update: InvoiceUpdate = JSON.parse(event.data)
          setLastUpdate(update)

          // Handle different update types
          switch (update.type) {
            case 'processing_status':
              setProcessingStatus(prev => ({
                ...prev,
                [update.invoiceId]: {
                  taskId: update.data.taskId,
                  status: update.data.status,
                  progress: update.data.progress || 0,
                  stage: update.data.stage,
                  message: update.data.message,
                  error: update.data.error
                }
              }))
              break

            case 'invoice_updated':
              // Clear processing status when invoice is updated
              setProcessingStatus(prev => {
                const updated = { ...prev }
                delete updated[update.invoiceId]
                return updated
              })
              break

            default:
              console.log('Received update:', update)
          }

          // Call callback if provided
          onInvoiceUpdate?.(update)

        } catch (parseError) {
          console.error('Failed to parse WebSocket message:', parseError)
        }
      }

      websocketRef.current.onerror = (event) => {
        console.error('WebSocket error:', event)
        setError('Connection error')
        setConnectionState('error')
        setIsConnected(false)
      }

      websocketRef.current.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason)
        setIsConnected(false)
        setConnectionState('disconnected')

        // Attempt reconnection if not a clean close
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)

          console.log(`Attempting to reconnect in ${delay}ms (attempt ${reconnectAttempts.current}/${maxReconnectAttempts})`)

          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, delay)
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          setError('Failed to reconnect after multiple attempts')
        }
      }

    } catch (err) {
      console.error('Failed to create WebSocket connection:', err)
      setError('Failed to establish connection')
      setConnectionState('error')
    }
  }, [invoiceId, onInvoiceUpdate])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }

    if (websocketRef.current) {
      websocketRef.current.close(1000, 'User disconnected')
      websocketRef.current = null
    }

    setIsConnected(false)
    setConnectionState('disconnected')
    reconnectAttempts.current = 0
  }, [])

  const reconnect = useCallback(() => {
    disconnect()
    setTimeout(connect, 1000)
  }, [disconnect, connect])

  // Initialize connection
  useEffect(() => {
    connect()

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [])

  return {
    isConnected,
    connectionState,
    lastUpdate,
    processingStatus,
    error,
    reconnect,
    disconnect
  }
}

// Hook for processing status updates
export const useProcessingStatus = (taskId: string) => {
  const [status, setStatus] = useState<ProcessingStatus | null>(null)
  const [isComplete, setIsComplete] = useState(false)

  // Poll for status as fallback
  useEffect(() => {
    if (!taskId || isComplete) return

    const pollStatus = async () => {
      try {
        const statusData = await invoiceApi.getProcessingStatus(taskId)
        setStatus(statusData)

        if (statusData.status === 'completed' || statusData.status === 'failed') {
          setIsComplete(true)
        }
      } catch (error) {
        console.error('Failed to fetch processing status:', error)
      }
    }

    // Initial poll
    pollStatus()

    // Set up polling interval
    const interval = setInterval(pollStatus, 2000)

    return () => clearInterval(interval)
  }, [taskId, isComplete])

  return { status, isComplete }
}