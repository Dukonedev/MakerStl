import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
        errorInfo: null
    };

    public static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error, errorInfo: null };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("Uncaught error:", error, errorInfo);
        this.setState({ error, errorInfo });
    }

    public render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen bg-black text-red-500 font-mono p-10 overflow-auto">
                    <h1 className="text-2xl font-bold mb-4">CRITICAL SYSTEM FAILURE</h1>
                    <div className="bg-zinc-900 border border-red-900 p-4 rounded mb-4">
                        <h2 className="text-lg font-bold">Error:</h2>
                        <pre className="whitespace-pre-wrap">{this.state.error?.toString()}</pre>
                    </div>
                    <div className="bg-zinc-900 border border-zinc-800 p-4 rounded">
                        <h2 className="text-lg font-bold text-zinc-500">Stack Trace:</h2>
                        <pre className="whitespace-pre-wrap text-xs text-zinc-400">
                            {this.state.errorInfo?.componentStack}
                        </pre>
                    </div>
                    <button
                        onClick={() => {
                            localStorage.clear();
                            window.location.reload();
                        }}
                        className="mt-6 bg-red-600 hover:bg-red-500 text-white px-6 py-3 rounded font-bold uppercase tracking-widest"
                    >
                        HARD RESET (Clear Data)
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
