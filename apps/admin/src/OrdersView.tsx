import { useCallback, useEffect, useState } from "react";
import {
  fetchOrderDetail,
  fetchOrders,
  formatPrice,
  type OrderDetail,
  type OrderListItem,
} from "./api";

export type OrderDayFilter = "today" | "tomorrow" | "all";

type Props = {
  onSelectOrder: (orderId: string) => void;
};

function formatWhen(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function statusClass(status: string) {
  if (status === "paid") return "status-paid";
  if (status === "open") return "status-open";
  return "status-other";
}

export function OrdersView({ onSelectOrder }: Props) {
  const [filter, setFilter] = useState<OrderDayFilter>("today");
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [timezone, setTimezone] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (day: OrderDayFilter) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchOrders(day);
      setOrders(data.orders);
      setTimezone(data.timezone);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load orders");
      setOrders([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(filter);
  }, [filter, load]);

  return (
    <>
      <div className="card">
        <h2>Orders</h2>
        <p className="muted">
          Recent orders from voice, API, and checkout. Times use restaurant timezone
          {timezone ? ` (${timezone})` : ""}.
        </p>
        <div className="btn-row filter-row">
          {(["today", "tomorrow", "all"] as const).map((f) => (
            <button
              key={f}
              className={filter === f ? "primary" : "secondary"}
              onClick={() => setFilter(f)}
              disabled={loading}
            >
              {f === "today" ? "Today" : f === "tomorrow" ? "Tomorrow" : "Last 30 days"}
            </button>
          ))}
          <button className="secondary" onClick={() => load(filter)} disabled={loading}>
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
        {error && <div className="alert alert-error">{error}</div>}
      </div>

      <div className="card table-card">
        <table className="data-table orders-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Order ID</th>
              <th>Call</th>
              <th>Status</th>
              <th>Items</th>
              <th>Total</th>
              <th>Preview</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {orders.length === 0 && !loading && (
              <tr>
                <td colSpan={8} className="empty-cell">
                  No orders for this filter.
                </td>
              </tr>
            )}
            {orders.map((o) => (
              <tr key={o.order_id} className="order-row" onClick={() => onSelectOrder(o.order_id)}>
                <td>{formatWhen(o.created_at)}</td>
                <td>
                  <code className="mono-sm">{o.order_id.slice(0, 8)}…</code>
                </td>
                <td>
                  <code className="mono-sm">{o.call_id}</code>
                </td>
                <td>
                  <span className={`status-pill ${statusClass(o.status)}`}>{o.status}</span>
                </td>
                <td>{o.item_count}</td>
                <td>{formatPrice(o.total_cents)}</td>
                <td className="preview-cell">{o.summary_preview ?? "—"}</td>
                <td>
                  <button
                    className="secondary small"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectOrder(o.order_id);
                    }}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

type DetailProps = {
  orderId: string;
  onBack: () => void;
  onOpenCallCart: (callId: string) => void;
};

export function OrderDetailView({ orderId, onBack, onOpenCallCart }: DetailProps) {
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchOrderDetail(orderId)
      .then(setOrder)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load order"))
      .finally(() => setLoading(false));
  }, [orderId]);

  if (loading) return <div className="card">Loading order…</div>;
  if (error) return <div className="alert alert-error">{error}</div>;
  if (!order) return null;

  const parity =
    order.spoken_summary && order.sms_summary && order.spoken_summary === order.sms_summary;

  return (
    <>
      <div className="card">
        <div className="btn-row">
          <button className="secondary" onClick={onBack}>
            ← Back to orders
          </button>
          <button className="secondary" onClick={() => onOpenCallCart(order.call_id)}>
            Open voice cart ({order.call_id})
          </button>
        </div>
        <h2>Order {order.order_id.slice(0, 8)}…</h2>
        <div className="detail-grid">
          <div>
            <span className="stat-label">Status</span>
            <span className={`status-pill ${statusClass(order.status)}`}>{order.status}</span>
          </div>
          <div>
            <span className="stat-label">Total</span>
            <span className="stat-value">{formatPrice(order.total_cents ?? 0)}</span>
          </div>
          <div>
            <span className="stat-label">Created</span>
            <span>{formatWhen(order.created_at)}</span>
          </div>
          <div>
            <span className="stat-label">Call ID</span>
            <code>{order.call_id}</code>
          </div>
          <div>
            <span className="stat-label">Phone</span>
            <span>{order.customer_phone ?? "—"}</span>
          </div>
        </div>
        <div className={parity ? "parity-match" : "parity-mismatch"}>
          {parity ? "✓ Spoken summary matches SMS" : "✗ Spoken and SMS differ"}
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <h2>Spoken summary</h2>
          <pre>{order.spoken_summary ?? "—"}</pre>
        </div>
        <div className="card">
          <h2>SMS summary</h2>
          <pre>{order.sms_summary ?? "—"}</pre>
        </div>
      </div>

      <div className="card">
        <h2>Cart</h2>
        <pre>{JSON.stringify(order.cart, null, 2)}</pre>
      </div>

      {order.payments.length > 0 && (
        <div className="card">
          <h2>Payments</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Charge</th>
                <th>Amount</th>
                <th>Card</th>
                <th>Status</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {order.payments.map((p) => (
                <tr key={p.charge_id}>
                  <td>
                    <code>{p.charge_id}</code>
                  </td>
                  <td>{formatPrice(p.amount_cents)}</td>
                  <td>•••• {p.last_four ?? "—"}</td>
                  <td>{p.status}</td>
                  <td>{formatWhen(p.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {order.sms_messages.length > 0 && (
        <div className="card">
          <h2>SMS messages</h2>
          {order.sms_messages.map((m) => (
            <div key={m.sms_id} className="sms-block">
              <p>
                <strong>{m.to_phone}</strong> — {m.status} — {formatWhen(m.created_at)}
              </p>
              <pre>{m.body}</pre>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
