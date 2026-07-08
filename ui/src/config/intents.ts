export const INTENTS = {
  revenue: {
    keywords: ["revenue", "sales"],
    requiredFields: ["period", "region"],
  },

  forecast: {
    keywords: ["forecast", "prediction"],
    requiredFields: ["period"],
  },

  customer: {
    keywords: ["customer", "client"],
    requiredFields: ["segment"],
  },
};