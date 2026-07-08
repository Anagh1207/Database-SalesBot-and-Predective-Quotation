import { useState, useMemo } from "react";
import { ArrowUpDown, ShieldCheck } from "lucide-react";
import { SimilarProject } from "../../services/api/predictionService";

export interface SimilarProjectsProps {
  projects: SimilarProject[];
  onProjectClick?: (project: SimilarProject) => void;
}

type SortKey = "projectName" | "industry" | "revenue" | "matchScore" | "completionDate";

export default function SimilarProjects({ projects, onProjectClick }: SimilarProjectsProps) {
  const [sortKey, setSortKey] = useState<SortKey>("matchScore");
  const [sortAsc, setSortAsc] = useState(false);

  const getScoreBadge = (score: number) => {
    if (score >= 90) return "text-app-success bg-green-50 border-green-200";
    if (score >= 80) return "text-app-warning bg-amber-50 border-amber-200";
    return "text-app-text-secondary bg-gray-50 border-gray-200";
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  const sortedProjects = useMemo(() => {
    const list = [...projects];
    list.sort((a, b) => {
      let valA = a[sortKey];
      let valB = b[sortKey];

      // Handle raw numeric comparisons for revenue and score
      if (sortKey === "revenue") {
        valA = Number(String(valA).replace(/[^0-9.-]/g, ""));
        valB = Number(String(valB).replace(/[^0-9.-]/g, ""));
      }

      if (valA === valB) return 0;
      return valA < valB ? -1 : 1;
    });

    if (!sortAsc) {
      list.reverse();
    }
    return list;
  }, [projects, sortKey, sortAsc]);

  const headers: { label: string; key: SortKey }[] = [
    { label: "Project Name", key: "projectName" },
    { label: "Industry", key: "industry" },
    { label: "Revenue", key: "revenue" },
    { label: "Match Score", key: "matchScore" },
    { label: "Completion Date", key: "completionDate" },
  ];

  return (
    <div className="bg-app-surface border border-app-border rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.05)] overflow-hidden">
      {/* Title */}
      <div className="p-4 border-b border-app-border bg-white flex items-center gap-2 shrink-0">
        <ShieldCheck className="text-app-accent" size={16} />
        <span className="text-sm font-semibold text-app-text-primary">
          Matching Historical Projects
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-full">
          <thead className="bg-app-bg border-b border-app-border">
            <tr>
              {headers.map((h) => (
                <th
                  key={h.key}
                  onClick={() => handleSort(h.key)}
                  className="px-6 py-3 text-xs font-semibold text-app-text-secondary uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none whitespace-nowrap"
                >
                  <div className="flex items-center gap-1">
                    {h.label}
                    <ArrowUpDown size={12} className="text-gray-400" />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-app-border bg-white text-sm text-app-text-primary">
            {sortedProjects.map((proj: SimilarProject, idx: number) => (
              <tr
                key={idx}
                onClick={() => onProjectClick?.(proj)}
                className={`transition-colors ${
                  onProjectClick ? "cursor-pointer hover:bg-app-bg" : "hover:bg-app-bg"
                }`}
              >
                <td className="px-6 py-3.5 whitespace-nowrap text-app-text-primary font-semibold">
                  {proj.projectName}
                </td>
                <td className="px-6 py-3.5 whitespace-nowrap text-app-text-secondary">
                  {proj.industry}
                </td>
                <td className="px-6 py-3.5 whitespace-nowrap text-app-text-primary font-semibold">
                  {proj.revenue}
                </td>
                <td className="px-6 py-3.5 whitespace-nowrap">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold border ${getScoreBadge(proj.matchScore)}`}>
                    {proj.matchScore}% Match
                  </span>
                </td>
                <td className="px-6 py-3.5 whitespace-nowrap text-app-text-secondary">
                  {proj.completionDate}
                </td>
              </tr>
            ))}
            {sortedProjects.length === 0 && (
              <tr>
                <td colSpan={headers.length} className="px-6 py-8 text-center text-app-text-secondary italic">
                  No matching projects found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
