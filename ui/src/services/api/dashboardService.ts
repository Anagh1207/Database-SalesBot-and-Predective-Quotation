import { API_BASE } from "../../config/api";

interface AnalyticsResult {
  columns: string[];
  rows: unknown[][];
  summary?: string;
}

export interface DashboardData {
  totalRevenue: number;
  recordCount: number;
  topCustomer: string;
  topCustomerRevenue: number;
  topSalesperson: string;
  topSalespersonRevenue: number;
  trend: Array<{ name: string; revenue: number }>;
  topCustomers: Array<{ name: string; revenue: number }>;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(`Dashboard request failed (${response.status})`);
  return response.json();
}

export const dashboardService = {
  async getData(): Promise<DashboardData> {
    const [summary, customers, salespeople, trend] = await Promise.all([
      get<AnalyticsResult>("/sales-summary"),
      get<AnalyticsResult>("/top-customers?limit=5"),
      get<AnalyticsResult>("/salesperson-performance"),
      get<AnalyticsResult>("/sales-trends?period=quarterly"),
    ]);

    const summaryRow = summary.rows[0] || [];
    const firstCustomer = customers.rows[0] || [];
    const firstSalesperson = salespeople.rows[0] || [];

    return {
      totalRevenue: Number(summaryRow[0] || 0),
      recordCount: Number(summaryRow[1] || 0),
      topCustomer: String(firstCustomer[0] || "No data"),
      topCustomerRevenue: Number(firstCustomer[1] || 0),
      topSalesperson: String(firstSalesperson[0] || "No data"),
      topSalespersonRevenue: Number(firstSalesperson[1] || 0),
      topCustomers: customers.rows.map((row) => ({
        name: String(row[0]),
        revenue: Number(row[1] || 0),
      })),
      trend: trend.rows.map((row) => ({
        name: `Q${Number(row[1])} ${Number(row[0])}`,
        revenue: Number(row[2] || 0),
      })),
    };
  },
};
