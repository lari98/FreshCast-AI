/** Shapes of the demo/API payload. Mirrors scripts/export_demo_data.py. */

export type Lang = "de" | "en";
export type Risk = "low" | "medium" | "high";

export interface Localised {
  de: string;
  en: string;
}

export interface SeriesPoint {
  date: string; // ISO yyyy-mm-dd
  actual: number | null; // null in the future
  lower: number;
  point: number;
  upper: number;
  is_open: boolean;
}

export interface Lot {
  lot_id: string;
  quantity: number;
  use_by: string;
  days_left: number;
  risk: Risk;
}

export interface Proposal {
  recommended_order_units: number;
  usable_stock_units: number;
  expiring_stock_units: number;
  target_stock_units: number;
  order_multiple: number;
  arrival_date: string;
  forecast_units: number;
  safety_stock_units: number;
  outlook_waste_units: number;
  outlook_lost_units: number;
}

export interface Item {
  store_id: string;
  city: string;
  currency: "EUR" | "CHF";
  sku: string;
  name: Localised;
  shelf_life_days: number;
  series: SeriesPoint[];
  lots: Lot[];
  proposal: Proposal;
  explanation: Localised;
}

export interface DashboardData {
  disclaimer: string;
  as_of: string;
  horizon_days: number;
  items: Item[];
}
