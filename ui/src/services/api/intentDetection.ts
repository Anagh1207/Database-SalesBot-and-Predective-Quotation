import { INTENTS } from "../../config/intents";

export function detectIntent(query: string) {
  const lower = query.toLowerCase();

  for (const [intent, config] of Object.entries(INTENTS)) {
    const matched = config.keywords.some(keyword =>
      lower.includes(keyword)
    );

    if (matched) {
      return intent;
    }
  }

  return null;
}