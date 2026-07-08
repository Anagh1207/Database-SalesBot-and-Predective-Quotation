import React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

export interface VisualChartProps {
  type?: "line" | "bar" | "area";
  data: Array<Record<string, any>>;
  keys?: string[];
  xAxisKey?: string;
  height?: number;
}

export default function VisualChart({
  type = "line",
  data,
  keys,
  xAxisKey = "name",
  height = 300,
}: VisualChartProps) {
  // If keys are not provided, auto-detect numeric fields excluding xAxisKey
  const chartKeys = React.useMemo(() => {
    if (keys && keys.length > 0) return keys;
    if (data.length === 0) return [];
    
    // Find all keys in the first data object that have numeric values
    return Object.keys(data[0]).filter((key) => {
      if (key === xAxisKey) return false;
      const val = data[0][key];
      return typeof val === "number" && !isNaN(val);
    });
  }, [data, keys, xAxisKey]);

  // Color sequence for multiple series
  const colors = ["#2563EB", "#16A34A", "#D97706", "#DC2626", "#7C3AED", "#0891B2"];

  // Custom formatted tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white border border-app-border rounded-lg p-3 shadow-sm text-xs font-sans">
          <p className="font-semibold text-app-text-primary mb-1">{label}</p>
          <div className="space-y-1">
            {payload.map((item: any, index: number) => (
              <div key={index} className="flex items-center gap-4 justify-between">
                <span className="flex items-center gap-1.5 text-app-text-secondary">
                  <span
                    className="w-2.5 h-2.5 rounded-full inline-block"
                    style={{ backgroundColor: item.color || item.fill }}
                  />
                  {item.name}
                </span>
                <span className="font-bold text-app-text-primary">
                  {typeof item.value === "number" ? item.value.toLocaleString() : item.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      );
    }
    return null;
  };

  const renderChart = () => {
    switch (type) {
      case "bar":
        return (
          <BarChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
            <XAxis
              dataKey={xAxisKey}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#6B7280", fontSize: 11, fontFamily: "Inter" }}
              dy={8}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#6B7280", fontSize: 11, fontFamily: "Inter" }}
              tickFormatter={(v) => (v >= 1000000 ? `£${(v / 1000000).toFixed(1)}M` : v >= 1000 ? `£${(v / 1000).toFixed(0)}K` : v)}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "#F8FAFC" }} />
            <Legend
              verticalAlign="top"
              height={36}
              iconType="circle"
              iconSize={8}
              wrapperStyle={{ fontSize: 11, fontFamily: "Inter", color: "#6B7280" }}
            />
            {chartKeys.map((key, idx) => (
              <Bar
                key={key}
                dataKey={key}
                fill={colors[idx % colors.length]}
                radius={[4, 4, 0, 0]}
                maxBarSize={40}
              />
            ))}
          </BarChart>
        );

      case "area":
        return (
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <defs>
              {chartKeys.map((key, idx) => (
                <linearGradient key={key} id={`colorUv-${idx}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={colors[idx % colors.length]} stopOpacity={0.2} />
                  <stop offset="95%" stopColor={colors[idx % colors.length]} stopOpacity={0.0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
            <XAxis
              dataKey={xAxisKey}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#6B7280", fontSize: 11, fontFamily: "Inter" }}
              dy={8}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#6B7280", fontSize: 11, fontFamily: "Inter" }}
              tickFormatter={(v) => (v >= 1000000 ? `£${(v / 1000000).toFixed(1)}M` : v >= 1000 ? `£${(v / 1000).toFixed(0)}K` : v)}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              verticalAlign="top"
              height={36}
              iconType="circle"
              iconSize={8}
              wrapperStyle={{ fontSize: 11, fontFamily: "Inter", color: "#6B7280" }}
            />
            {chartKeys.map((key, idx) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[idx % colors.length]}
                strokeWidth={2}
                fillOpacity={1}
                fill={`url(#colorUv-${idx})`}
              />
            ))}
          </AreaChart>
        );

      case "line":
      default:
        return (
          <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F1F5F9" />
            <XAxis
              dataKey={xAxisKey}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#6B7280", fontSize: 11, fontFamily: "Inter" }}
              dy={8}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fill: "#6B7280", fontSize: 11, fontFamily: "Inter" }}
              tickFormatter={(v) => (v >= 1000000 ? `£${(v / 1000000).toFixed(1)}M` : v >= 1000 ? `£${(v / 1000).toFixed(0)}K` : v)}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              verticalAlign="top"
              height={36}
              iconType="circle"
              iconSize={8}
              wrapperStyle={{ fontSize: 11, fontFamily: "Inter", color: "#6B7280" }}
            />
            {chartKeys.map((key, idx) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[idx % colors.length]}
                strokeWidth={2}
                dot={{ r: 3, strokeWidth: 1 }}
                activeDot={{ r: 5 }}
              />
            ))}
          </LineChart>
        );
    }
  };

  return (
    <div className="bg-app-surface border border-app-border rounded-lg p-5 shadow-[0_1px_2px_rgba(0,0,0,0.05)] select-none">
      <div className="w-full" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
