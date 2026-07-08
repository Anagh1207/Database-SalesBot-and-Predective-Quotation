import React from "react";
import { FileText, Download, ExternalLink } from "lucide-react";
import { DocumentReference } from "../../services/api/predictionService";
import { reportService } from "../../services/storageService";

export interface DocumentReferencesProps {
  documents: DocumentReference[];
}

export default function DocumentReferences({ documents }: DocumentReferencesProps) {
  const handleDownload = (doc: DocumentReference, e: React.MouseEvent) => {
    e.preventDefault();
    const report = reportService.save({
      name: doc.name.endsWith(".json") ? doc.name : `${doc.name}.json`,
      type: "forecast",
      description: `Reference generated on ${doc.generatedDate}`,
      format: "json",
      content: JSON.stringify(doc, null, 2),
    });
    reportService.download(report);
  };

  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold text-app-text-secondary uppercase tracking-wider px-1">
        Generated Reference Documents
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {documents.map((doc) => (
          <div
            key={doc.id}
            className="flex items-center justify-between p-3.5 bg-app-surface border border-app-border rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.05)] hover:border-gray-300 transition-colors"
          >
            <div className="flex items-center gap-3 min-w-0">
              <div className="p-2 bg-blue-50 text-app-accent rounded shrink-0">
                <FileText size={18} />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-app-text-primary truncate" title={doc.name}>
                  {doc.name}
                </div>
                <div className="text-xs text-app-text-secondary">
                  Generated: {doc.generatedDate}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1 shrink-0 ml-2">
              <button
                onClick={(event) => handleDownload(doc, event)}
                className="p-1.5 rounded text-app-text-secondary hover:text-app-text-primary hover:bg-app-bg transition-colors"
                title="Open report data"
              >
                <ExternalLink size={14} />
              </button>
              <button
                onClick={(e) => handleDownload(doc, e)}
                className="p-1.5 rounded text-app-text-secondary hover:text-app-text-primary hover:bg-app-bg transition-colors"
                title="Download PDF"
              >
                <Download size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
