"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { API_BASE_URL } from '@/lib/api';
import { DashboardNav } from '@/components/dashboard/DashboardNav';

const API_BASE = API_BASE_URL;

interface PaymentTx {
  id: string;
  merchant_id: string;
  purchase_intent_id: string;
  authorization_id: string;
  razorpay_order_id?: string;
  razorpay_payment_id?: string;
  amount: string;
  currency: string;
  status: string;
  idempotency_key: string;
  receipt: string;
  attempt_count: number;
  failure_code?: string;
  failure_message?: string;
  created_at: string;
  updated_at: string;
  authorized_at?: string;
  captured_at?: string;
  failed_at?: string;
}

interface TimelineEvent {
  timestamp: string;
  event_type: string;
  title: string;
  description: string;
  badge_variant: "success" | "warning" | "error" | "info";
  metadata?: Record<string, unknown>;
}

export default function RecoveryCenterPage() {
  const [failures, setFailures] = useState<PaymentTx[]>([]);
  const [allPayments, setAllPayments] = useState<PaymentTx[]>([]);
  const [loading, setLoading] = useState(true);
  const [reconcilingId, setReconcilingId] = useState<string | null>(null);
  const [selectedTxTimeline, setSelectedTxTimeline] = useState<{ tx: PaymentTx; events: TimelineEvent[] } | null>(null);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [alert, setAlert] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Simulator state
  const [simScenario, setSimScenario] = useState("TIMEOUT");
  const [simTxId, setSimTxId] = useState("");
  const [simLoading, setSimLoading] = useState(false);
  const [simResult, setSimResult] = useState<Record<string, unknown> | null>(null);

  const fetchTransactions = async () => {
    try {
      setLoading(true);
      const resF = await fetch(`${API_BASE}/payments/recovery/failures`);
      if (resF.ok) setFailures(await resF.json());

      const resAll = await fetch(`${API_BASE}/payments`);
      if (resAll.ok) {
        const all = await resAll.json();
        setAllPayments(all);
        if (all.length > 0 && !simTxId) {
          setSimTxId(all[0].id);
        }
      }
    } catch (err) {
      console.error("Error fetching recovery transactions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleReconcile = async (txId: string) => {
    setReconcilingId(txId);
    setAlert(null);
    try {
      const res = await fetch(`${API_BASE}/payments/${txId}/reconcile`, {
        method: "POST"
      });
      if (res.ok) {
        const data = await res.json();
        setAlert({
          type: "success",
          message: `✓ ${data.message}`
        });
        fetchTransactions();
        if (selectedTxTimeline && selectedTxTimeline.tx.id === txId) {
          viewTimeline(txId);
        }
      } else {
        const err = await res.json();
        setAlert({ type: "error", message: err.detail || "Reconciliation failed." });
      }
    } catch (err: unknown) {
      const e = err as { message?: string };
      setAlert({ type: "error", message: e?.message || "Network error during reconciliation." });
    } finally {
      setReconcilingId(null);
    }
  };

  const viewTimeline = async (txId: string) => {
    setTimelineLoading(true);
    try {
      const [resTx, resTl] = await Promise.all([
        fetch(`${API_BASE}/payments/${txId}`),
        fetch(`${API_BASE}/payments/${txId}/timeline`)
      ]);
      if (resTx.ok && resTl.ok) {
        const tx = await resTx.json();
        const events = await resTl.json();
        setSelectedTxTimeline({ tx, events });
      }
    } catch (err) {
      console.error("Error loading timeline:", err);
    } finally {
      setTimelineLoading(false);
    }
  };

  const handleTriggerSimulation = async () => {
    setSimLoading(true);
    setSimResult(null);
    setAlert(null);
    try {
      const selected = allPayments.find((p) => p.id === simTxId) || failures[0];
      const payload: Record<string, unknown> = {
        scenario: simScenario,
        transaction_id: selected?.id,
        purchase_intent_id: selected?.purchase_intent_id,
        authorization_id: selected?.authorization_id
      };

      const res = await fetch(`${API_BASE}/payments/simulator/scenario`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: jsonToString(payload)
      });

      if (res.ok) {
        const data = await res.json();
        setSimResult(data);
        setAlert({ type: "success", message: `✓ Scenario ${simScenario} injected successfully.` });
        fetchTransactions();
      } else {
        const err = await res.json();
        setAlert({ type: "error", message: err.detail || "Simulation failed." });
      }
    } catch (err: unknown) {
      const e = err as { message?: string };
      setAlert({ type: "error", message: e?.message || "Network error during simulation." });
    } finally {
      setSimLoading(false);
    }
  };

  const jsonToString = (obj: unknown) => JSON.stringify(obj);

  const getBadgeStyle = (variant: string) => {
    switch (variant) {
      case "success":
        return "bg-emerald-950/80 border-emerald-700 text-emerald-300";
      case "warning":
        return "bg-amber-950/80 border-amber-700 text-amber-300";
      case "error":
        return "bg-red-950/80 border-red-700 text-red-300";
      default:
        return "bg-blue-950/80 border-blue-700 text-blue-300";
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col justify-between">
      <DashboardNav />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        {/* Navigation Bar */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-6 border-b border-slate-800">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-bold text-white">
                Payment Recovery & Reconciliation Center
              </h1>
              <span className="px-2.5 py-0.5 bg-amber-950 border border-amber-700/60 text-amber-300 text-[10px] font-mono font-semibold rounded-full animate-pulse">
                Reconciliation Active
              </span>
            </div>
            <p className="text-slate-400 text-xs sm:text-sm mt-1">
              Deterministic recovery subsystem. <code className="text-amber-300">UNKNOWN ≠ FAILED</code>. Blind retries are strictly blocked until authoritative provider reconciliation.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              href="/dashboard/payments"
              className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition"
            >
              ← Payments Ledger
            </Link>
          </div>
        </div>

        {alert && (
          <div
            className={`p-4 rounded-xl text-sm border ${
              alert.type === "success"
                ? "bg-emerald-950/60 border-emerald-800 text-emerald-300"
                : "bg-red-950/60 border-red-800 text-red-300"
            }`}
          >
            {alert.message}
          </div>
        )}

        {/* Top Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
            <span className="text-xs text-slate-400 font-semibold uppercase">Active UNKNOWN</span>
            <div className="text-2xl font-bold text-amber-400 font-mono">
              {failures.filter((f) => f.status === "UNKNOWN").length}
            </div>
            <p className="text-[11px] text-slate-500">Provider state is indeterminate; order retries blocked</p>
          </div>
          <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
            <span className="text-xs text-slate-400 font-semibold uppercase">Reconciling Now</span>
            <div className="text-2xl font-bold text-cyan-400 font-mono">
              {failures.filter((f) => f.status === "RECONCILING").length}
            </div>
            <p className="text-[11px] text-slate-500">Row-locked polling gateway state</p>
          </div>
          <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
            <span className="text-xs text-slate-400 font-semibold uppercase">Settled (CAPTURED)</span>
            <div className="text-2xl font-bold text-emerald-400 font-mono">
              {allPayments.filter((p) => p.status === "CAPTURED").length}
            </div>
            <p className="text-[11px] text-slate-500">Immune to out-of-order webhook downgrades</p>
          </div>
          <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-1">
            <span className="text-xs text-slate-400 font-semibold uppercase">Definite FAILED</span>
            <div className="text-2xl font-bold text-rose-400 font-mono">
              {failures.filter((f) => f.status === "FAILED").length}
            </div>
            <p className="text-[11px] text-slate-500">Known client 4xx or provider rejection</p>
          </div>
        </div>

        {/* Section 1: Active Failures & UNKNOWN Ledger */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-xl">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-lg font-bold text-slate-200">Active Failures & Ambiguous Transactions</h2>
              <p className="text-xs text-slate-400">Transactions requiring reconciliation or failure inspection</p>
            </div>
            <button
              onClick={fetchTransactions}
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-semibold transition"
            >
              ↻ Refresh
            </button>
          </div>

          {loading ? (
            <div className="p-8 text-center text-slate-500">Scanning for unconfirmed transactions...</div>
          ) : failures.length === 0 ? (
            <div className="p-8 text-center text-emerald-400 bg-emerald-950/20 border border-emerald-800/40 rounded-xl font-mono text-xs">
              ✓ All payment transactions are cleanly settled or reconciled. No active UNKNOWN states detected.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm font-mono text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-[11px]">
                    <th className="p-3">Transaction ID</th>
                    <th className="p-3">Amount</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Failure Reason</th>
                    <th className="p-3">Attempts</th>
                    <th className="p-3">Created</th>
                    <th className="p-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {failures.map((f) => (
                    <tr key={f.id} className="hover:bg-slate-800/40 transition">
                      <td className="p-3 font-bold text-slate-200">{f.id.slice(0, 8)}...</td>
                      <td className="p-3 font-bold text-emerald-400">
                        ₹{parseFloat(f.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })} {f.currency}
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border uppercase ${
                          f.status === "UNKNOWN" ? "bg-amber-950 border-amber-700 text-amber-300 animate-pulse" : "bg-red-950 border-red-700 text-red-300"
                        }`}>
                          {f.status}
                        </span>
                      </td>
                      <td className="p-3 text-slate-300 truncate max-w-xs font-sans text-xs">
                        {f.failure_code || "UNKNOWN"}: {f.failure_message || "Awaiting authoritative lookup"}
                      </td>
                      <td className="p-3 text-slate-400">{f.attempt_count}</td>
                      <td className="p-3 text-slate-400 font-sans text-[11px]">{new Date(f.created_at).toLocaleTimeString()}</td>
                      <td className="p-3 text-right space-x-2 font-sans">
                        <button
                          onClick={() => viewTimeline(f.id)}
                          className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs transition"
                        >
                          Timeline
                        </button>
                        <button
                          onClick={() => handleReconcile(f.id)}
                          disabled={reconcilingId === f.id}
                          className="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded text-xs font-semibold transition disabled:opacity-50"
                        >
                          {reconcilingId === f.id ? "Reconciling..." : "Reconcile"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Section 2: Demo Failure Simulator Panel */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-xl">
          <div className="flex justify-between items-center">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl">🧪</span>
                <h2 className="text-lg font-bold text-slate-200">Demo Failure Simulator</h2>
                <span className="px-2.5 py-0.5 bg-rose-950/80 border border-rose-800 text-rose-300 text-[10px] font-mono rounded">
                  Mock Provider Only
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Injects deterministic network timeouts, 4xx/5xx responses, and out-of-order webhooks into the live backend pipeline.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
            <div className="space-y-1.5">
              <label className="text-xs text-slate-400 font-semibold">Scenario</label>
              <select
                value={simScenario}
                onChange={(e) => setSimScenario(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200 font-mono"
              >
                <option value="TIMEOUT">TIMEOUT (Gateway network timeout → UNKNOWN)</option>
                <option value="PROVIDER_4XX">PROVIDER_4XX (Bad Request → Immediate FAILED)</option>
                <option value="OUT_OF_ORDER_WEBHOOK">OUT_OF_ORDER_WEBHOOK (payment.failed on settled order)</option>
                <option value="INVALID_WEBHOOK_SIGNATURE">INVALID_WEBHOOK_SIGNATURE (HMAC forgery test)</option>
                <option value="SUCCESS">SUCCESS (Standard order creation)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-slate-400 font-semibold">Target Transaction</label>
              <select
                value={simTxId}
                onChange={(e) => setSimTxId(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200 font-mono"
              >
                {allPayments.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id.slice(0, 8)}... — ₹{p.amount} ({p.status})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-end">
              <button
                onClick={handleTriggerSimulation}
                disabled={simLoading}
                className="w-full py-2.5 bg-gradient-to-r from-amber-600 to-rose-600 hover:from-amber-500 hover:to-rose-500 text-white rounded-lg text-xs font-bold transition shadow-lg disabled:opacity-50"
              >
                {simLoading ? "Injecting Scenario..." : `⚡ Inject ${simScenario}`}
              </button>
            </div>
          </div>

          {simResult && (
            <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 space-y-2 font-mono text-xs">
              <span className="text-slate-400 font-bold">Simulator Pipeline Result:</span>
              <pre className="text-amber-300 overflow-x-auto">{jsonToString(simResult)}</pre>
            </div>
          )}
        </div>

        {/* Database-Backed Timeline Drawer */}
        {selectedTxTimeline && (
          <div className="fixed inset-0 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-6 max-h-[85vh] flex flex-col">
              <div className="flex justify-between items-start border-b border-slate-800 pb-4">
                <div>
                  <h3 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                    <span>📜</span> Database-Backed Audit Timeline
                  </h3>
                  <p className="text-xs text-slate-400 font-mono mt-0.5">
                    TX ID: {selectedTxTimeline.tx.id} — Status: <span className="font-bold text-amber-400">{selectedTxTimeline.tx.status}</span>
                  </p>
                </div>
                <button onClick={() => setSelectedTxTimeline(null)} className="text-slate-400 hover:text-white p-1">
                  ✕
                </button>
              </div>

              <div className="overflow-y-auto pr-2 space-y-4 flex-1">
                {timelineLoading ? (
                  <div className="p-8 text-center text-slate-500">Querying database audit records...</div>
                ) : selectedTxTimeline.events.length === 0 ? (
                  <div className="p-8 text-center text-slate-500">No timeline events recorded yet.</div>
                ) : (
                  <div className="relative border-l-2 border-slate-800 ml-4 pl-6 space-y-6">
                    {selectedTxTimeline.events.map((ev, i) => (
                      <div key={i} className="relative group">
                        <div className={`absolute -left-[31px] top-1 w-4 h-4 rounded-full border-2 bg-slate-950 ${
                          ev.badge_variant === "success"
                            ? "border-emerald-500"
                            : ev.badge_variant === "error"
                            ? "border-red-500"
                            : "border-amber-500"
                        }`} />
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-slate-200">{ev.title}</span>
                            <span className={`px-2 py-0.5 rounded text-[9px] font-mono border uppercase ${getBadgeStyle(ev.badge_variant)}`}>
                              {ev.event_type}
                            </span>
                          </div>
                          <p className="text-xs text-slate-300 font-sans">{ev.description}</p>
                          <div className="text-[10px] text-slate-500 font-mono">
                            {new Date(ev.timestamp).toLocaleString()}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  onClick={() => handleReconcile(selectedTxTimeline.tx.id)}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold transition"
                >
                  Trigger Reconciliation
                </button>
                <button
                  onClick={() => setSelectedTxTimeline(null)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs transition"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
      <footer className="border-t border-slate-900 bg-slate-950 text-slate-500 text-xs py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <span>Agentic Commerce OS — Payment Recovery & Reconciliation Center</span>
          <span className="text-[11px] text-slate-600">Deterministic Safety Active</span>
        </div>
      </footer>
    </div>
  );
}
