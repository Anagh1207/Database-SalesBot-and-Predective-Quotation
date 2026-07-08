import { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  MessageSquarePlus,
  History,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
  MessageSquare,
  User,
  Moon,
  Sun
} from "lucide-react";
import { chatService, Conversation } from "../../services/api/chatService";
import {
  APP_DATA_CHANGED,
  preferencesService,
  profileService,
  UserProfile,
} from "../../services/storageService";

interface SidebarProps {
  onNewChat?: () => void;
}

const prefersDark = () => {
  const theme = preferencesService.get().theme;
  return theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
};

export default function Sidebar({ onNewChat }: SidebarProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
    const saved = localStorage.getItem("sales-intelligence-sidebar-collapsed");
    return saved === "true";
  });
  const [recentChats, setRecentChats] = useState<Conversation[]>([]);
  const [profile, setProfile] = useState<UserProfile>(() => profileService.get());
  const [isDark, setIsDark] = useState(prefersDark);

  // Monitor screen size to auto-collapse on tablet/mobile
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setIsCollapsed(true);
      }
    };
    window.addEventListener("resize", handleResize);
    handleResize(); // Initial run
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Fetch recent conversations
  useEffect(() => {
    const loadConversations = () => {
      setRecentChats(chatService.getConversations().slice(0, 5));
    };

    loadConversations();
    
    // Add event listener to capture updates in history
    window.addEventListener("storage", loadConversations);
    window.addEventListener(APP_DATA_CHANGED, loadConversations);
    const interval = setInterval(loadConversations, 2000); // Simple poll for changes

    return () => {
      window.removeEventListener("storage", loadConversations);
      window.removeEventListener(APP_DATA_CHANGED, loadConversations);
      clearInterval(interval);
    };
  }, [location.pathname]);

  useEffect(() => {
    const loadProfile = () => setProfile(profileService.get());
    const loadPreferences = () => setIsDark(prefersDark());
    window.addEventListener(APP_DATA_CHANGED, loadProfile);
    window.addEventListener(APP_DATA_CHANGED, loadPreferences);
    loadPreferences();
    return () => {
      window.removeEventListener(APP_DATA_CHANGED, loadProfile);
      window.removeEventListener(APP_DATA_CHANGED, loadPreferences);
    };
  }, []);

  const toggleTheme = () => {
    const theme = isDark ? "light" : "dark";
    preferencesService.save({ ...preferencesService.get(), theme });
    preferencesService.applyTheme(theme);
    setIsDark(!isDark);
  };

  const toggleCollapse = () => {
    const nextState = !isCollapsed;
    setIsCollapsed(nextState);
    localStorage.setItem("sales-intelligence-sidebar-collapsed", String(nextState));
  };

  const navItems = [
    { label: "Dashboard", icon: LayoutDashboard, path: "/" },
    { label: "New Chat", icon: MessageSquarePlus, path: "/chat", onClick: onNewChat },
    { label: "Chat History", icon: History, path: "/history" },
    { label: "Saved Reports", icon: FileText, path: "/reports" },
    { label: "Settings", icon: Settings, path: "/settings" },
  ];

  return (
    <div
      className={`h-screen flex flex-col bg-app-surface border-r border-app-border transition-all duration-300 ease-in-out select-none ${
        isCollapsed ? "w-[72px]" : "w-[280px]"
      }`}
    >
      {/* Sidebar Header */}
      <div className={`h-[76px] flex items-center border-b border-app-border overflow-hidden ${isCollapsed ? "justify-center px-3" : "justify-between px-5"}`}>
        <Link to="/" className="flex min-w-0 items-center gap-3 font-semibold text-app-text-primary">
          <div className="w-10 h-10 rounded-xl bg-app-accent flex items-center justify-center text-white text-sm font-bold shrink-0 shadow-sm">
            SI
          </div>
          {!isCollapsed && (
            <span className="text-base font-bold tracking-tight text-app-text-primary whitespace-nowrap">
              Sales Intelligence
            </span>
          )}
        </Link>
        {!isCollapsed && (
          <button
            onClick={toggleCollapse}
            className="p-1 rounded-md hover:bg-app-bg text-app-text-secondary hover:text-app-text-primary transition-colors"
            title="Collapse Sidebar"
          >
            <ChevronLeft size={18} />
          </button>
        )}
      </div>

      {/* Navigation Sections */}
      <div className="flex-1 py-4 overflow-y-auto px-3 space-y-6">
        <div className="space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;

            return (
              <Link
                key={item.label}
                to={item.path}
                onClick={item.onClick}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all relative group ${
                  isActive
                    ? "bg-app-accent-light text-app-accent"
                    : "text-app-text-secondary hover:bg-app-bg hover:text-app-text-primary"
                }`}
              >
                <Icon size={18} className="shrink-0" />
                {!isCollapsed && <span className="truncate">{item.label}</span>}
                {isCollapsed && (
                  <div className="absolute left-14 bg-gray-900 text-white text-xs rounded-md px-2 py-1 opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity duration-200 whitespace-nowrap z-50 shadow-md">
                    {item.label}
                  </div>
                )}
              </Link>
            );
          })}
        </div>

        {/* Divider */}
        <hr className="border-app-border mx-1" />

        {/* Recent Conversations */}
        <div className="space-y-2">
          {!isCollapsed && (
            <div className="text-xs font-semibold text-app-text-secondary px-3 uppercase tracking-wider">
              Recent Conversations
            </div>
          )}
          <div className="space-y-1">
            {recentChats.map((chat) => {
              const isActive = location.pathname === `/chat/${chat.id}`;
              const isPrediction = chat.tags.includes("prediction");

              return (
                <button
                  key={chat.id}
                  onClick={() => navigate(`/chat/${chat.id}`)}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-left transition-colors relative group ${
                    isActive
                      ? "bg-app-bg text-app-text-primary font-medium border-l-2 border-app-accent rounded-l-none"
                      : "text-app-text-secondary hover:bg-app-bg hover:text-app-text-primary"
                  }`}
                >
                  {isPrediction ? (
                    <TrendingUp size={16} className="text-app-accent shrink-0" />
                  ) : (
                    <MessageSquare size={16} className="shrink-0" />
                  )}
                  {!isCollapsed && <span className="truncate flex-1">{chat.title}</span>}
                  {isCollapsed && (
                    <div className="absolute left-14 bg-gray-900 text-white text-xs rounded-md px-2 py-1 opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity duration-200 whitespace-nowrap z-50 shadow-md">
                      {chat.title}
                    </div>
                  )}
                </button>
              );
            })}
            {!isCollapsed && recentChats.length === 0 && (
              <div className="text-xs text-app-text-secondary px-3 italic">
                No recent conversations
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Sidebar Collapse Toggle for Collapsed State */}
      {isCollapsed && (
        <div className="p-3 border-t border-app-border flex justify-center">
          <button
            onClick={toggleCollapse}
            className="p-2 rounded-md hover:bg-app-bg text-app-text-secondary hover:text-app-text-primary transition-colors"
            title="Expand Sidebar"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      )}

      {/* User Profile */}
      <div className={`border-t border-app-border p-3 flex items-center gap-2 overflow-hidden shrink-0 ${isCollapsed ? "flex-col" : ""}`}>
        <button
          onClick={() => navigate("/settings")}
          className="flex min-w-0 flex-1 items-center gap-3 rounded-lg p-1.5 text-left hover:bg-app-bg"
          title="Edit profile"
        >
          <div className="w-9 h-9 rounded-full bg-app-accent-light flex items-center justify-center text-app-accent border border-app-border shrink-0 text-xs font-bold">
            {profile.initials || <User size={16} />}
          </div>
        {!isCollapsed && (
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-semibold text-app-text-primary truncate">
              {profile.name}
            </span>
            <span className="text-xs text-app-text-secondary truncate">
              {profile.role}
            </span>
          </div>
        )}
        </button>
        <button
          onClick={toggleTheme}
          className="shrink-0 rounded-lg p-2 text-app-text-secondary hover:bg-app-bg hover:text-app-text-primary"
          title={isDark ? "Use light theme" : "Use dark theme"}
        >
          {isDark ? <Sun size={17} /> : <Moon size={17} />}
        </button>
      </div>
    </div>
  );
}
