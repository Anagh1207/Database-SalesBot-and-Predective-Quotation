import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Shell from "./components/layout/Shell";
import Dashboard from "./pages/Dashboard";
import ChatWorkspace from "./pages/ChatWorkspace";
import History from "./pages/History";
import SavedReports from "./pages/SavedReports";
import Settings from "./pages/Settings";
import { preferencesService } from "./services/storageService";

// Instantiate the TanStack Query client for API caching and data pre-fetching
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export default function App() {
  const [dashboardQuery, setDashboardQuery] = React.useState<string>("");

  const handleTriggerQuery = (query: string) => {
    setDashboardQuery(query);
  };

  const handleClearQuery = () => {
    setDashboardQuery("");
  };

  React.useEffect(() => {
    const apply = () => preferencesService.applyTheme(preferencesService.get().theme);
    apply();
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Shell onNewChat={handleClearQuery}>
          <Routes>
            {/* Dashboard / Landing */}
            <Route
              path="/"
              element={<Dashboard onTriggerQuery={handleTriggerQuery} />}
            />

            {/* Chat Workspace (New Chat) */}
            <Route
              path="/chat"
              element={
                <ChatWorkspace
                  initialQuery={dashboardQuery}
                  onClearInitialQuery={handleClearQuery}
                />
              }
            />

            {/* Chat Workspace (Active Conversation) */}
            <Route
              path="/chat/:id"
              element={
                <ChatWorkspace
                  initialQuery={dashboardQuery}
                  onClearInitialQuery={handleClearQuery}
                />
              }
            />

            {/* Search History */}
            <Route path="/history" element={<History />} />

            {/* Document References */}
            <Route path="/reports" element={<SavedReports />} />

            {/* Ingestion & Caches admin dashboard */}
            <Route path="/settings" element={<Settings />} />

            {/* Redirect anything else to dashboard */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Shell>
      </Router>
    </QueryClientProvider>
  );
}
