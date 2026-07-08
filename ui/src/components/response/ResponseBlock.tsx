import KPICard from "./KPICard";
import DataTable from "./DataTable";
import ForecastCard from "./ForecastCard";
import VisualChart from "./VisualChart";
import SimilarProjects from "./SimilarProjects";
import DocumentReferences from "./DocumentReferences";
import SqlQueryViewer from "./SqlQueryViewer";
import { ResponseBlock as BlockType } from "../../services/api/chatService";
import { AlertCircle, RotateCcw } from "lucide-react";
import QuestionCard from "./QuestionCard";
import { preferencesService } from "../../services/storageService";


export interface ResponseBlockProps {
  blocks: BlockType[];
  onRetry?: () => void;
  onQuestionSelect?: (value: string, sourceQuery?: string) => void;
}

// Simple parser to render basic bold markdown tags (**bold**) to HTML
function renderMarkdownText(text: string) {
  if (!text) return null;
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <p className="text-sm leading-relaxed text-app-text-primary whitespace-pre-wrap">
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={i} className="font-bold text-app-text-primary">
              {part.slice(2, -2)}
            </strong>
          );
        }
        return part;
      })}
    </p>
  );
}

export default function ResponseBlock({ blocks, onRetry, onQuestionSelect }: ResponseBlockProps) {
  const showSql = preferencesService.get().showSql;
  return (
    <div className="w-full space-y-4 py-4 border-b border-app-border first:pt-0 last:border-b-0">
      {blocks.map((block, idx) => {
        switch (block.type) {
          case "text":
            return (
              <div key={idx} className="prose max-w-none text-app-text-primary">
                {renderMarkdownText(block.data)}
              </div>
            );

          case "kpi":
            return (
              <div key={idx} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                <KPICard
                  title={block.data.label || block.data.title}
                  value={block.data.value}
                  trend={block.data.delta}
                  trendDirection={block.data.trend}
                  context={block.data.context}
                />
              </div>
            );

          case "table":
            return (
              <div key={idx} className="my-2">
                <DataTable
                  columns={block.data.columns}
                  rows={block.data.rows}
                  title="sales_query"
                />
              </div>
            );

          case "forecast":
            return (
              <div key={idx} className="my-2">
                <ForecastCard forecast={block.data} />
              </div>
            );

          case "chart":
            return (
              <div key={idx} className="my-2">
                <VisualChart
                  type={block.data.type}
                  data={block.data.data}
                  keys={block.data.keys}
                />
              </div>
            );

          case "similar_projects":
            return (
              <div key={idx} className="my-2">
                <SimilarProjects projects={block.data} />
              </div>
            );

          case "pdf_links":
            return (
              <div key={idx} className="my-2">
                <DocumentReferences documents={block.data} />
              </div>
            );

          case "sql":
            if (!showSql) return null;
            return (
              <div key={idx} className="my-1">
                <SqlQueryViewer sql={block.data} />
              </div>
            );
          case "question":
            return (
              <div key={idx} className="my-2">
                <QuestionCard
                  question={block.data.question}
                  options={block.data.options || []}
                  onSelect={(value) => onQuestionSelect?.(value, block.data.sourceQuery)}
                />
              </div>
            );

          case "error":
            return (
              <div
                key={idx}
                className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-app-error flex gap-3 items-start"
              >
                <AlertCircle className="shrink-0 mt-0.5" size={16} />
                <div className="flex-1 space-y-1">
                  <div className="font-semibold">Query Execution Error</div>
                  <div className="text-red-700">{block.data.message}</div>
                  {block.data.recovery && (
                    <div className="text-xs text-red-600 italic mt-1">
                      Action: {block.data.recovery}
                    </div>
                  )}
                  {onRetry && (
                    <button
                      onClick={onRetry}
                      className="mt-2 inline-flex items-center gap-1 text-xs font-bold text-red-700 hover:text-red-800 transition-colors"
                    >
                      <RotateCcw size={12} />
                      Retry Query
                    </button>
                  )}
                </div>
              </div>
            );

          default:
            return null;
        }
      })}
    </div>
  );
}
