import { get } from "svelte/store";
import { websocket } from "../stores/websocket";
import type { ChatThread, ChatMessage } from "../stores/chat";

export interface ChatWebSocketEvent {
  type: "chat_update";
  data: {
    type: string;
    thread_id: string;
    message_id?: string;
    title?: string;
    content?: string;
    role?: string;
    status?: string;
    created_at?: string;
    edited_at?: string;
  };
}

export interface ChatUpdateHandlers {
  onThreadCreated: (threadData: Partial<ChatThread>) => void;
  onMessageSent: (messageData: Partial<ChatMessage>) => void;
  onMessageUpdated: (messageData: any) => void;
  onThreadUpdated: (threadId: string, updates: Partial<ChatThread>) => void;
  onThreadDeleted: (threadId: string) => void;
  onNotificationsRead: (threadId: string) => void;
}

export class ChatWebSocketHandler {
  private handlers: ChatUpdateHandlers | null = null;

  constructor() {
    this.initializeWebSocketListener();
  }

  setHandlers(handlers: ChatUpdateHandlers): void {
    this.handlers = handlers;
  }

  private initializeWebSocketListener(): void {
    if (typeof window !== "undefined") {
      websocket.subscribe((wsState) => {
        if (wsState.lastMessage && this.handlers) {
          this.handleWebSocketMessage(wsState.lastMessage);
        }
      });
    }
  }

  private handleWebSocketMessage(event: any): void {
    if (event.type === "chat_update") {
      const { data } = event;

      switch (data.type) {
        case "thread_created":
          this.handlers?.onThreadCreated({
            id: data.thread_id,
            title: data.title,
            status: "ACTIVE" as const,
            created_at: data.created_at,
            metadata: {},
          });
          break;

        case "message_sent":
          this.handlers?.onMessageSent({
            id: data.message_id,
            thread_id: data.thread_id,
            role: data.role?.toUpperCase() as "USER" | "ASSISTANT" | "SYSTEM",
            content: data.content,
            message_type: "TEXT" as const,
            metadata: {},
            created_at: data.created_at,
          });
          break;

        case "message_updated":
          this.handlers?.onMessageUpdated({
            message_id: data.message_id,
            thread_id: data.thread_id,
            content: data.content,
            edited_at: data.edited_at,
          });
          break;

        case "thread_updated":
          this.handlers?.onThreadUpdated(data.thread_id, {
            title: data.title,
            status: data.status,
          });
          break;

        case "thread_deleted":
          this.handlers?.onThreadDeleted(data.thread_id);
          break;

        case "notifications_read":
          this.handlers?.onNotificationsRead(data.thread_id);
          break;

        default:
          console.warn("Unknown chat WebSocket event type:", data.type);
      }
    }
  }
}

export const chatWebSocketHandler = new ChatWebSocketHandler();