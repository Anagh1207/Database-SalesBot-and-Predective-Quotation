import { useState } from "react";
import { TrendingUp, AlertCircle, Clock, ChevronDown, ChevronUp, Share2, FileSpreadsheet } from "lucide-react";
import { ForecastData } from "../../services/api/predictionService";
import { reportService } from "../../services/storageService";

export interface ForecastCardProps {
  forecast: ForecastData;
}

export default function ForecastCard({ forecast }: ForecastCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Confidence color code
  const getConfidenceColor = (score: number) => {
    if (score >= 90) return "text-app-success bg-green-50 border-green-200";
    if (score >= 75) return "text-app-warning bg-amber-50 border-amber-200";
    return "text-app-error bg-red-50 border-red-200";
  };

  const saveForecast = () => {
    reportService.save({
      name: `forecast_${forecast.predictionPeriod.replace(/\s+/g, "_")}.json`,
      type: "forecast",
      description: `${forecast.forecastedValue} forecast at ${forecast.confidenceScore}% confidence`,
      format: "json",
      content: JSON.stringify(forecast, null, 2),
    });
  };

  const shareForecast = async () => {
    const text = `${forecast.predictionPeriod}: ${forecast.forecastedValue} (${forecast.confidenceScore}% confidence)`;
    if (navigator.share) await navigator.share({ title: "Sales forecast", text });
    else await navigator.clipboard.writeText(text);
  };

  return (
    <div className="bg-app-surface border border-app-border rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.05)] overflow-hidden">
      {/* Header Panel */}
      <div className="p-5 border-b border-app-border flex items-center justify-between bg-white">
        <div className="flex items-center gap-2">
          <TrendingUp className="text-app-accent" size={18} />
          <span className="text-sm font-semibold text-app-text-primary">
            Sales Forecast Model Estimate
          </span>
        </div>
        <span className="text-xs text-app-text-secondary flex items-center gap-1">
          <Clock size={12} />
          Generated: {forecast.timestamp.split(",")[0]}
        </span>
      </div>

      {/* Main Prediction Layout */}
      <div className="p-6 bg-white flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-1">
          <span className="text-xs font-semibold text-app-text-secondary uppercase tracking-wider">
            Projected Revenue ({forecast.predictionPeriod})
          </span>
          <div className="flex items-baseline gap-3">
            <span className="text-4xl font-bold tracking-tight text-app-text-primary">
              {forecast.forecastedValue}
            </span>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${getConfidenceColor(
                forecast.confidenceScore
              )}`}
            >
              {forecast.confidenceScore}% Confidence
            </span>
          </div>
          <p className="text-sm text-app-text-secondary max-w-xl mt-2 leading-relaxed">
            {forecast.summary}
          </p>
        </div>

        {/* Actions Pane */}
        <div className="flex flex-row md:flex-col gap-2 shrink-0 self-start md:self-center">
          <button onClick={saveForecast} className="flex items-center gap-1.5 px-3 py-1.5 bg-app-accent hover:bg-app-accent-hover text-white text-xs font-semibold rounded-md transition-colors shadow-sm">
            <FileSpreadsheet size={14} />
            Commit Forecast
          </button>
          <button onClick={shareForecast} className="flex items-center gap-1.5 px-3 py-1.5 bg-app-surface hover:bg-app-bg text-app-text-primary border border-app-border text-xs font-semibold rounded-md transition-colors">
            <Share2 size={14} />
            Share Report
          </button>
        </div>
      </div>

      {/* Expandable Breakdown Drawer */}
      <div className="border-t border-app-border bg-app-bg">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full py-2.5 px-5 flex items-center justify-center gap-1 text-xs font-semibold text-app-text-secondary hover:text-app-text-primary transition-colors focus:outline-none"
        >
          {isExpanded ? (
            <>
              Hide Model Weights
              <ChevronUp size={14} />
            </>
          ) : (
            <>
              Expand Variance & Details
              <ChevronDown size={14} />
            </>
          )}
        </button>

        {isExpanded && (
          <div className="p-5 border-t border-app-border bg-white divide-y divide-app-border text-sm text-app-text-primary">
            <div className="pb-3 flex flex-col sm:flex-row sm:items-center justify-between gap-1">
              <span className="font-medium text-app-text-secondary flex items-center gap-1.5 shrink-0">
                <AlertCircle size={14} className="text-app-accent" />
                Backlog Impact
              </span>
              <span className="sm:text-right font-medium text-app-text-primary">
                {forecast.details.backlogImpact}
              </span>
            </div>
            <div className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-1">
              <span className="font-medium text-app-text-secondary flex items-center gap-1.5 shrink-0">
                <AlertCircle size={14} className="text-app-accent" />
                Seasonal Factor
              </span>
              <span className="sm:text-right font-medium text-app-text-primary">
                {forecast.details.seasonalFactor}
              </span>
            </div>
            <div className="pt-3 flex flex-col sm:flex-row sm:items-center justify-between gap-1">
              <span className="font-medium text-app-text-secondary flex items-center gap-1.5 shrink-0">
                <AlertCircle size={14} className="text-app-warning" />
                Risk Adjustments
              </span>
              <span className="sm:text-right font-medium text-app-text-primary">
                {forecast.details.negotiationRisk}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
