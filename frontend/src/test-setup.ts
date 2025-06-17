import { vi } from 'vitest';
import '@testing-library/jest-dom';

// Mock WebSocket globally
global.WebSocket = vi.fn(() => ({
  close: vi.fn(),
  send: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  readyState: 1,
  CONNECTING: 0,
  OPEN: 1,
  CLOSING: 2,
  CLOSED: 3
})) as any;

// Mock fetch globally
global.fetch = vi.fn();

// Mock window.location for WebSocket URL construction
Object.defineProperty(window, 'location', {
  value: {
    protocol: 'http:',
    host: 'localhost:3000'
  },
  writable: true
});