/**
 * Application Routes
 * Centralized definition of all route paths used within the application.
 */
export const ROUTES = {
  LOGIN: "/login",
  DASHBOARD: "/",
  BROKERS: "/brokers",
  INSTRUMENTS: "/instruments",
  POSITIONS: "/positions",
  EXECUTION: "/execution",
  TRADES: "/trades",
  TRADE_ENTRY: "/trade-entry",
  AI_SCANNER: "/ai-scanner",
  F1: "/f1",
  F1_BASKET: "/f1-basket",
  HEALTH: "/health",
  SETTINGS: "/settings",
} as const;