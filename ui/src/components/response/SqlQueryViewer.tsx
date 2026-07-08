import React, { useState } from "react";
import { Terminal, ChevronDown, ChevronUp, Copy, Check } from "lucide-react";

export interface SqlQueryViewerProps {
  sql: string;
}

export default function SqlQueryViewer({ sql }: SqlQueryViewerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="border border-app-border rounded-lg bg-app-bg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.05)]">
      {/* Header Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-app-bg text-sm font-semibold text-app-text-secondary hover:text-app-text-primary transition-colors focus:outline-none"
      >
        <div className="flex items-center gap-2">
          <Terminal size={15} className="text-app-accent" />
          <span>View Compiled SQL Query</span>
        </div>
        <div className="flex items-center gap-2">
          {isOpen && (
            <button
              onClick={handleCopy}
              className="p-1 rounded text-app-text-secondary hover:text-app-text-primary hover:bg-gray-200 transition-colors"
              title="Copy Query"
            >
              {copied ? <Check size={14} className="text-app-success" /> : <Copy size={14} />}
            </button>
          )}
          {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>

      {/* SQL Body */}
      {isOpen && (
        <div className="p-4 border-t border-app-border bg-[#0F172A] overflow-x-auto text-left">
          <pre className="text-xs text-slate-100 font-mono leading-relaxed select-all whitespace-pre-wrap break-all">
            {sql}
          </pre>
        </div>
      )}
    </div>
  );
}
