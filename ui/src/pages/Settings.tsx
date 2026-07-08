import { useEffect, useState } from "react";
import { CheckCircle2, Cpu, Database, Moon, RefreshCw, Save, Sun, User } from "lucide-react";
import { API_BASE } from "../config/api";
import { chatService } from "../services/api/chatService";
import {
  AppPreferences,
  preferencesService,
  profileService,
  UserProfile,
} from "../services/storageService";

export default function Settings() {
  const [profile, setProfile] = useState<UserProfile>(() => profileService.get());
  const [preferences, setPreferences] = useState<AppPreferences>(() => preferencesService.get());
  const [status, setStatus] = useState<"checking" | "online" | "offline">("checking");
  const [busy, setBusy] = useState<"ingest" | "cache" | null>(null);
  const [notice, setNotice] = useState("");

  const checkHealth = async () => {
    setStatus("checking");
    try {
      const response = await fetch(`${API_BASE}/health`);
      setStatus(response.ok ? "online" : "offline");
    } catch {
      setStatus("offline");
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  const saveProfile = () => {
    const initials = profile.name
      .split(/\s+/)
      .map((part) => part[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();
    profileService.save({ ...profile, initials });
    setProfile((current) => ({ ...current, initials }));
    setNotice("Profile saved.");
  };

  const updatePreferences = (next: AppPreferences) => {
    setPreferences(next);
    preferencesService.save(next);
    preferencesService.applyTheme(next.theme);
  };

  const ingest = async () => {
    if (!window.confirm("This replaces the current sales tables with data from the configured Excel file. Continue?")) return;
    setBusy("ingest");
    setNotice("");
    try {
      const result = await chatService.triggerIngestion();
      setNotice(`Ingestion complete: ${Object.entries(result.counts).map(([name, count]) => `${name} ${count}`).join(", ")}.`);
    } catch (error: any) {
      setNotice(error.message || "Ingestion failed.");
    } finally {
      setBusy(null);
      checkHealth();
    }
  };

  const clearCache = async () => {
    setBusy("cache");
    setNotice("");
    try {
      const result = await chatService.bustSchemaCache();
      setNotice(result.detail || "Schema cache cleared.");
    } catch (error: any) {
      setNotice(error.message || "Cache clear failed.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <main className="flex-1 overflow-y-auto px-5 py-6 sm:px-8 space-y-6">
      <header className="border-b border-app-border pb-5">
        <h1 className="text-2xl font-bold tracking-tight text-app-text-primary">Settings</h1>
        <p className="mt-1 text-sm text-app-text-secondary">
          Manage your profile, appearance, data connection, and analytics preferences.
        </p>
      </header>

      {notice && (
        <div className="flex items-center gap-2 rounded-lg border border-app-border bg-app-surface px-4 py-3 text-sm text-app-text-primary">
          <CheckCircle2 size={16} className="text-app-success" /> {notice}
        </div>
      )}

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <div className="rounded-xl border border-app-border bg-app-surface p-5 shadow-sm">
          <div className="mb-5 flex items-center gap-2">
            <User size={18} className="text-app-accent" />
            <h2 className="font-semibold text-app-text-primary">Profile</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="text-xs font-semibold text-app-text-secondary">
              Full name
              <input value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} className="mt-1.5 w-full rounded-lg border border-app-border bg-app-bg px-3 py-2 text-sm text-app-text-primary" />
            </label>
            <label className="text-xs font-semibold text-app-text-secondary">
              Role
              <input value={profile.role} onChange={(e) => setProfile({ ...profile, role: e.target.value })} className="mt-1.5 w-full rounded-lg border border-app-border bg-app-bg px-3 py-2 text-sm text-app-text-primary" />
            </label>
            <label className="text-xs font-semibold text-app-text-secondary sm:col-span-2">
              Email
              <input type="email" value={profile.email} onChange={(e) => setProfile({ ...profile, email: e.target.value })} className="mt-1.5 w-full rounded-lg border border-app-border bg-app-bg px-3 py-2 text-sm text-app-text-primary" />
            </label>
          </div>
          <button onClick={saveProfile} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-app-accent px-4 py-2 text-sm font-semibold text-white hover:bg-app-accent-hover">
            <Save size={15} /> Save profile
          </button>
        </div>

        <div className="rounded-xl border border-app-border bg-app-surface p-5 shadow-sm">
          <div className="mb-5 flex items-center gap-2">
            {document.documentElement.classList.contains("dark") ? <Moon size={18} /> : <Sun size={18} />}
            <h2 className="font-semibold text-app-text-primary">Appearance</h2>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {(["light", "dark", "system"] as const).map((theme) => (
              <button key={theme} onClick={() => updatePreferences({ ...preferences, theme })} className={`rounded-lg border px-3 py-2 text-sm font-semibold capitalize ${preferences.theme === theme ? "border-app-accent bg-app-accent-light text-app-accent" : "border-app-border text-app-text-secondary"}`}>
                {theme}
              </button>
            ))}
          </div>
          <label className="mt-5 flex items-center justify-between gap-3 border-t border-app-border pt-4 text-sm text-app-text-primary">
            Compact analytics tables
            <input type="checkbox" checked={preferences.compactTables} onChange={(e) => updatePreferences({ ...preferences, compactTables: e.target.checked })} className="h-4 w-4 accent-blue-600" />
          </label>
          <label className="mt-3 flex items-center justify-between gap-3 text-sm text-app-text-primary">
            Show generated SQL
            <input type="checkbox" checked={preferences.showSql} onChange={(e) => updatePreferences({ ...preferences, showSql: e.target.checked })} className="h-4 w-4 accent-blue-600" />
          </label>
        </div>

        <div className="rounded-xl border border-app-border bg-app-surface p-5 shadow-sm">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Database size={18} className="text-app-accent" />
              <h2 className="font-semibold text-app-text-primary">Data connection</h2>
            </div>
            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${status === "online" ? "bg-green-50 text-app-success" : status === "offline" ? "bg-red-50 text-app-error" : "bg-app-bg text-app-text-secondary"}`}>
              {status}
            </span>
          </div>
          <p className="text-xs text-app-text-secondary">API: {API_BASE || "Same origin"}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button onClick={checkHealth} className="inline-flex items-center gap-2 rounded-lg border border-app-border px-3 py-2 text-xs font-semibold text-app-text-primary">
              <RefreshCw size={14} className={status === "checking" ? "animate-spin" : ""} /> Test connection
            </button>
            <button onClick={ingest} disabled={busy !== null} className="inline-flex items-center gap-2 rounded-lg bg-app-accent px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">
              <Database size={14} /> {busy === "ingest" ? "Ingesting..." : "Ingest Excel data"}
            </button>
          </div>
        </div>

        <div className="rounded-xl border border-app-border bg-app-surface p-5 shadow-sm">
          <div className="mb-3 flex items-center gap-2">
            <Cpu size={18} className="text-app-accent" />
            <h2 className="font-semibold text-app-text-primary">Schema cache</h2>
          </div>
          <p className="text-sm text-app-text-secondary">
            Refresh reflected table metadata after the database schema changes.
          </p>
          <button onClick={clearCache} disabled={busy !== null} className="mt-4 inline-flex items-center gap-2 rounded-lg border border-app-border px-3 py-2 text-xs font-semibold text-app-text-primary disabled:opacity-50">
            <RefreshCw size={14} className={busy === "cache" ? "animate-spin" : ""} /> Clear schema cache
          </button>
        </div>
      </section>
    </main>
  );
}
