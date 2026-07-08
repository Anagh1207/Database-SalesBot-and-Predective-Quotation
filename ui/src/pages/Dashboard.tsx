import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  Compass,
  FileText,
  MessageSquare,
  RefreshCw,
  Users,
} from "lucide-react";
import KPICard from "../components/response/KPICard";
import VisualChart from "../components/response/VisualChart";
import { SAMPLE_QUERIES } from "../constants/sampleQueries";
import { dashboardService } from "../services/api/dashboardService";
import { chatService } from "../services/api/chatService";
import { reportService } from "../services/storageService";

interface DashboardProps {
  onTriggerQuery: (query: string) => void;
}

const money = (value: number) =>
  new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    notation: value >= 1_000_000 ? "compact" : "standard",
    maximumFractionDigits: value >= 1_000_000 ? 2 : 0,
  }).format(value);

export default function Dashboard({ onTriggerQuery }: DashboardProps) {
  const navigate = useNavigate();
  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: dashboardService.getData,
    staleTime: 60_000,
  });

  const conversations = chatService.getConversations().slice(0, 4);
  const reports = reportService.getAll().slice(0, 4);

  const handleQueryClick = (query: string) => {
    onTriggerQuery(query);
    navigate("/chat");
  };

  return (
    <main className="flex-1 overflow-y-auto px-5 py-6 sm:px-8 space-y-6">
      <header className="flex flex-col gap-4 border-b border-app-border pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-app-text-primary">Sales overview</h1>
          <p className="mt-1 text-sm text-app-text-secondary">
            Live commercial performance from the connected sales database.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${
            dashboard.isError
              ? "border-red-200 bg-red-50 text-app-error"
              : "border-green-200 bg-green-50 text-app-success"
          }`}>
            <span className={`h-2 w-2 rounded-full ${dashboard.isError ? "bg-app-error" : "bg-app-success"}`} />
            {dashboard.isError ? "Database unavailable" : dashboard.isPending ? "Connecting..." : "Live data"}
          </span>
          <button
            onClick={() => dashboard.refetch()}
            className="rounded-lg border border-app-border bg-app-surface p-2 text-app-text-secondary hover:text-app-text-primary"
            title="Refresh dashboard"
          >
            <RefreshCw size={16} className={dashboard.isFetching ? "animate-spin" : ""} />
          </button>
        </div>
      </header>

      {dashboard.isError ? (
        <section className="rounded-xl border border-dashed border-app-border bg-app-surface p-8 text-center">
          <BarChart3 className="mx-auto mb-3 text-app-text-secondary" size={28} />
          <h2 className="font-semibold text-app-text-primary">Live analytics are offline</h2>
          <p className="mx-auto mt-1 max-w-lg text-sm text-app-text-secondary">
            Start the FastAPI server and make sure sales data has been ingested. This dashboard does not substitute mock values.
          </p>
          <button
            onClick={() => navigate("/settings")}
            className="mt-4 rounded-lg bg-app-accent px-4 py-2 text-sm font-semibold text-white hover:bg-app-accent-hover"
          >
            Open data settings
          </button>
        </section>
      ) : (
        <>
          <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <KPICard
              title="Total contract value"
              value={dashboard.data ? money(dashboard.data.totalRevenue) : "..."}
              context={`${dashboard.data?.recordCount.toLocaleString() || 0} sales records`}
            />
            <KPICard
              title="Top customer"
              value={dashboard.data?.topCustomer || "..."}
              context={dashboard.data ? money(dashboard.data.topCustomerRevenue) : "Loading"}
            />
            <KPICard
              title="Top salesperson"
              value={dashboard.data?.topSalesperson || "..."}
              context={dashboard.data ? money(dashboard.data.topSalespersonRevenue) : "Loading"}
            />
            <KPICard
              title="Saved analyses"
              value={String(reports.length)}
              context={`${chatService.getConversations().length} conversations available`}
            />
          </section>

          <section className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <div className="xl:col-span-2">
              <div className="mb-2 flex items-center justify-between px-1">
                <span className="text-xs font-semibold uppercase tracking-wider text-app-text-secondary">
                  Quarterly contract value
                </span>
              </div>
              <VisualChart
                type="area"
                data={dashboard.data?.trend || []}
                keys={["revenue"]}
                height={290}
              />
            </div>
            <div className="rounded-xl border border-app-border bg-app-surface p-5 shadow-sm">
              <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-app-text-secondary">
                <Users size={15} className="text-app-accent" />
                Top customers
              </div>
              <div className="space-y-4">
                {(dashboard.data?.topCustomers || []).map((customer, index) => (
                  <div key={customer.name}>
                    <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                      <span className="truncate font-medium text-app-text-primary">
                        {index + 1}. {customer.name}
                      </span>
                      <span className="shrink-0 text-xs font-semibold text-app-text-secondary">
                        {money(customer.revenue)}
                      </span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-app-bg">
                      <div
                        className="h-full rounded-full bg-app-accent"
                        style={{
                          width: `${Math.max(8, (customer.revenue / (dashboard.data?.topCustomerRevenue || 1)) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </>
      )}

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-app-border bg-app-surface p-5 shadow-sm">
          <div className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-app-text-secondary">
            <Compass size={15} className="text-app-accent" />
            Ask your sales data
          </div>
          <div className="grid gap-2">
            {SAMPLE_QUERIES.slice(0, 4).map((query) => (
              <button
                key={query}
                onClick={() => handleQueryClick(query)}
                className="group flex w-full items-center justify-between rounded-lg border border-app-border bg-app-bg/50 p-3 text-left text-sm font-medium text-app-text-primary hover:border-app-accent"
              >
                <span className="truncate pr-3">{query}</span>
                <ArrowRight size={15} className="shrink-0 text-app-text-secondary group-hover:text-app-accent" />
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-app-border bg-app-surface p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-app-text-secondary">
              <MessageSquare size={15} className="text-app-accent" />
              Recent conversations
            </div>
            <button onClick={() => navigate("/history")} className="text-xs font-semibold text-app-accent">
              View all
            </button>
          </div>
          <div className="space-y-2">
            {conversations.length ? conversations.map((conversation) => (
              <button
                key={conversation.id}
                onClick={() => navigate(`/chat/${conversation.id}`)}
                className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left hover:bg-app-bg"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-app-text-primary">{conversation.title}</div>
                  <div className="text-xs text-app-text-secondary">
                    {new Date(conversation.timestamp).toLocaleString()} · {conversation.messages.length} messages
                  </div>
                </div>
                <ArrowRight size={14} className="ml-3 shrink-0 text-app-text-secondary" />
              </button>
            )) : (
              <div className="py-6 text-center text-sm text-app-text-secondary">No conversations yet.</div>
            )}
          </div>
        </div>
      </section>

      {reports.length > 0 && (
        <section className="rounded-xl border border-app-border bg-app-surface p-5 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-app-text-secondary">
              <FileText size={15} className="text-app-accent" />
              Latest saved reports
            </div>
            <button onClick={() => navigate("/reports")} className="text-xs font-semibold text-app-accent">Manage reports</button>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            {reports.map((report) => (
              <button
                key={report.id}
                onClick={() => reportService.download(report)}
                className="flex items-center justify-between rounded-lg border border-app-border p-3 text-left hover:border-app-accent"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-app-text-primary">{report.name}</div>
                  <div className="text-xs text-app-text-secondary">{new Date(report.createdAt).toLocaleDateString()}</div>
                </div>
                <ArrowRight size={14} className="ml-3 shrink-0 text-app-text-secondary" />
              </button>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
