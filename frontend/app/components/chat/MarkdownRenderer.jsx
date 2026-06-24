// app/components/chat/MarkdownRenderer.jsx
"use client";

import { useMemo } from "react";

/**
 * Lightweight markdown renderer for AI chat responses.
 * Supports: headings, bold, italic, code blocks, inline code, links,
 * lists, blockquotes, and paragraphs. No external dependencies.
 */
export default function MarkdownRenderer({ content }) {
  const html = useMemo(() => renderMarkdown(content || ""), [content]);

  return (
    <div
      className="prose prose-sm max-w-none dark:prose-invert"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderMarkdown(md) {
  const lines = md.split("\n");
  let html = "";
  let inCodeBlock = false;
  let codeLang = "";
  let codeContent = "";
  let inList = false;
  let listType = "ul";

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code block fence
    if (line.trim().startsWith("```")) {
      if (inCodeBlock) {
        html += `<pre class="rounded-lg bg-gray-900 p-4 overflow-x-auto my-3"><code class="text-sm text-gray-100">${escapeHtml(codeContent)}</code></pre>`;
        inCodeBlock = false;
        codeContent = "";
        codeLang = "";
      } else {
        inCodeBlock = true;
        codeLang = line.trim().slice(3);
      }
      continue;
    }

    if (inCodeBlock) {
      codeContent += line + "\n";
      continue;
    }

    // Close list if we hit a non-list line
    if (inList && !line.match(/^\s*[-*]\s/) && !line.match(/^\s*\d+\.\s/)) {
      html += `</${listType}>`;
      inList = false;
    }

    // Headings
    if (line.startsWith("### ")) {
      html += `<h3 class="text-base font-semibold mt-4 mb-2">${inline(line.slice(4))}</h3>`;
    } else if (line.startsWith("## ")) {
      html += `<h2 class="text-lg font-semibold mt-4 mb-2">${inline(line.slice(3))}</h2>`;
    } else if (line.startsWith("# ")) {
      html += `<h1 class="text-xl font-bold mt-4 mb-2">${inline(line.slice(2))}</h1>`;
    }
    // Blockquote
    else if (line.startsWith("> ")) {
      html += `<blockquote class="border-l-4 border-gray-300 pl-4 italic text-gray-600 my-2">${inline(line.slice(2))}</blockquote>`;
    }
    // Unordered list
    else if (line.match(/^\s*[-*]\s/)) {
      if (!inList || listType !== "ul") {
        if (inList) html += `</${listType}>`;
        html += `<ul class="list-disc list-inspace my-2 space-y-1">`;
        inList = true;
        listType = "ul";
      }
      html += `<li>${inline(line.replace(/^\s*[-*]\s/, ""))}</li>`;
    }
    // Ordered list
    else if (line.match(/^\s*\d+\.\s/)) {
      if (!inList || listType !== "ol") {
        if (inList) html += `</${listType}>`;
        html += `<ol class="list-decimal list-inside my-2 space-y-1">`;
        inList = true;
        listType = "ol";
      }
      html += `<li>${inline(line.replace(/^\s*\d+\.\s/, ""))}</li>`;
    }
    // Horizontal rule
    else if (line.trim() === "---" || line.trim() === "***") {
      html += `<hr class="my-4 border-gray-200" />`;
    }
    // Empty line
    else if (line.trim() === "") {
      // paragraph break — just skip
    }
    // Regular paragraph
    else {
      html += `<p class="my-1.5 leading-relaxed">${inline(line)}</p>`;
    }
  }

  // Close any open blocks
  if (inCodeBlock) {
    html += `<pre class="rounded-lg bg-gray-900 p-4 overflow-x-auto my-3"><code class="text-sm text-gray-100">${escapeHtml(codeContent)}</code></pre>`;
  }
  if (inList) html += `</${listType}>`;

  return html;
}

function inline(text) {
  return escapeHtml(text)
    // Bold
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // Italic
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // Strikethrough
    .replace(/~~(.+?)~~/g, "<del>$1</del>")
    // Inline code
    .replace(/`(.+?)`/g, '<code class="rounded bg-gray-100 px-1.5 py-0.5 text-sm font-mono">$1</code>')
    // Links
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener" class="text-blue-600 underline">$1</a>',
    );
}