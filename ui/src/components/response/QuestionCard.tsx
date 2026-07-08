import { useState } from "react";

interface Props {
  question: string;
  options: string[];
  onSelect?: (value: string) => void;
}

export default function QuestionCard({
  question,
  options,
  onSelect,
}: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <div className="border border-app-border bg-app-bg/50 rounded-lg p-4">
      <h3 className="font-semibold text-sm mb-3">
        {question}
      </h3>

      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option}
            disabled={selected !== null}
            onClick={() => {
              setSelected(option);
              onSelect?.(option);
            }}
            className={`px-3 py-2 text-sm font-medium rounded-md border transition-colors disabled:cursor-not-allowed ${
              selected === option
                ? "border-app-accent bg-app-accent text-white"
                : "border-app-border bg-app-surface hover:border-app-accent"
            }`}
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}
