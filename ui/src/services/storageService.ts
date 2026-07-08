import type { ChatMessage } from "./api/chatService";

export interface UserProfile {
  name: string;
  role: string;
  email: string;
  initials: string;
}

export interface AppPreferences {
  theme: "light" | "dark" | "system";
  compactTables: boolean;
  showSql: boolean;
}

export interface SavedReport {
  id: string;
  name: string;
  type: "chat" | "data" | "forecast";
  createdAt: string;
  description: string;
  format: "json" | "csv";
  content: string;
}

const PROFILE_KEY = "sales-intelligence-profile";
const PREFERENCES_KEY = "sales-intelligence-preferences";
const REPORTS_KEY = "sales-intelligence-reports";
export const APP_DATA_CHANGED = "sales-intelligence-data-changed";

const defaultProfile: UserProfile = {
  name: "Alex Carter",
  role: "Senior Sales Analyst",
  email: "alex.carter@company.com",
  initials: "AC",
};

const defaultPreferences: AppPreferences = {
  theme: "system",
  compactTables: false,
  showSql: true,
};

function read<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(key);
    return value ? { ...fallback, ...JSON.parse(value) } : fallback;
  } catch {
    return fallback;
  }
}

function notify() {
  window.dispatchEvent(new CustomEvent(APP_DATA_CHANGED));
}

function downloadText(name: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const profileService = {
  get(): UserProfile {
    return read(PROFILE_KEY, defaultProfile);
  },
  save(profile: UserProfile) {
    localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    notify();
  },
};

export const preferencesService = {
  get(): AppPreferences {
    return read(PREFERENCES_KEY, defaultPreferences);
  },
  save(preferences: AppPreferences) {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(preferences));
    notify();
  },
  applyTheme(theme: AppPreferences["theme"]) {
    const dark =
      theme === "dark" ||
      (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.style.colorScheme = dark ? "dark" : "light";
  },
};

export const reportService = {
  getAll(): SavedReport[] {
    try {
      return JSON.parse(localStorage.getItem(REPORTS_KEY) || "[]");
    } catch {
      return [];
    }
  },
  save(report: Omit<SavedReport, "id" | "createdAt">): SavedReport {
    const saved: SavedReport = {
      ...report,
      id: `report-${Date.now()}`,
      createdAt: new Date().toISOString(),
    };
    localStorage.setItem(REPORTS_KEY, JSON.stringify([saved, ...this.getAll()]));
    notify();
    return saved;
  },
  saveConversation(title: string, messages: ChatMessage[]) {
    return this.save({
      name: `${title.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "") || "conversation"}.json`,
      type: "chat",
      description: `${messages.length} message analytical conversation`,
      format: "json",
      content: JSON.stringify({ title, messages }, null, 2),
    });
  },
  saveTable(name: string, columns: string[], rows: unknown[][]) {
    const escape = (value: unknown) => {
      const text = String(value ?? "").replace(/"/g, '""');
      return /[",\n]/.test(text) ? `"${text}"` : text;
    };
    const content = [columns, ...rows].map((row) => row.map(escape).join(",")).join("\n");
    return this.save({
      name: `${name.replace(/[^a-z0-9]+/gi, "_")}.csv`,
      type: "data",
      description: `${rows.length} rows exported from sales analytics`,
      format: "csv",
      content,
    });
  },
  delete(id: string) {
    localStorage.setItem(REPORTS_KEY, JSON.stringify(this.getAll().filter((r) => r.id !== id)));
    notify();
  },
  download(report: SavedReport) {
    downloadText(
      report.name,
      report.content,
      report.format === "csv" ? "text/csv" : "application/json"
    );
  },
  downloadConversation(title: string, messages: ChatMessage[]) {
    downloadText(
      `${title.replace(/[^a-z0-9]+/gi, "_") || "conversation"}.json`,
      JSON.stringify({ title, messages }, null, 2),
      "application/json"
    );
  },
};
