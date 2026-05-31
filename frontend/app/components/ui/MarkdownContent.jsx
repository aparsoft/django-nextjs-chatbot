/**
 * MarkdownContent Component
 * Centralized component for rendering markdown with proper sanitization
 * Handles LaTeX math, unicode bullets, and proper markdown formatting
 */

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { preprocessContentWithTypoFixes } from '@/utils/latexPreprocessor';

export default function MarkdownContent({
    children,
    className = '',
    components = {},
    remarkPlugins = [],
    rehypePlugins = [],
    ...props
}) {
    // Preprocess the content using the centralized latexPreprocessor
    // This handles tab character fixes, LaTeX delimiter conversion, and typos
    const processedContent = preprocessContentWithTypoFixes(children);

    // Default plugins for math support
    // IMPORTANT: remarkMath MUST come before remarkGfm so that math delimiters ($...$)
    // are parsed first, preventing GFM from misinterpreting pipes, underscores, etc. inside math
    const defaultRemarkPlugins = [remarkMath, remarkGfm, ...remarkPlugins];
    const defaultRehypePlugins = [rehypeKatex, ...rehypePlugins];

    // Default prose styling for markdown
    const wrapperClassName = `prose prose-sm max-w-none dark:prose-invert ${className}`;

    return (
        <div className={wrapperClassName}>
            <ReactMarkdown
                remarkPlugins={defaultRemarkPlugins}
                rehypePlugins={defaultRehypePlugins}
                components={components}
                {...props}
            >
                {processedContent}
            </ReactMarkdown>
        </div>
    );
}
