import { useCallback, useEffect, useState } from "react";
import {
  checkHealth,
  fetchCart,
  fetchConfig,
  fetchMenu,
  fetchRestaurants,
  fetchScenarios,
  formatPrice,
  resetCall,
  runDemoOrder,
  runScenario,
  type ConfigResponse,
  type MenuResponse,
  type RestaurantInfo,
  type Scenario,
  type ToolResponse,
  RESTAURANT,
} from "./api";

import { OrderDetailView, OrdersView } from "./OrdersView";

function initialCallId(): string {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get("call") || params.get("call_id");
  if (fromUrl?.trim()) return fromUrl.trim();
  return crypto.randomUUID().slice(0, 8);
}

type Tab = "dashboard" | "orders" | "order-detail" | "menu" | "scenarios" | "operations" | "integrations" | "cart";

const NAV: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "orders", label: "Orders" },
  { id: "menu", label: "Menu" },
  { id: "scenarios", label: "Test Scenarios" },
  { id: "operations", label: "Operations" },
  { id: "integrations", label: "Integrations" },
  { id: "cart", label: "Cart Inspector" },
];

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const initialOrder = params.get("order");
  const [tab, setTab] = useState<Tab>(initialOrder ? "order-detail" : "dashboard");
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(initialOrder);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [callId, setCallId] = useState(initialCallId);
  const [cartSource, setCartSource] = useState<"demo" | "voice" | "scenario" | null>(null);
  const [restaurants, setRestaurants] = useState<RestaurantInfo[]>([]);
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [menu, setMenu] = useState<MenuResponse | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [lastResult, setLastResult] = useState<ToolResponse | null>(null);
  const [scenarioResults, setScenarioResults] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const ok = await checkHealth();
    setApiOk(ok);
    if (!ok) return;
    try {
      const [r, c, m, s] = await Promise.all([
        fetchRestaurants(),
        fetchConfig(),
        fetchMenu(),
        fetchScenarios(),
      ]);
      setRestaurants(r.restaurants);
      setConfig(c);
      setMenu(m);
      setScenarios(s.scenarios);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load config");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openOrderDetail = (orderId: string) => {
    setSelectedOrderId(orderId);
    setTab("order-detail");
    const url = new URL(window.location.href);
    url.searchParams.set("order", orderId);
    window.history.replaceState({}, "", url.toString());
  };

  const openCallCartFromOrder = (voiceCallId: string) => {
    setCallId(voiceCallId);
    setCartSource("voice");
    void loadLiveCart(voiceCallId);
  };

  const loadLiveCart = useCallback(async (id?: string) => {
    const sessionId = (id ?? callId).trim();
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchCart(sessionId);
      setLastResult(result);
      setCartSource(sessionId.startsWith("web-") ? "voice" : "demo");
      setTab("cart");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load cart");
    } finally {
      setLoading(false);
    }
  }, [callId]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get("call") || params.get("call_id");
    if (!fromUrl?.trim() || !apiOk) return;
    const sessionId = fromUrl.trim();
    setCallId(sessionId);
    setLoading(true);
    fetchCart(sessionId)
      .then((result) => {
        setLastResult(result);
        setCartSource(sessionId.startsWith("web-") ? "voice" : "demo");
        setTab("cart");
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Failed to load cart");
      })
      .finally(() => setLoading(false));
  }, [apiOk]);

  const runDemo = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await runDemoOrder(callId);
      setLastResult(result);
      setCartSource("demo");
      setTab("cart");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Demo failed");
    } finally {
      setLoading(false);
    }
  };

  const runTest = async (scenarioId: string) => {
    setLoading(true);
    setError(null);
    try {
      await resetCall(callId);
      const result = await runScenario(callId, scenarioId);
      setLastResult(result);
      setCartSource("scenario");
      const pass = ["success", "clarification", "violation", "advance_notice"].includes(result.status);
      setScenarioResults((prev) => ({
        ...prev,
        [scenarioId]: pass ? `✓ ${result.status}` : `✗ ${result.status}`,
      }));
    } catch (e) {
      setScenarioResults((prev) => ({ ...prev, [scenarioId]: "✗ error" }));
      setError(e instanceof Error ? e.message : "Scenario failed");
    } finally {
      setLoading(false);
    }
  };

  const parityMatch =
    lastResult?.spoken_summary &&
    lastResult?.sms_summary &&
    lastResult.spoken_summary === lastResult.sms_summary;

  const restaurant = restaurants.find((r) => r.id === RESTAURANT);

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Restaurants AI Agent</h1>
        <p className="subtitle">
          {restaurant?.name ?? "Hot Bagels 2nd Street"}
          {config?.is_mock && <span className="mock-badge">MOCK DATA</span>}
        </p>
        <nav className="nav">
          {NAV.map((n) => (
            <button
              key={n.id}
              className={tab === n.id || (n.id === "orders" && tab === "order-detail") ? "active" : ""}
              onClick={() => {
                if (n.id === "orders") {
                  setTab("orders");
                  setSelectedOrderId(null);
                  const url = new URL(window.location.href);
                  url.searchParams.delete("order");
                  window.history.replaceState({}, "", url.toString());
                } else {
                  setTab(n.id);
                }
              }}
            >
              {n.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <small>Call session (voice + API)</small>
          <input
            className="call-id-input"
            value={callId}
            onChange={(e) => setCallId(e.target.value)}
            placeholder="web-… or demo id"
          />
          <button
            className="secondary small full-width"
            disabled={loading || !apiOk || !callId.trim()}
            onClick={() => loadLiveCart()}
          >
            Load live cart
          </button>
        </div>
      </aside>

      <main className="main">
        {error && <div className="alert alert-error">{error}</div>}

        {tab === "dashboard" && (
          <>
            <div className="stats-grid">
              <div className="stat-card">
                <span className="stat-label">Order API</span>
                <span className={apiOk ? "status-ok" : "status-fail"}>
                  {apiOk === null ? "…" : apiOk ? "Online" : "Offline"}
                </span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Menu items</span>
                <span className="stat-value">{config?.menu_summary.item_count ?? "—"}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Modifiers</span>
                <span className="stat-value">{config?.menu_summary.modifier_count ?? "—"}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Bundles</span>
                <span className="stat-value">{config?.menu_summary.bundle_count ?? "—"}</span>
              </div>
            </div>
            <div className="card">
              <h2>Quick actions</h2>
              <p>
                After a <strong>voice call</strong> on port 8090, copy the Call ID (e.g.{" "}
                <code>web-ef5d62ae</code>) into the sidebar and click <strong>Load live cart</strong>.
                Or use the link on the voice page.
              </p>
              <p className="muted">
                <strong>Run Demo Order</strong> uses this dashboard&apos;s own session — not the voice
                session.
              </p>
              <div className="btn-row">
                <button className="primary" onClick={runDemo} disabled={loading || !apiOk}>
                  {loading ? "Running…" : "Run Demo Order"}
                </button>
                <button
                  className="secondary"
                  onClick={() => loadLiveCart()}
                  disabled={loading || !apiOk || !callId.trim()}
                >
                  Load live cart
                </button>
                <button className="secondary" onClick={load} disabled={!apiOk}>
                  Refresh data
                </button>
              </div>
            </div>
            <div className="card">
              <h2>Automated tests</h2>
              <p>
                All 13 engine scenarios pass locally:{" "}
                <code>python run_tests.py</code>
              </p>
            </div>
          </>
        )}

        {tab === "orders" && <OrdersView onSelectOrder={openOrderDetail} />}

        {tab === "order-detail" && selectedOrderId && (
          <OrderDetailView
            orderId={selectedOrderId}
            onBack={() => setTab("orders")}
            onOpenCallCart={openCallCartFromOrder}
          />
        )}

        {tab === "menu" && menu && (
          <>
            {Object.entries(menu.categories).map(([category, items]) => (
              <div className="card" key={category}>
                <h2>{category}</h2>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>ID</th>
                      <th>Price</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <tr key={item.id}>
                        <td>{item.name}</td>
                        <td><code>{item.id}</code></td>
                        <td>{formatPrice(item.base_price_cents)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
            {menu.bundles.length > 0 && (
              <div className="card">
                <h2>Bundles</h2>
                <table className="data-table">
                  <thead>
                    <tr><th>Bundle</th><th>ID</th><th>Price</th></tr>
                  </thead>
                  <tbody>
                    {menu.bundles.map((b) => (
                      <tr key={b.id}>
                        <td>{b.name}</td>
                        <td><code>{b.id}</code></td>
                        <td>{formatPrice(b.base_price_cents)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {tab === "scenarios" && (
          <div className="card">
            <h2>HOT BAGELS Critical Tests</h2>
            <p>Run individual scenarios against the live order engine (resets cart each run).</p>
            <ul className="scenario-list">
              {scenarios.map((s) => (
                <li key={s.id}>
                  <div className="scenario-info">
                    <strong>{s.id}</strong>
                    <span>{s.name}</span>
                    {s.utterance && <small>{s.utterance}</small>}
                    {scenarioResults[s.id] && (
                      <span className="scenario-result">{scenarioResults[s.id]}</span>
                    )}
                  </div>
                  <button
                    className="secondary small"
                    disabled={loading || !apiOk}
                    onClick={() => runTest(s.id)}
                  >
                    Run
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {tab === "operations" && config && (
          <>
            <div className="card">
              <h2>Store hours</h2>
              <pre>{JSON.stringify(
                (config.operations as { store_hours?: unknown }).store_hours,
                null,
                2,
              )}</pre>
            </div>
            <div className="card">
              <h2>Delivery & ordering</h2>
              <pre>{JSON.stringify(
                {
                  ordering_modes: (config.operations as { ordering_modes?: unknown }).ordering_modes,
                  delivery_zones: (config.operations as { delivery_zones?: unknown }).delivery_zones,
                },
                null,
                2,
              )}</pre>
            </div>
            <div className="card">
              <h2>Agent messages</h2>
              <pre>{JSON.stringify(
                (config.operations as { agent_prompts_and_messages?: unknown }).agent_prompts_and_messages,
                null,
                2,
              )}</pre>
            </div>
            <div className="card">
              <h2>Escalation</h2>
              <pre>{JSON.stringify(
                (config.operations as { contact_channels?: unknown }).contact_channels,
                null,
                2,
              )}</pre>
            </div>
          </>
        )}

        {tab === "integrations" && config && (
          <>
            <div className="card">
              <h2>Telephony</h2>
              <pre>{JSON.stringify(
                (config.integrations as { telephony?: unknown }).telephony,
                null,
                2,
              )}</pre>
            </div>
            <div className="card">
              <h2>SMS gateway</h2>
              <pre>{JSON.stringify(
                (config.integrations as { sms_gateway?: unknown }).sms_gateway,
                null,
                2,
              )}</pre>
            </div>
            <div className="card">
              <h2>Payment processing</h2>
              <pre>{JSON.stringify(
                (config.integrations as { payment_processing?: unknown }).payment_processing,
                null,
                2,
              )}</pre>
            </div>
            <div className="card">
              <h2>Pronunciation lexicon</h2>
              <pre>{JSON.stringify(config.pronunciations, null, 2)}</pre>
            </div>
          </>
        )}

        {tab === "cart" && (
          <>
            <div className="card">
              <h2>Cart Inspector</h2>
              <p className="muted">
                Session <code>{callId}</code>
                {cartSource === "voice" && " — live voice order"}
                {cartSource === "demo" && " — dashboard demo"}
                {cartSource === "scenario" && " — test scenario"}
              </p>
              <div className="btn-row">
                <button
                  className="secondary small"
                  onClick={() => loadLiveCart()}
                  disabled={loading || !apiOk}
                >
                  {loading ? "Loading…" : "Refresh cart from API"}
                </button>
              </div>
              {lastResult && lastResult.cart && (lastResult.cart as { lines?: unknown[] }).lines?.length === 0 && (
                <div className="alert alert-error">
                  Cart is empty. If you used voice, open{" "}
                  <code>http://localhost:5173/?call=web-…</code> with the voice Call ID — not
                  this dashboard session (<code>{callId}</code>).
                </div>
              )}
              {lastResult ? (
                <>
                  <p>
                    Status: <strong>{lastResult.status}</strong> — {lastResult.message}
                  </p>
                  {lastResult.options && lastResult.options.length > 0 && (
                    <p>Options: {lastResult.options.join(", ")}</p>
                  )}
                  <div className={parityMatch ? "parity-match" : "parity-mismatch"}>
                    {parityMatch
                      ? "✓ Spoken summary matches SMS (Test 13)"
                      : "✗ Spoken and SMS differ"}
                  </div>
                </>
              ) : (
                <p>
                  Paste the voice <strong>Call ID</strong> from port 8090 into the sidebar, then click{" "}
                  <strong>Load live cart</strong>. Questions-only turns (e.g. &quot;do you have pizza?&quot;)
                  may leave the cart empty until you order items.
                </p>
              )}
            </div>
            {lastResult && (
              <div className="grid-2">
                <div className="card">
                  <h2>Spoken summary</h2>
                  <pre>{lastResult.spoken_summary ?? "—"}</pre>
                </div>
                <div className="card">
                  <h2>SMS summary</h2>
                  <pre>{lastResult.sms_summary ?? "—"}</pre>
                </div>
              </div>
            )}
            {lastResult?.cart && (
              <div className="card">
                <h2>Structured cart JSON</h2>
                <pre>{JSON.stringify(lastResult.cart, null, 2)}</pre>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
