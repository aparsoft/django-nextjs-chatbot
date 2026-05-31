"use client";

import { useEffect, useRef, useState, useCallback } from "react";

/**
 * Modern Mermaid Diagram Component
 * Uses official Mermaid v11 with proper React integration
 * 
 * @param {Object} props
 * @param {string} props.chart - Mermaid diagram code
 * @param {string} props.className - Additional CSS classes
 */
export default function MermaidDiagram({ chart, className = "" }) {
    const containerRef = useRef(null);
    const fullscreenContainerRef = useRef(null);
    const [svg, setSvg] = useState("");
    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [zoom, setZoom] = useState(1);
    const [isFullscreen, setIsFullscreen] = useState(false);

    // Handle fullscreen toggle
    const toggleFullscreen = useCallback(async () => {
        try {
            if (!document.fullscreenElement) {
                if (fullscreenContainerRef.current?.requestFullscreen) {
                    await fullscreenContainerRef.current.requestFullscreen();
                } else if (fullscreenContainerRef.current?.webkitRequestFullscreen) {
                    await fullscreenContainerRef.current.webkitRequestFullscreen();
                } else if (fullscreenContainerRef.current?.msRequestFullscreen) {
                    await fullscreenContainerRef.current.msRequestFullscreen();
                }
                setIsFullscreen(true);
            } else {
                if (document.exitFullscreen) {
                    await document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    await document.webkitExitFullscreen();
                } else if (document.msExitFullscreen) {
                    await document.msExitFullscreen();
                }
                setIsFullscreen(false);
            }
        } catch (err) {
            console.error("Fullscreen error:", err);
        }
    }, []);

    // Listen for fullscreen change events
    useEffect(() => {
        const handleFullscreenChange = () => {
            setIsFullscreen(!!document.fullscreenElement);
        };
        
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
        
        return () => {
            document.removeEventListener('fullscreenchange', handleFullscreenChange);
            document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
        };
    }, []);

    useEffect(() => {
        let mounted = true;
        let timeoutId;

        const renderDiagram = async () => {
            if (!chart) {
                console.warn("MermaidDiagram: No chart provided");
                setIsLoading(false);
                return;
            }

            // Set a timeout to prevent infinite loading
            timeoutId = setTimeout(() => {
                if (mounted) {
                    setError("Diagram rendering timed out after 10 seconds");
                    setIsLoading(false);
                }
            }, 10000);

            try {
                setIsLoading(true);
                setError(null);

                console.log("MermaidDiagram: Starting render...");

                // Dynamic import for better bundle size
                const mermaidModule = await import("mermaid");
                const mermaid = mermaidModule.default;

                // Initialize mermaid with configuration
                await mermaid.initialize({
                    startOnLoad: false,
                    theme: "default",
                    securityLevel: "loose",
                    suppressErrors: false,
                    flowchart: {
                        useMaxWidth: false,
                        htmlLabels: true,
                    },
                });

                // Generate unique ID for this diagram
                const id = `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

                // Render the diagram
                const result = await mermaid.render(id, chart);

                clearTimeout(timeoutId);

                if (mounted) {
                    setSvg(result.svg);
                    setError(null);
                }
            } catch (err) {
                console.error("Mermaid rendering error:", err);
                clearTimeout(timeoutId);
                if (mounted) {
                    setError(err.message || err.toString() || "Failed to render diagram");
                }
            } finally {
                if (mounted) {
                    setIsLoading(false);
                }
            }
        };

        renderDiagram();

        return () => {
            mounted = false;
            if (timeoutId) clearTimeout(timeoutId);
        };
    }, [chart]); // Only depend on chart, removed config

    if (isLoading) {
        return (
            <div className={`flex items-center justify-center p-8 bg-gray-50 rounded-lg ${className}`}>
                <div className="flex flex-col items-center gap-3">
                    <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
                    <p className="text-sm text-gray-600">Rendering diagram...</p>
                </div>
            </div>
        );
    }

    if (error) {
        // Check if it's a Mermaid syntax/parse error
        const isParseError = error.includes('Parse error') || error.includes('Syntax error') || error.includes('Expecting');
        
        return (
            <div className={`p-6 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg ${className}`}>
                <div className="flex flex-col items-center gap-4 text-center py-4">
                    <div className="p-3 bg-amber-100 dark:bg-amber-900/40 rounded-full">
                        <svg
                            className="h-8 w-8 text-amber-600 dark:text-amber-400"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                            />
                        </svg>
                    </div>
                    <div>
                        <h3 className="text-base font-semibold text-amber-800 dark:text-amber-200">
                            {isParseError ? 'Diagram Syntax Issue' : 'Unable to Display Diagram'}
                        </h3>
                        <p className="mt-2 text-sm text-amber-700 dark:text-amber-300 max-w-md">
                            {isParseError 
                                ? 'This concept map has a formatting issue and cannot be displayed at the moment. Our team has been notified and will fix it soon.'
                                : 'There was an issue rendering this diagram. Please try again later.'}
                        </p>
                    </div>
                    {/* Show technical details in a collapsible section for debugging */}
                    <details className="mt-2 text-left w-full max-w-lg">
                        <summary className="text-xs text-amber-600 dark:text-amber-400 cursor-pointer hover:underline">
                            Show technical details
                        </summary>
                        <pre className="mt-2 p-3 bg-amber-100 dark:bg-amber-900/30 rounded text-xs text-amber-800 dark:text-amber-200 overflow-x-auto whitespace-pre-wrap break-words">
                            {error}
                        </pre>
                    </details>
                </div>
            </div>
        );
    }

    return (
        <div 
            ref={fullscreenContainerRef}
            className={`relative ${isFullscreen ? 'bg-white dark:bg-gray-900 p-4' : ''}`}
        >
            {/* Scrollable Container with Zoom */}
            <div 
                className={`overflow-auto ${className}`} 
                style={{ maxHeight: isFullscreen ? '100vh' : '600px' }}
            >
                <div
                    ref={containerRef}
                    className="mermaid-container transition-transform duration-200"
                    style={{
                        transform: `scale(${zoom})`,
                        transformOrigin: 'top left',
                        minWidth: 'max-content',
                    }}
                    dangerouslySetInnerHTML={{ __html: svg }}
                />
            </div>

            {/* Zoom Controls - Bottom Right */}
            <div className="absolute bottom-4 right-4 z-20 flex gap-2 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-2">
                <button
                    onClick={() => setZoom(z => Math.max(0.5, z - 0.25))}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                    title="Zoom Out"
                >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" />
                    </svg>
                </button>
                <span className="px-3 py-2 text-sm font-medium">
                    {Math.round(zoom * 100)}%
                </span>
                <button
                    onClick={() => setZoom(z => Math.min(3, z + 0.25))}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                    title="Zoom In"
                >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
                    </svg>
                </button>
                <button
                    onClick={() => setZoom(1)}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                    title="Reset Zoom"
                >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                </button>
                <div className="w-px bg-gray-200 dark:bg-gray-700" />
                <button
                    onClick={toggleFullscreen}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
                    title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
                >
                    {isFullscreen ? (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    ) : (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                        </svg>
                    )}
                </button>
            </div>
        </div>
    );
}
