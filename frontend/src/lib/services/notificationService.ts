import { writable } from "svelte/store";
import { api, ApiError } from "../utils/api";
import type { ChatNotification } from "../stores/chat";

interface NotificationState {
  notifications: ChatNotification[];
  loading: boolean;
  error: string | null;
}

class NotificationService {
  private store = writable<NotificationState>({
    notifications: [],
    loading: false,
    error: null,
  });

  public readonly subscribe = this.store.subscribe;

  async fetchNotifications(unreadOnly: boolean = true): Promise<void> {
    this.update((state) => ({ ...state, loading: true, error: null }));

    try {
      const notifications = await api.getChatNotifications(unreadOnly);
      this.set({
        notifications,
        loading: false,
        error: null,
      });
    } catch (error) {
      const errorMessage = error instanceof ApiError 
        ? error.message 
        : "Failed to fetch notifications";
      
      this.update((state) => ({
        ...state,
        loading: false,
        error: errorMessage,
      }));
      
      console.warn("Failed to fetch notifications:", error);
    }
  }

  async markThreadNotificationsRead(threadId: string): Promise<void> {
    try {
      await api.markChatNotificationsRead(threadId);
      
      // Update local state
      this.update((state) => ({
        ...state,
        notifications: state.notifications.filter(
          (notification) => notification.thread_id !== threadId
        ),
      }));
    } catch (error) {
      console.warn("Failed to mark notifications as read:", error);
      throw error;
    }
  }

  addNotification(notification: ChatNotification): void {
    this.update((state) => ({
      ...state,
      notifications: [notification, ...state.notifications],
    }));
  }

  removeNotification(notificationId: string): void {
    this.update((state) => ({
      ...state,
      notifications: state.notifications.filter(
        (notification) => notification.id !== notificationId
      ),
    }));
  }

  clearError(): void {
    this.update((state) => ({ ...state, error: null }));
  }

  private set(newState: NotificationState): void {
    this.store.set(newState);
  }

  private update(updater: (state: NotificationState) => NotificationState): void {
    this.store.update(updater);
  }
}

export const notificationService = new NotificationService();