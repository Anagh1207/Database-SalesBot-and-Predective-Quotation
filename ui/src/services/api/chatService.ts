import { API_BASE } from "../../config/api";
import { APP_DATA_CHANGED } from "../storageService";
import { getMissingRequirements } from "./elicitationService";

export interface ResponseBlock {
  type:
    | "text"
    | "kpi"
    | "table"
    | "forecast"
    | "chart"
    | "similar_projects"
    | "pdf_links"
    | "sql"
    | "question"
    | "error";
  data: any;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  timestamp: string;
  content: string;
  blocks: ResponseBlock[];
  intent?: string;
  metadata?: Record<string, any>;
}

export interface Conversation {
  id: string;
  title: string;
  timestamp: string;
  messages: ChatMessage[];
  tags: ("prediction" | "sales-query" | "general")[];
}

const STORAGE_KEY = "sales-intelligence-chat-conversations";
const notify = () => window.dispatchEvent(new CustomEvent(APP_DATA_CHANGED));

function createChartBlock(table: { columns: string[]; rows: any[][] }): ResponseBlock | null {
  if (table.rows.length < 2 || table.columns.length < 2) return null;
  const numericColumns = table.columns
    .map((name, index) => {
      const numeric = table.rows.slice(0, 10).every((row) => row[index] != null && !Number.isNaN(Number(row[index])));
      return numeric ? { name, index } : null;
    })
    .filter(Boolean) as Array<{ name: string; index: number }>;

  if (!numericColumns.length) return null;
  return {
    type: "chart",
    data: {
      type: table.rows.length > 15 ? "area" : "bar",
      keys: numericColumns.map((column) => column.name),
      data: table.rows.map((row) => {
        const point: Record<string, string | number> = { name: String(row[0]) };
        numericColumns.forEach((column) => {
          point[column.name] = Number(row[column.index]);
        });
        return point;
      }),
    },
  };
}

export const chatService = {
  getConversations(): Conversation[] {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    } catch {
      return [];
    }
  },

  saveConversation(conversation: Conversation): void {
    const list = this.getConversations();
    const index = list.findIndex((item) => item.id === conversation.id);
    if (index >= 0) list[index] = conversation;
    else list.unshift(conversation);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
    notify();
  },

  getConversationById(id: string): Conversation | undefined {
    return this.getConversations().find((conversation) => conversation.id === id);
  },

  deleteConversation(id: string): void {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(this.getConversations().filter((conversation) => conversation.id !== id))
    );
    notify();
  },

  searchConversations(
    query: string,
    filters?: { date?: string; tag?: "prediction" | "sales-query" }
  ): Conversation[] {
    let list = this.getConversations();
    const search = query.trim().toLowerCase();
    if (search) {
      list = list.filter(
        (conversation) =>
          conversation.title.toLowerCase().includes(search) ||
          conversation.messages.some((message) => message.content.toLowerCase().includes(search))
      );
    }
    if (filters?.tag) list = list.filter((conversation) => conversation.tags.includes(filters.tag!));
    if (filters?.date && filters.date !== "all") {
      const limit = filters.date === "today" ? 1 : filters.date === "week" ? 7 : 30;
      const now = Date.now();
      list = list.filter(
        (conversation) => (now - new Date(conversation.timestamp).getTime()) / 86_400_000 <= limit
      );
    }
    return list.sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  },

  async sendQuery(
    message: string,
    history: ChatMessage[],
    activeConversationId?: string,
    onStatusChange?: (status: string) => void
  ): Promise<{ conversation: Conversation; responseMessage: ChatMessage }> {
    const promptText = message.trim();
    const prediction = /forecast|predict|estimate|confidence|similar project/i.test(promptText);
    let conversation = activeConversationId
      ? this.getConversationById(activeConversationId)
      : undefined;

    if (!conversation) {
      conversation = {
        id: activeConversationId || `conv-${Date.now()}`,
        title: promptText.length > 45 ? `${promptText.slice(0, 45)}...` : promptText,
        timestamp: new Date().toISOString(),
        messages: [],
        tags: [prediction ? "prediction" : "sales-query"],
      };
    }

    const userMessage: ChatMessage = {
      id: `msg-user-${Date.now()}`,
      role: "user",
      timestamp: new Date().toISOString(),
      content: promptText,
      blocks: [{ type: "text", data: promptText }],
    };
    conversation.messages.push(userMessage);

    const elicitation = getMissingRequirements(promptText);
    if (elicitation) {
      const responseMessage: ChatMessage = {
        id: `msg-assistant-${Date.now() + 1}`,
        role: "assistant",
        timestamp: new Date().toISOString(),
        content: elicitation.question,
        blocks: [{ type: "question", data: { ...elicitation, sourceQuery: promptText } }],
        intent: "requirements_elicitation",
      };
      conversation.messages.push(responseMessage);
      conversation.timestamp = new Date().toISOString();
      this.saveConversation(conversation);
      return { conversation, responseMessage };
    }

    let responseMessage: ChatMessage;
    try {
      onStatusChange?.(prediction ? "Analyzing historical sales data..." : "Querying sales data...");
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: promptText,
          history: history.map(({ role, content }) => ({ role, content })),
          session_id: conversation.id,
        }),
      });
      if (!response.ok) throw new Error(`Sales API returned ${response.status}`);
      const data = await response.json();
      const blocks: ResponseBlock[] = [{ type: "text", data: data.message }];

      if (data.needs_clarification) {
        blocks.push({
          type: "question",
          data: {
            question: data.clarification_question || data.message,
            options: ["This quarter", "This financial year", "All available data"],
            sourceQuery: promptText,
          },
        });
      }
      if (data.meta?.sql) blocks.push({ type: "sql", data: data.meta.sql });
      if (data.table?.rows?.length) {
        blocks.push({ type: "table", data: data.table });
        const chart = createChartBlock(data.table);
        if (chart) blocks.push(chart);
      }
      if (data.similar_projects?.length) {
        blocks.push({ type: "similar_projects", data: data.similar_projects });
      }
      if (data.pdf_links?.length) {
        blocks.push({ type: "pdf_links", data: data.pdf_links });
      }
      if (data.forecast) {
        blocks.push({ type: "forecast", data: data.forecast });
      }

      responseMessage = {
        id: `msg-assistant-${Date.now()}`,
        role: "assistant",
        timestamp: new Date().toISOString(),
        content: data.message,
        blocks,
        intent: data.intent,
        metadata: data.meta,
      };
      if (prediction && !conversation.tags.includes("prediction")) conversation.tags.push("prediction");
    } catch (error: any) {
      responseMessage = {
        id: `msg-assistant-${Date.now()}`,
        role: "assistant",
        timestamp: new Date().toISOString(),
        content: `Error: ${error.message || "Failed to process query."}`,
        blocks: [{
          type: "error",
          data: {
            message: error.message || "The sales database could not be reached.",
            recovery: "Check the backend and database connection, then retry the query.",
          },
        }],
      };
    }

    conversation.messages.push(responseMessage);
    conversation.timestamp = new Date().toISOString();
    this.saveConversation(conversation);
    return { conversation, responseMessage };
  },

  async triggerIngestion(): Promise<{ status: string; counts: Record<string, number>; detail?: string }> {
    const response = await fetch(`${API_BASE}/admin/ingest-excel`, { method: "POST" });
    if (!response.ok) throw new Error("Excel ingestion failed");
    return response.json();
  },

  async bustSchemaCache(): Promise<{ status: string; detail: string }> {
    const response = await fetch(`${API_BASE}/text-to-sql/bust-cache`, { method: "POST" });
    if (!response.ok) throw new Error("Failed to clear schema cache");
    return response.json();
  },
};
