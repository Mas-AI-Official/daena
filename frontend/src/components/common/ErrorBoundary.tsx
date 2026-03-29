import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw, Home } from 'lucide-react'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

/**
 * Global error boundary that catches rendering errors and shows
 * a friendly recovery UI instead of a white screen.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[ErrorBoundary] Uncaught rendering error:', error)
    console.error('[ErrorBoundary] Component stack:', errorInfo.componentStack)
  }

  private handleReload = (): void => {
    window.location.reload()
  }

  private handleGoHome = (): void => {
    window.location.href = '/chat'
  }

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children
    }

    const errorMessage = this.state.error?.message ?? 'An unexpected error occurred.'

    return (
      <div className="flex-1 flex items-center justify-center min-h-screen bg-midnight-900 px-6">
        <div className="max-w-md w-full text-center space-y-6">
          {/* Icon */}
          <div className="flex justify-center">
            <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
              <AlertTriangle size={32} className="text-amber-400" />
            </div>
          </div>

          {/* Heading */}
          <div className="space-y-2">
            <h1 className="text-xl font-display font-bold text-starlight-100">
              Something went wrong
            </h1>
            <p className="text-sm text-starlight-400">
              An unexpected error prevented this page from rendering.
            </p>
          </div>

          {/* Error details (collapsible) */}
          <details className="text-left rounded-xl bg-midnight-800/50 border border-white/5 overflow-hidden">
            <summary className="px-4 py-3 text-xs font-medium text-starlight-400 cursor-pointer select-none hover:text-starlight-300 transition-colors">
              Show error details
            </summary>
            <pre className="px-4 pb-4 text-xs text-red-400/80 whitespace-pre-wrap break-words font-mono leading-relaxed">
              {errorMessage}
            </pre>
          </details>

          {/* Actions */}
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={this.handleReload}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium transition-colors"
            >
              <RotateCcw size={14} />
              Try Again
            </button>
            <button
              onClick={this.handleGoHome}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white/5 hover:bg-white/10 text-starlight-200 text-sm font-medium border border-white/5 transition-colors"
            >
              <Home size={14} />
              Go Home
            </button>
          </div>
        </div>
      </div>
    )
  }
}
