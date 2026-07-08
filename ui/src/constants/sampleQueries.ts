export const SAMPLE_QUERIES = [
  "Sales difference between FY 2024/25 and FY 2025/26, and reason for it",
  "Which product types perform best in retrofit projects?",
  "Compare cladding-only customers vs insulation customers",
  "Show the top 5 customers and their total purchase amount",
];

export const WELCOME_MESSAGE = {
  role: "assistant" as const,
  content:
    "**Sales Info V2** connects to your consolidated `sales_data` table so you can explore commercial performance in plain language.\n\nAsk about revenue trends, product mix, customer segments, or fiscal-year comparisons. Results include a written summary, supporting figures, and the underlying SQL when you need to verify the logic.\n\nUse a suggested question below or type your own.",
  isIntro: true,
};
