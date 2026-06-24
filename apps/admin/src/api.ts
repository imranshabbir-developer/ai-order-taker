const API = "/api";
export const RESTAURANT = "hot_bagels_2nd_street";

const path = (p: string) => `${API}${p}`;

export type ToolResponse = {
  status: string;
  message: string;
  line_id?: string;
  options?: string[];
  cart?: Record<string, unknown>;
  spoken_summary?: string;
  sms_summary?: string;
};

export type Scenario = {
  id: string;
  name: string;
  utterance?: string;
};

export type RestaurantInfo = {
  id: string;
  name: string;
  is_mock: boolean;
  item_count: number;
};

export type ConfigResponse = {
  restaurant_id: string;
  is_mock: boolean;
  menu_summary: { name: string; item_count: number; bundle_count: number; modifier_count: number };
  operations: Record<string, unknown>;
  integrations: Record<string, unknown>;
  pronunciations: Record<string, unknown>;
};

export type MenuResponse = {
  categories: Record<string, Array<{ id: string; name: string; base_price_cents: number; category: string }>>;
  bundles: Array<{ id: string; name: string; base_price_cents: number }>;
};

async function apiGet<T>(p: string): Promise<T> {
  const res = await fetch(path(p));
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function apiPost<T>(p: string, body?: unknown): Promise<T> {
  const res = await fetch(path(p), {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function checkHealth(): Promise<boolean> {
  try {
    const d = await apiGet<{ status: string }>("/health");
    return d.status === "ok";
  } catch {
    return false;
  }
}

export async function fetchRestaurants() {
  return apiGet<{ restaurants: RestaurantInfo[] }>("/v1/restaurants");
}

export async function fetchConfig() {
  return apiGet<ConfigResponse>(`/v1/restaurants/${RESTAURANT}/config`);
}

export async function fetchMenu() {
  return apiGet<MenuResponse>(`/v1/restaurants/${RESTAURANT}/menu`);
}

export async function fetchScenarios() {
  return apiGet<{ scenarios: Scenario[] }>(`/v1/restaurants/${RESTAURANT}/scenarios`);
}

export async function resetCall(callId: string) {
  return apiPost(`/v1/restaurants/${RESTAURANT}/calls/${callId}/reset`);
}

export async function runScenario(callId: string, scenarioId: string) {
  return apiPost<ToolResponse>(
    `/v1/restaurants/${RESTAURANT}/calls/${callId}/scenarios/${scenarioId}/run`,
  );
}

export async function fetchCart(callId: string) {
  return apiGet<ToolResponse>(`/v1/restaurants/${RESTAURANT}/calls/${callId}/cart`);
}

export async function runDemoOrder(callId: string) {
  await resetCall(callId);
  await apiPost(`/v1/restaurants/${RESTAURANT}/calls/${callId}/tools/add_item`, {
    item_term: "cream cheese sandwich",
  });
  return apiPost<ToolResponse>(
    `/v1/restaurants/${RESTAURANT}/calls/${callId}/tools/add_item`,
    { item_term: "coffee", requested_modifiers: ["no sugar"] },
  );
}

export function formatPrice(cents: number) {
  return `$${(cents / 100).toFixed(2)}`;
}

export type OrderListItem = {
  order_id: string;
  call_id: string;
  customer_phone: string | null;
  status: string;
  total_cents: number;
  item_count: number;
  created_at: string | null;
  summary_preview: string | null;
};

export type OrderDetail = {
  order_id: string;
  restaurant_id: string;
  call_id: string;
  customer_phone: string | null;
  status: string;
  cart: Record<string, unknown>;
  spoken_summary: string | null;
  sms_summary: string | null;
  created_at: string | null;
  total_cents: number | null;
  payments: Array<{
    charge_id: string;
    amount_cents: number;
    last_four: string | null;
    status: string;
    created_at: string | null;
  }>;
  sms_messages: Array<{
    sms_id: string;
    to_phone: string;
    body: string;
    status: string;
    created_at: string | null;
  }>;
};

export async function fetchOrders(day: "today" | "tomorrow" | "all" = "today") {
  return apiGet<{
    filter: string;
    timezone: string;
    count: number;
    orders: OrderListItem[];
  }>(`/v1/restaurants/${RESTAURANT}/orders?day=${day}`);
}

export async function fetchOrderDetail(orderId: string) {
  return apiGet<OrderDetail>(`/v1/restaurants/${RESTAURANT}/orders/${orderId}`);
}
