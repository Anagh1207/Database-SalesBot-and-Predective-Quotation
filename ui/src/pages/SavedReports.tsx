import { useEffect, useMemo, useState } from "react";
import { Download, FileJson, FileSpreadsheet, Search, Trash2 } from "lucide-react";
import {
  APP_DATA_CHANGED,
  reportService,
  SavedReport,
} from "../services/storageService";

export default function SavedReports() {
  const [reports, setReports] = useState<SavedReport[]>(() => reportService.getAll());
  const [filter, setFilter] = useState<"all" | SavedReport["type"]>("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    const load = () => setReports(reportService.getAll());
    window.addEventListener(APP_DATA_CHANGED, load);
    return () => window.removeEventListener(APP_DATA_CHANGED, load);
  }, []);

  const filtered = useMemo(
    () =>
      reports.filter(
        (report) =>
          (filter === "all" || report.type === filter) &&
          `${report.name} ${report.description}`.toLowerCase().includes(search.toLowerCase())
      ),
    [filter, reports, search]
  );

  const remove = (id: string) => {
    if (window.confirm("Delete this saved report?")) reportService.delete(id);
  };

  return (
    <main className="flex-1 overflow-y-auto px-5 py-6 sm:px-8 space-y-6">
      <header className="border-b border-app-border pb-5">
        <h1 className="text-2xl font-bold tracking-tight text-app-text-primary">Saved reports</h1>
        <p className="mt-1 text-sm text-app-text-secondary">
          Download and manage reports saved from conversations and analytics tables.
        </p>
      </header>

      <section className="flex flex-col gap-3 rounded-xl border border-app-border bg-app-surface p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-sm">
          <Search className="absolute left-3 top-2.5 text-app-text-secondary" size={16} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search saved reports..."
            className="w-full rounded-lg border border-app-border bg-app-bg py-2 pl-9 pr-3 text-sm text-app-text-primary"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {(["all", "chat", "data", "forecast"] as const).map((type) => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-semibold capitalize ${
                filter === type
                  ? "border-app-accent bg-app-accent-light text-app-accent"
                  : "border-app-border bg-app-surface text-app-text-secondary"
              }`}
            >
              {type === "all" ? "All reports" : type}
            </button>
          ))}
        </div>
      </section>

      {filtered.length ? (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {filtered.map((report) => (
            <article key={report.id} className="rounded-xl border border-app-border bg-app-surface p-5 shadow-sm">
              <div className="flex gap-3">
                <div className="rounded-lg bg-app-accent-light p-2.5 text-app-accent">
                  {report.format === "csv" ? <FileSpreadsheet size={20} /> : <FileJson size={20} />}
                </div>
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-sm font-semibold text-app-text-primary" title={report.name}>
                    {report.name}
                  </h2>
                  <p className="mt-1 text-xs text-app-text-secondary">{report.description}</p>
                  <p className="mt-2 text-xs text-app-text-secondary">
                    {new Date(report.createdAt).toLocaleString()} · {report.format.toUpperCase()}
                  </p>
                </div>
              </div>
              <div className="mt-4 flex gap-2 border-t border-app-border pt-3">
                <button
                  onClick={() => reportService.download(report)}
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-app-accent px-3 py-2 text-xs font-semibold text-white hover:bg-app-accent-hover"
                >
                  <Download size={14} /> Download
                </button>
                <button
                  onClick={() => remove(report.id)}
                  className="rounded-lg border border-app-border p-2 text-app-text-secondary hover:border-red-200 hover:bg-red-50 hover:text-app-error"
                  title="Delete report"
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <section className="rounded-xl border border-dashed border-app-border bg-app-surface py-16 text-center">
          <FileSpreadsheet className="mx-auto mb-3 text-app-text-secondary" size={28} />
          <h2 className="font-semibold text-app-text-primary">No saved reports</h2>
          <p className="mt-1 text-sm text-app-text-secondary">
            Save a conversation or export a result table to create one.
          </p>
        </section>
      )}
    </main>
  );
}
