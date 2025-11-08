/**
 * Error Boundary Component for Graceful Error Handling
 * Catches JavaScript errors in child components and displays fallback UI
 */

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { AlertTriangle, RefreshCw, Bug } from 'lucide-react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  retryCount: number
}

export class ErrorBoundary extends Component<Props, State> {
  private maxRetries = 3

  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      retryCount: 0
    }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return {
      hasError: true,
      error
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)

    this.setState({
      errorInfo
    })

    // Call custom error handler if provided
    this.props.onError?.(error, errorInfo)

    // Report to monitoring service in production
    if (process.env.NODE_ENV === 'production') {
      this.reportError(error, errorInfo)
    }
  }

  private reportError = (error: Error, errorInfo: ErrorInfo) => {
    // Integration with error monitoring services like Sentry, LogRocket, etc.
    try {
      // Example Sentry integration
      if (typeof window !== 'undefined' && (window as any).Sentry) {
        (window as any).Sentry.captureException(error, {
          contexts: {
            react: {
              componentStack: errorInfo.componentStack
            }
          }
        })
      }

      // Example custom error reporting
      fetch('/api/v1/errors/report', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          error: {
            message: error.message,
            stack: error.stack,
            name: error.name
          },
          componentStack: errorInfo.componentStack,
          timestamp: new Date().toISOString(),
          userAgent: navigator.userAgent,
          url: window.location.href
        })
      }).catch(reportError => {
        console.error('Failed to report error:', reportError)
      })
    } catch (reportingError) {
      console.error('Error reporting failed:', reportingError)
    }
  }

  private handleRetry = () => {
    if (this.state.retryCount < this.maxRetries) {
      this.setState(prevState => ({
        hasError: false,
        error: null,
        errorInfo: null,
        retryCount: prevState.retryCount + 1
      }))
    }
  }

  private handleReload = () => {
    window.location.reload()
  }

  private getErrorSeverity = (error: Error): 'low' | 'medium' | 'high' => {
    // Classify error severity based on error message or type
    const message = error.message.toLowerCase()

    if (message.includes('network') || message.includes('fetch') || message.includes('timeout')) {
      return 'low' // Network errors are usually temporary
    }

    if (message.includes('permission') || message.includes('unauthorized')) {
      return 'medium' // Permission issues might need user action
    }

    return 'high' // Other errors are likely application bugs
  }

  private getErrorMessage = (error: Error, severity: 'low' | 'medium' | 'high'): string => {
    // Provide user-friendly error messages based on error type and severity
    const message = error.message.toLowerCase()

    if (message.includes('network') || message.includes('fetch')) {
      return 'Network connection issue. Please check your internet connection and try again.'
    }

    if (message.includes('timeout')) {
      return 'Request timed out. The server is taking longer than expected to respond.'
    }

    if (message.includes('permission') || message.includes('unauthorized')) {
      return 'You don\'t have permission to perform this action. Please contact your administrator.'
    }

    if (message.includes('not found')) {
      return 'The requested resource was not found. It may have been moved or deleted.'
    }

    if (severity === 'high') {
      return 'An unexpected error occurred. Our team has been notified and is working on a fix.'
    }

    return 'Something went wrong. Please try again in a moment.'
  }

  render() {
    if (this.state.hasError && this.state.error) {
      // If custom fallback is provided, use it
      if (this.props.fallback) {
        return this.props.fallback
      }

      const severity = this.getErrorSeverity(this.state.error)
      const userMessage = this.getErrorMessage(this.state.error, severity)
      const canRetry = this.state.retryCount < this.maxRetries

      return (
        <div className="min-h-[200px] flex items-center justify-center p-6">
          <div className="max-w-md w-full space-y-4">
            <Alert variant={severity === 'high' ? 'destructive' : 'default'}>
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Something went wrong</AlertTitle>
              <AlertDescription className="mt-2">
                {userMessage}
              </AlertDescription>
            </Alert>

            <div className="flex flex-col gap-2">
              {canRetry && (
                <Button
                  onClick={this.handleRetry}
                  variant="outline"
                  className="w-full"
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Try Again {this.state.retryCount > 0 && `(${this.state.retryCount}/${this.maxRetries})`}
                </Button>
              )}

              <Button
                onClick={this.handleReload}
                variant="default"
                className="w-full"
              >
                Reload Page
              </Button>
            </div>

            {/* Show error details in development */}
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="mt-4 p-3 bg-gray-100 rounded text-sm">
                <summary className="cursor-pointer font-medium mb-2">
                  <Bug className="inline w-4 h-4 mr-1" />
                  Error Details (Development Only)
                </summary>
                <div className="space-y-2 text-xs">
                  <div>
                    <strong>Error:</strong> {this.state.error.name}
                  </div>
                  <div>
                    <strong>Message:</strong> {this.state.error.message}
                  </div>
                  {this.state.error.stack && (
                    <div>
                      <strong>Stack Trace:</strong>
                      <pre className="mt-1 overflow-auto bg-white p-2 rounded border">
                        {this.state.error.stack}
                      </pre>
                    </div>
                  )}
                  {this.state.errorInfo?.componentStack && (
                    <div>
                      <strong>Component Stack:</strong>
                      <pre className="mt-1 overflow-auto bg-white p-2 rounded border">
                        {this.state.errorInfo.componentStack}
                      </pre>
                    </div>
                  )}
                </div>
              </details>
            )}
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

// Hook for functional components to handle errors
export const useErrorHandler = () => {
  const [error, setError] = React.useState<Error | null>(null)

  const resetError = React.useCallback(() => {
    setError(null)
  }, [])

  const captureError = React.useCallback((error: Error) => {
    console.error('Error captured by useErrorHandler:', error)
    setError(error)

    // Report to monitoring service in production
    if (process.env.NODE_ENV === 'production') {
      // Similar error reporting logic as in ErrorBoundary
      fetch('/api/v1/errors/report', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          error: {
            message: error.message,
            stack: error.stack,
            name: error.name
          },
          timestamp: new Date().toISOString(),
          userAgent: navigator.userAgent,
          url: window.location.href,
          source: 'useErrorHandler'
        })
      }).catch(reportError => {
        console.error('Failed to report error:', reportError)
      })
    }
  }, [])

  // Reset error on route change
  React.useEffect(() => {
    const handleRouteChange = () => {
      resetError()
    }

    window.addEventListener('popstate', handleRouteChange)
    return () => {
      window.removeEventListener('popstate', handleRouteChange)
    }
  }, [resetError])

  return { error, captureError, resetError }
}

// HOC to wrap components with error boundary
export const withErrorBoundary = <P extends object>(
  Component: React.ComponentType<P>,
  fallback?: ReactNode,
  onError?: (error: Error, errorInfo: ErrorInfo) => void
) => {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary fallback={fallback} onError={onError}>
      <Component {...props} />
    </ErrorBoundary>
  )

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`

  return WrappedComponent
}