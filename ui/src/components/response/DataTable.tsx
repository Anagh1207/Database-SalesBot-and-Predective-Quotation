import { useState, useMemo } from "react";
import { ArrowUpDown, Download, Search, ChevronLeft, ChevronRight } from "lucide-react";
import { reportService } from "../../services/storageService";
import { preferencesService } from "../../services/storageService";

export interface DataTableProps {
  columns: string[];
  rows: any[][];
  title?: string;
}

function formatHeader(colName: string): string {
  if (!colName) return "";
  const clean = colName.replace(/_/g, " ");
  const lower = clean.toLowerCase();
  if (lower === "total sales gbp" || lower === "total sales") return "Total Sales";
  if (lower === "yoy growth pct" || lower === "yoy growth") return "YoY Growth";
  if (lower === "growth rate") return "Growth Rate";
  if (lower === "sales person") return "Sales Rep";
  if (lower === "customer code") return "Customer";
  if (lower === "product type") return "Product Type";
  if (lower === "job type") return "Job Type";
  if (lower === "sale date") return "Date";
  if (lower === "contract price") return "Contract Value";
  
  return clean.split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

function formatCell(value: any, columnName: string): React.ReactNode {
  if (value === null || value === undefined || String(value).trim() === "" || String(value).trim() === "-") {
    return <span className="text-gray-300">-</span>;
  }
  const name = columnName.toLowerCase();
  
  // Currency formatting
  if (
    name.includes("sales") ||
    name.includes("revenue") ||
    name.includes("price") ||
    name.includes("value") ||
    name.includes("gbp") ||
    name.includes("turnover") ||
    name.includes("amount")
  ) {
    const num = typeof value === "number" ? value : Number(String(value).replace(/[^0-9.-]/g, ""));
    if (!isNaN(num)) {
      return new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 }).format(num);
    }
  }
  
  // Percentage formatting
  if (name.includes("growth") || name.includes("rate") || name.includes("pct") || name.includes("percent")) {
    const num = typeof value === "number" ? value : Number(String(value).replace(/[^0-9.-]/g, ""));
    if (!isNaN(num)) {
      const formatted = `${num > 0 ? "+" : ""}${num.toFixed(1)}%`;
      const colorClass = num > 0 ? "text-green-600 font-semibold" : num < 0 ? "text-red-600 font-semibold" : "text-app-text-primary";
      return <span className={colorClass}>{formatted}</span>;
    }
  }
  
  if (typeof value === "number") {
    return value.toLocaleString();
  }
  
  return String(value);
}

export default function DataTable({ columns, rows, title }: DataTableProps) {
  const compact = preferencesService.get().compactTables;
  const [filterText, setFilterText] = useState("");
  const [sortColumn, setSortColumn] = useState<number | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);

  // Filter rows based on search input
  const filteredRows = useMemo(() => {
    if (!filterText.trim()) return rows;
    const lowerFilter = filterText.toLowerCase();
    return rows.filter((row) =>
      row.some((val) => String(val).toLowerCase().includes(lowerFilter))
    );
  }, [rows, filterText]);

  // Sort rows based on active header selection
  const sortedRows = useMemo(() => {
    if (sortColumn === null) return filteredRows;

    const sorted = [...filteredRows].sort((a, b) => {
      const valA = a[sortColumn];
      const valB = b[sortColumn];

      if (valA === valB) return 0;
      if (valA === null || valA === undefined) return 1;
      if (valB === null || valB === undefined) return -1;

      // Try numeric comparison
      const numA = Number(String(valA).replace(/[^0-9.-]/g, ""));
      const numB = Number(String(valB).replace(/[^0-9.-]/g, ""));

      if (!isNaN(numA) && !isNaN(numB)) {
        return numA - numB;
      }

      // Fallback to string comparison
      return String(valA).localeCompare(String(valB));
    });

    if (sortDirection === "desc") {
      sorted.reverse();
    }
    return sorted;
  }, [filteredRows, sortColumn, sortDirection]);

  // Paginated set
  const paginatedRows = useMemo(() => {
    const startIdx = (currentPage - 1) * pageSize;
    return sortedRows.slice(startIdx, startIdx + pageSize);
  }, [sortedRows, currentPage, pageSize]);

  const totalPages = Math.ceil(sortedRows.length / pageSize) || 1;

  const handleSort = (colIndex: number) => {
    if (sortColumn === colIndex) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(colIndex);
      setSortDirection("asc");
    }
    setCurrentPage(1);
  };

  const handleExportCSV = () => {
    const csvContent = [
      columns.join(","),
      ...sortedRows.map((row) =>
        row
          .map((val) => {
            const strVal = String(val).replace(/"/g, '""');
            return strVal.includes(",") || strVal.includes("\n") || strVal.includes('"')
              ? `"${strVal}"`
              : strVal;
          })
          .join(",")
      ),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `${title || "sales_report"}_export.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    reportService.saveTable(title || "sales_report", columns, sortedRows);
  };

  return (
    <div className="bg-app-surface border border-app-border rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.05)] overflow-hidden">
      {/* Table Action Controls */}
      <div className="p-4 border-b border-app-border flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between bg-white shrink-0">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-app-text-secondary" />
          <input
            type="text"
            placeholder="Filter data..."
            value={filterText}
            onChange={(e) => {
              setFilterText(e.target.value);
              setCurrentPage(1);
            }}
            className="w-full pl-9 pr-4 py-1.5 bg-app-bg text-app-text-primary text-sm border border-app-border rounded-md focus:outline-none focus:ring-1 focus:ring-app-accent focus:border-app-accent placeholder-app-text-secondary"
          />
        </div>
        <div className="flex items-center gap-2 self-end sm:self-auto">
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setCurrentPage(1);
            }}
            className="px-2 py-1.5 bg-white text-app-text-primary text-sm border border-app-border rounded-md focus:outline-none focus:ring-1 focus:ring-app-accent"
          >
            <option value={5}>5 rows</option>
            <option value={10}>10 rows</option>
            <option value={20}>20 rows</option>
            <option value={50}>50 rows</option>
          </select>
          <button
            onClick={handleExportCSV}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-app-bg text-app-text-primary border border-app-border text-sm font-semibold rounded-md transition-colors"
          >
            <Download size={14} />
            Export CSV
          </button>
        </div>
      </div>

      {/* Main Table Grid View with sticky header & horizontal scroll */}
      <div className="overflow-x-auto max-h-[350px]">
        <table className="w-full text-left border-collapse min-w-full">
          <thead className="bg-app-bg sticky top-0 z-10 border-b border-app-border">
            <tr>
              {columns.map((col, idx) => (
                <th
                  key={col}
                  onClick={() => handleSort(idx)}
                  className="px-6 py-3 text-xs font-semibold text-app-text-secondary uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none whitespace-nowrap"
                >
                  <div className="flex items-center gap-1">
                    {formatHeader(col)}
                    <ArrowUpDown size={12} className="text-gray-400" />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-app-border bg-white text-sm text-app-text-primary">
            {paginatedRows.map((row, rIdx) => (
              <tr key={rIdx} className="hover:bg-app-bg transition-colors">
                {row.map((cell, cIdx) => (
                  <td key={cIdx} className={`${compact ? "px-4 py-2" : "px-6 py-3.5"} whitespace-nowrap text-app-text-primary font-medium`}>
                    {formatCell(cell, columns[cIdx])}
                  </td>
                ))}
              </tr>
            ))}
            {paginatedRows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-6 py-10 text-center text-app-text-secondary italic">
                  No matching records found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      <div className="p-4 border-t border-app-border bg-white flex flex-col sm:flex-row items-center justify-between gap-3 text-sm text-app-text-secondary">
        <div>
          Showing {sortedRows.length === 0 ? 0 : (currentPage - 1) * pageSize + 1} to{" "}
          {Math.min(currentPage * pageSize, sortedRows.length)} of {sortedRows.length} entries
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="p-1.5 rounded border border-app-border bg-white text-app-text-secondary hover:text-app-text-primary disabled:opacity-50 disabled:hover:bg-white disabled:pointer-events-none transition-colors"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="font-semibold text-app-text-primary">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="p-1.5 rounded border border-app-border bg-white text-app-text-secondary hover:text-app-text-primary disabled:opacity-50 disabled:hover:bg-white disabled:pointer-events-none transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
