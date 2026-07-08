export interface ElicitationResult {
  question: string;
  options: string[];
}

export function getMissingRequirements(_query: string): ElicitationResult | null {
  return null;
}

