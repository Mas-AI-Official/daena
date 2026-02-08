/**
 * Error Boundary Component
 * Catches JavaScript errors anywhere in the child component tree,
 * logs them, and displays a fallback UI.
 */

import React, { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
    onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
    showDetails: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = {
            hasError: false,
            error: null,
            errorInfo: null,
            showDetails: false
        };
    }

    static getDerivedStateFromError(error: Error): Partial<State> {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        this.setState({ errorInfo });

        // Log to console
        console.error('ErrorBoundary caught an error:', error, errorInfo);

        // Call optional error handler
        this.props.onError?.(error, errorInfo);

        // Show toast notification
        toast.error('An error occurred. Check the error panel for details.');

        // TODO: Send to error reporting service
        // reportError(error, errorInfo);
    }

    handleReload = () => {
        window.location.reload();
    };

    handleGoHome = () => {
        window.location.href = '/';
    };

    handleReset = () => {
        this.setState({
            hasError: false,
            error: null,
            errorInfo: null,
            showDetails: false
        });
    };

    toggleDetails = () => {
        this.setState(prev => ({ showDetails: !prev.showDetails }));
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            const { error, errorInfo, showDetails } = this.state;

            return (
                <div className="min-h-screen bg-neutral-950 flex items-center justify-center p-6">
                    <div className="max-w-2xl w-full bg-neutral-900 border border-neutral-800 rounded-2xl p-8 shadow-xl">
                        {/* Error Icon */}
                        <div className="flex items-center justify-center mb-6">
                            <div className="p-4 bg-red-500/10 rounded-full">
                                <AlertTriangle className="w-12 h-12 text-red-500" />
                            </div>
                        </div>

                        {/* Error Message */}
                        <h1 className="text-2xl font-bold text-white text-center mb-2">
                            Something went wrong
                        </h1>
                        <p className="text-neutral-400 text-center mb-6">
                            An unexpected error occurred. You can try reloading the page or going back to the dashboard.
                        </p>

                        {/* Action Buttons */}
                        <div className="flex gap-4 justify-center mb-6">
                            <button
                                onClick={this.handleReload}
                                className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors"
                            >
                                <RefreshCw className="w-4 h-4" />
                                Reload Page
                            </button>
                            <button
                                onClick={this.handleGoHome}
                                className="flex items-center gap-2 px-4 py-2 bg-neutral-700 hover:bg-neutral-600 text-white rounded-lg transition-colors"
                            >
                                <Home className="w-4 h-4" />
                                Go to Dashboard
                            </button>
                            <button
                                onClick={this.handleReset}
                                className="flex items-center gap-2 px-4 py-2 bg-neutral-800 hover:bg-neutral-700 text-neutral-300 rounded-lg transition-colors"
                            >
                                Try Again
                            </button>
                        </div>

                        {/* Error Details Toggle */}
                        <button
                            onClick={this.toggleDetails}
                            className="w-full flex items-center justify-center gap-2 text-sm text-neutral-500 hover:text-neutral-300 transition-colors"
                        >
                            {showDetails ? (
                                <>
                                    <ChevronUp className="w-4 h-4" />
                                    Hide Technical Details
                                </>
                            ) : (
                                <>
                                    <ChevronDown className="w-4 h-4" />
                                    Show Technical Details
                                </>
                            )}
                        </button>

                        {/* Error Details */}
                        {showDetails && (
                            <div className="mt-4 p-4 bg-neutral-950 border border-neutral-800 rounded-lg overflow-auto max-h-64">
                                <div className="mb-4">
                                    <h3 className="text-sm font-semibold text-red-400 mb-1">Error:</h3>
                                    <code className="text-xs text-neutral-300 font-mono break-all">
                                        {error?.toString()}
                                    </code>
                                </div>
                                {errorInfo?.componentStack && (
                                    <div>
                                        <h3 className="text-sm font-semibold text-yellow-400 mb-1">Component Stack:</h3>
                                        <pre className="text-xs text-neutral-400 font-mono whitespace-pre-wrap overflow-x-auto">
                                            {errorInfo.componentStack}
                                        </pre>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Footer */}
                        <p className="text-xs text-neutral-600 text-center mt-6">
                            Error ID: {Date.now().toString(36).toUpperCase()}
                            {' | '}
                            If this persists, contact support.
                        </p>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

/**
 * Hook-based error boundary wrapper for functional components
 */
export function withErrorBoundary<P extends object>(
    WrappedComponent: React.ComponentType<P>,
    fallback?: ReactNode
) {
    return function WithErrorBoundaryWrapper(props: P) {
        return (
            <ErrorBoundary fallback={fallback}>
                <WrappedComponent {...props} />
            </ErrorBoundary>
        );
    };
}

export default ErrorBoundary;
