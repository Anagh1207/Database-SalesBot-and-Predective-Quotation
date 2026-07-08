export interface ForecastData {
  forecastedValue: string;
  confidenceScore: number;
  predictionPeriod: string;
  timestamp: string;
  summary: string;
  details: {
    backlogImpact: string;
    seasonalFactor: string;
    negotiationRisk: string;
  };
  chartData: Array<{ name: string; actual: number; predicted: number }>;
}

export interface SimilarProject {
  projectName: string;
  industry: string;
  revenue: string;
  matchScore: number;
  completionDate: string;
}

export interface DocumentReference {
  id: string;
  name: string;
  generatedDate: string;
  url: string;
}

export const predictionService = {
  /**
   * Generates a comprehensive forecast for a given period
   */
  async getForecast(period: string): Promise<{
    message: string;
    forecast: ForecastData;
    similarProjects: SimilarProject[];
    documents: DocumentReference[];
  }> {
    // Simulate API latency
    await new Promise((resolve) => setTimeout(resolve, 800));

    const timestamp = new Date().toLocaleString();

    // Mock data structures tailored for enterprise usage
    const forecast: ForecastData = {
      forecastedValue: "£3.68M",
      confidenceScore: 92.4,
      predictionPeriod: period,
      timestamp,
      summary: "Forecasted revenue shows strong upward momentum driven by high contract conversion rates in the Northern and Midlands regions, combined with a steady pipeline in commercial retrofits.",
      details: {
        backlogImpact: "£1.8M already contracted and secure in the project backlog.",
        seasonalFactor: "Historical Q3 seasonality adds a projected +8.5% bump in retrofit installations.",
        negotiationRisk: "Weighted risk applied to 4 active high-value opportunities currently at the contract negotiation phase.",
      },
      chartData: [
        { name: "Apr", actual: 820000, predicted: 820000 },
        { name: "May", actual: 950000, predicted: 950000 },
        { name: "Jun", actual: 1040000, predicted: 1040000 },
        { name: "Jul", actual: 0, predicted: 1150000 },
        { name: "Aug", actual: 0, predicted: 1220000 },
        { name: "Sep", actual: 0, predicted: 1310000 },
      ],
    };

    const similarProjects: SimilarProject[] = [
      {
        projectName: "Apex Commercial Retrofit",
        industry: "Commercial Real Estate",
        revenue: "£1,240,000",
        matchScore: 94,
        completionDate: "2025-11-15",
      },
      {
        projectName: "Midlands Logistics Hub Phase 2",
        industry: "Logistics & Transport",
        revenue: "£980,000",
        matchScore: 89,
        completionDate: "2026-02-10",
      },
      {
        projectName: "City Plaza Heat Pump Install",
        industry: "Public Sector",
        revenue: "£850,000",
        matchScore: 85,
        completionDate: "2025-08-30",
      },
      {
        projectName: "Brunswick Office Complex Cladding",
        industry: "Commercial Real Estate",
        revenue: "£1,450,000",
        matchScore: 78,
        completionDate: "2024-05-12",
      },
    ];

    const documents: DocumentReference[] = [
      {
        id: "doc-fc-1",
        name: `Q3_Revenue_Forecast_Report_${period.replace(/\s+/g, "_")}.pdf`,
        generatedDate: new Date().toISOString().split("T")[0],
        url: "#",
      },
      {
        id: "doc-fc-2",
        name: "Retrofit_Project_Similarity_Matrix_2026.pdf",
        generatedDate: "2026-05-20",
        url: "#",
      },
    ];

    return {
      message: `I have compiled the sales forecast and estimation results for **${period}**. The model estimates a revenue of **${forecast.forecastedValue}** with a confidence score of **${forecast.confidenceScore}%** based on historical trends and current pipeline backlog.`,
      forecast,
      similarProjects,
      documents,
    };
  },

  /**
   * Matches a new project proposal outline to similar past completed projects
   */
  async matchSimilarProjects(projectSpec: {
    industry: string;
    targetRevenue: number;
  }): Promise<SimilarProject[]> {
    await new Promise((resolve) => setTimeout(resolve, 500));
    return [
      {
        projectName: "Apex Commercial Retrofit",
        industry: projectSpec.industry,
        revenue: "£1,240,000",
        matchScore: 95,
        completionDate: "2025-11-15",
      },
      {
        projectName: "City Plaza Heat Pump Install",
        industry: projectSpec.industry,
        revenue: "£850,000",
        matchScore: 82,
        completionDate: "2025-08-30",
      },
    ];
  }
};
