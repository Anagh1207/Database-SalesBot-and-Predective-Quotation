import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Calendar, Tag, Trash2, ArrowRight, MessageSquare, TrendingUp } from "lucide-react";
import { chatService, Conversation } from "../services/api/chatService";

export default function History() {
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [searchText, setSearchText] = useState("");
  const [dateFilter, setDateFilter] = useState("all");
  const [tagFilter, setTagFilter] = useState("all");

  useEffect(() => {
    loadConversations();
  }, [searchText, dateFilter, tagFilter]);

  const loadConversations = () => {
    const filters: any = {};
    if (dateFilter !== "all") filters.date = dateFilter;
    if (tagFilter !== "all") filters.tag = tagFilter;

    const results = chatService.searchConversations(searchText, filters);
    setConversations(results);
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("Are you sure you want to delete this conversation?")) {
      chatService.deleteConversation(id);
      loadConversations();
    }
  };

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
      {/* Title */}
      <div className="border-b border-app-border pb-5 shrink-0">
        <h1 className="text-2xl font-bold tracking-tight text-app-text-primary">
          Conversation Search & History
        </h1>
        <p className="text-sm text-app-text-secondary">
          Find and review previous analytical inquiries, reports, and forecasts.
        </p>
      </div>

      {/* Filter Bar */}
      <div className="p-4 bg-app-surface border border-app-border rounded-lg flex flex-col md:flex-row gap-4 items-center justify-between shadow-[0_1px_2px_rgba(0,0,0,0.05)] select-none">
        <div className="relative w-full md:max-w-md">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-app-text-secondary" />
          <input
            type="text"
            placeholder="Search keywords in history..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-app-bg text-app-text-primary text-sm border border-app-border rounded-md focus:outline-none focus:ring-1 focus:ring-app-accent focus:border-app-accent placeholder-app-text-secondary"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-end">
          <div className="flex items-center gap-1.5 bg-app-bg border border-app-border rounded-md px-2 py-1.5">
            <Calendar size={14} className="text-app-text-secondary" />
            <select
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="bg-transparent border-none text-xs font-semibold text-app-text-primary focus:ring-0 outline-none cursor-pointer"
            >
              <option value="all">Any Date</option>
              <option value="today">Today</option>
              <option value="week">Past 7 Days</option>
              <option value="month">Past 30 Days</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 bg-app-bg border border-app-border rounded-md px-2 py-1.5">
            <Tag size={14} className="text-app-text-secondary" />
            <select
              value={tagFilter}
              onChange={(e) => setTagFilter(e.target.value)}
              className="bg-transparent border-none text-xs font-semibold text-app-text-primary focus:ring-0 outline-none cursor-pointer"
            >
              <option value="all">All Types</option>
              <option value="sales-query">Sales Queries</option>
              <option value="prediction">Predictions</option>
            </select>
          </div>
        </div>
      </div>

      {/* History Grid/List */}
      <div className="space-y-3">
        {conversations.map((conv) => {
          const isPrediction = conv.tags.includes("prediction");
          return (
            <div
              key={conv.id}
              onClick={() => navigate(`/chat/${conv.id}`)}
              className="flex items-center justify-between p-4 bg-app-surface border border-app-border rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.05)] hover:border-app-accent transition-colors cursor-pointer group"
            >
              <div className="flex items-center gap-4 min-w-0">
                <div className={`p-2.5 rounded-lg shrink-0 ${isPrediction ? "bg-blue-50 text-app-accent" : "bg-slate-100 text-slate-500"}`}>
                  {isPrediction ? <TrendingUp size={20} /> : <MessageSquare size={20} />}
                </div>
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-app-text-primary truncate">
                    {conv.title}
                  </h3>
                  <div className="flex items-center gap-3 text-xs text-app-text-secondary mt-1">
                    <span>{new Date(conv.timestamp).toLocaleDateString()}</span>
                    <span>•</span>
                    <span>{conv.messages.length} messages</span>
                    <span>•</span>
                    <span className="capitalize">{conv.tags.join(", ")}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0 ml-3">
                <button
                  onClick={(e) => handleDelete(conv.id, e)}
                  className="p-2 text-app-text-secondary hover:text-app-error hover:bg-red-50 rounded-md transition-all opacity-0 group-hover:opacity-100 focus:opacity-100"
                  title="Delete conversation"
                >
                  <Trash2 size={15} />
                </button>
                <ArrowRight size={16} className="text-app-text-secondary group-hover:text-app-accent transition-colors" />
              </div>
            </div>
          );
        })}

        {conversations.length === 0 && (
          <div className="text-center py-16 border border-dashed border-app-border rounded-lg text-app-text-secondary italic text-sm">
            No previous conversations match your search.
          </div>
        )}
      </div>
    </div>
  );
}
