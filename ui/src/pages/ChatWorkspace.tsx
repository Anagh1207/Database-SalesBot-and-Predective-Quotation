import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Send,
  Search,
  Download,
  Paperclip,
  MessageSquare,
  ArrowRight,
  Save
} from "lucide-react";
import { chatService, ChatMessage } from "../services/api/chatService";
import ResponseBlock from "../components/response/ResponseBlock";
import { WELCOME_MESSAGE, SAMPLE_QUERIES } from "../constants/sampleQueries";
import { reportService } from "../services/storageService";

interface ChatWorkspaceProps {
  initialQuery?: string;
  onClearInitialQuery?: () => void;
}

export default function ChatWorkspace({ initialQuery, onClearInitialQuery }: ChatWorkspaceProps) {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [activeConvId, setActiveConvId] = useState<string | undefined>(id);
  const [currentTitle, setCurrentTitle] = useState("Sales Assistant Workspace");

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Load existing conversation or initialize empty
  useEffect(() => {
    if (id) {
      const conv = chatService.getConversationById(id);
      if (conv) {
        setMessages(conv.messages);
        setActiveConvId(id);
        setCurrentTitle(conv.title);
      } else {
        navigate("/chat");
      }
    } else {
      setMessages([]);
      setActiveConvId(undefined);
      setCurrentTitle("Sales Assistant Workspace");
    }
  }, [id, navigate]);

  // Handle queries passed from the Dashboard
  useEffect(() => {
    if (initialQuery && initialQuery.trim()) {
      handleSend(initialQuery);
      onClearInitialQuery?.();
    }
  }, [initialQuery]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, statusText]);

  // Handle textarea vertical auto-growth (max 6 lines / 150px)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollHeight, 150)}px`;
    }
  }, [input]);

  const handleSend = async (customText?: string) => {
    const text = (customText || input).trim();
    if (!text || loading) return;

    if (!customText) setInput("");
    setLoading(true);

    try {
      const { conversation } = await chatService.sendQuery(
        text,
        messages,
        activeConvId,
        (status: string) => setStatusText(status)
      );

      setMessages(conversation.messages);
      setActiveConvId(conversation.id);
      setCurrentTitle(conversation.title);
      
      // Update browser URL if it's a new conversation
      if (!id) {
        navigate(`/chat/${conversation.id}`, { replace: true });
      }
    } catch (err) {
      console.error("Query submit failure", err);
    } finally {
      setLoading(false);
      setStatusText("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleExport = () => {
    if (messages.length === 0) return;
    reportService.downloadConversation(currentTitle, messages);
  };

  const handleSaveReport = () => {
    if (messages.length > 0) reportService.saveConversation(currentTitle, messages);
  };

  const handleQuestionSelect = (value: string, sourceQuery?: string) => {
    const latestQuery = messages.filter((message) => message.role === "user").at(-1)?.content || "";
    handleSend(`${sourceQuery || latestQuery} ${value}`.trim());
  };

  const handleAttachment = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const excerpt = String(reader.result || "").slice(0, 4000);
      setInput((current) => `${current}${current ? "\n\n" : ""}Attached file: ${file.name}\n${excerpt}`);
    };
    reader.readAsText(file);
    event.target.value = "";
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-app-bg relative">
      {/* Header Panel */}
      <div className="h-[76px] border-b border-app-border bg-app-surface px-6 flex items-center justify-between shrink-0 select-none">
        <div className="flex items-center gap-3 min-w-0">
          <MessageSquare className="text-app-accent shrink-0" size={18} />
          <h1 className="text-sm font-bold text-app-text-primary truncate" title={currentTitle}>
            {currentTitle}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate("/history")}
            className="p-2 text-app-text-secondary hover:text-app-text-primary hover:bg-app-bg rounded-md transition-colors"
            title="Search history"
          >
            <Search size={16} />
          </button>
          <button
            onClick={handleSaveReport}
            disabled={messages.length === 0}
            className="p-2 text-app-text-secondary hover:text-app-text-primary hover:bg-app-bg rounded-md disabled:opacity-50 disabled:pointer-events-none transition-colors"
            title="Save as report"
          >
            <Save size={16} />
          </button>
          <button
            onClick={handleExport}
            disabled={messages.length === 0}
            className="p-2 text-app-text-secondary hover:text-app-text-primary hover:bg-app-bg rounded-md disabled:opacity-50 disabled:pointer-events-none transition-colors"
            title="Export conversation"
          >
            <Download size={16} />
          </button>
        </div>
      </div>

      {/* Chat History View Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="max-w-2xl mx-auto py-12 px-4 space-y-8">
            <div className="space-y-3">
              <h2 className="text-xl font-bold tracking-tight text-app-text-primary">
                Sales Information Core Workspace
              </h2>
              <p className="text-sm text-app-text-secondary leading-relaxed whitespace-pre-wrap">
                {WELCOME_MESSAGE.content}
              </p>
            </div>

            {/* Quick action triggers */}
            <div className="space-y-2.5">
              <div className="text-xs font-semibold text-app-text-secondary uppercase tracking-wider">
                Explore Consolidated Sales Data
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {SAMPLE_QUERIES.map((query: string) => (
                  <button
                    key={query}
                    onClick={() => handleSend(query)}
                    className="text-left p-3.5 bg-app-surface border border-app-border rounded-lg text-xs font-semibold text-app-text-primary hover:border-app-accent hover:bg-blue-50/20 transition-all flex items-center justify-between group shadow-sm"
                  >
                    <span className="truncate pr-2">{query}</span>
                    <ArrowRight size={14} className="text-app-text-secondary group-hover:text-app-accent transition-colors shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((message) => {
          const isUser = message.role === "user";

          return (
            <div
              key={message.id}
              className={`max-w-4xl mx-auto flex gap-4 ${
                isUser ? "justify-end" : "justify-start"
              }`}
            >
              <div className="flex-1">
                {isUser ? (
                  // User bubble
                  <div className="flex justify-end">
                    <div className="bg-app-surface border border-app-border text-sm font-semibold text-app-text-primary px-4 py-2.5 rounded-lg shadow-sm max-w-[85%] break-words">
                      {message.content}
                    </div>
                  </div>
                ) : (
                  // Assistant report style blocks
                  <div className="bg-app-surface border border-app-border rounded-lg p-5 shadow-[0_1px_2px_rgba(0,0,0,0.05)]">
                    <ResponseBlock
                      blocks={message.blocks}
                      onRetry={() => handleSend(message.content)}
                      onQuestionSelect={handleQuestionSelect}
                    />
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Model Execution status logs */}
        {loading && (
          <div className="max-w-4xl mx-auto flex justify-start">
            <div className="bg-app-surface border border-app-border rounded-lg p-5 shadow-[0_1px_2px_rgba(0,0,0,0.05)] w-full flex items-center gap-3">
              <div className="flex gap-1.5 items-center justify-center shrink-0">
                <span className="w-1.5 h-1.5 rounded-full bg-app-accent animate-bounce" />
                <span className="w-1.5 h-1.5 rounded-full bg-app-accent animate-bounce [animation-delay:0.2s]" />
                <span className="w-1.5 h-1.5 rounded-full bg-app-accent animate-bounce [animation-delay:0.4s]" />
              </div>
              <span className="text-xs font-semibold text-app-text-secondary tracking-wide uppercase">
                {statusText || "Processing query..."}
              </span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input controls box */}
      <div className="p-4 bg-app-surface border-t border-app-border shrink-0 select-none">
        <div className="max-w-4xl mx-auto relative flex items-end gap-2 bg-app-bg border border-app-border rounded-lg px-3 py-2 focus-within:ring-1 focus-within:ring-app-accent focus-within:border-app-accent">
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="p-1.5 text-app-text-secondary hover:text-app-text-primary hover:bg-app-surface rounded-md transition-colors shrink-0"
            title="Attach a text or CSV file"
          >
            <Paperclip size={16} />
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.csv,.json,.md"
            className="hidden"
            onChange={handleAttachment}
          />
          
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about sales performance, forecasts, revenue, opportunities, or project estimates..."
            className="flex-1 max-h-[150px] resize-none overflow-y-auto bg-transparent border-0 outline-none text-sm text-app-text-primary py-1 px-1 focus:ring-0 focus:outline-none placeholder-app-text-secondary"
          />

          <button
            type="button"
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            className="p-1.5 bg-app-accent text-white hover:bg-app-accent-hover rounded-md shadow-sm disabled:opacity-40 disabled:hover:bg-app-accent disabled:cursor-not-allowed transition-all shrink-0"
          >
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
