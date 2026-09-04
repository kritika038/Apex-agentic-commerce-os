"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { API_BASE_URL } from '@/lib/api';

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

import { DashboardNav } from '@/components/dashboard/DashboardNav';

export default function PaymentsPage() {
  const [payments, setPayments] = useState<PaymentTx[]>([]);
  const [selectedTx, setSelectedTx] = useState<PaymentTx | null>(null);
  const [filter, setFilter] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [reconcilingId, setReconcilingId] = useState<string | null>(null);
  const [alert, setAlert] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const fetchPayments = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/payments`);
      if (res.ok) {
        const data = await res.json();
        setPayments(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPayments();
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
        fetchPayments();
        if (selectedTx && selectedTx.id === txId) {
          const updated = await fetch(`${API_BASE}/payments/${txId}`);
          if (updated.ok) setSelectedTx(await updated.json());
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

  const filteredPayments = payments.filter((p) => {
    if (filter === "ALL") return true;
    return p.status === filter;
  });

  const getStatusBadge = (st: string) => {
    switch (st) {
      case "CAPTURED":
        return "bg-emerald-950/80 border-emerald-700 text-emerald-300";
      case "ORDER_CREATED":
        return "bg-blue-950/80 border-blue-700 text-blue-300";
      case "PAYMENT_PENDING":
        return "bg-indigo-950/80 border-indigo-700 text-indigo-300";
      case "AUTHORIZED":
        return "bg-cyan-950/80 border-cyan-700 text-cyan-300";
      case "UNKNOWN":
      case "RECONCILING":
        return "bg-amber-950/80 border-amber-700 text-amber-300 animate-pulse";
      case "FAILED":
      case "CANCELLED":
        return "bg-red-950/80 border-red-700 text-red-300";
      default:
        return "bg-slate-800 text-slate-400";
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
                Payment Transactions Console
              </h1>
              <span className="px-2.5 py-0.5 bg-emerald-950 border border-emerald-700/60 text-emerald-300 text-[10px] font-mono font-semibold rounded-full">
                Razorpay Test Mode
              </span>
            </div>
            <p className="text-slate-400 text-xs sm:text-sm mt-1">
              Grounded Payment Execution Layer. Gated strictly behind Policy & Authorization.
            </p>
          </div>
          <div className="flex gap-2.5">
            <Link
              href="/dashboard/payments/recovery"
              className="px-3.5 py-2 bg-amber-950/80 hover:bg-amber-900 border border-amber-700 text-amber-300 rounded-lg text-xs transition font-semibold"
            >
              🛡️ Recovery Center
            </Link>
            <Link
              href="/dashboard/policies"
              className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 rounded-lg text-xs transition"
            >
              Policies
            </Link>
            <Link
              href="/dashboard/approvals"
              className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 rounded-lg text-xs transition"
            >
              Approvals
            </Link>
            <Link
              href="/dashboard/agents"
              className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 rounded-lg text-xs transition"
            >
              Agent Matrix
            </Link>
            <Link
              href="/dashboard"
              className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 rounded-lg text-xs transition"
            >
              ← Overview
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

        {/* Filter Tabs */}
        <div className="flex flex-wrap gap-2 border-b border-slate-800/80 pb-3">
          {["ALL", "CAPTURED", "ORDER_CREATED", "PAYMENT_PENDING", "UNKNOWN", "RECONCILING", "FAILED"].map((st) => (
            <button
              key={st}
              onClick={() => setFilter(st)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition ${
                filter === st
                  ? "bg-emerald-500 text-slate-950"
                  : "bg-slate-900 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              }`}
            >
              {st} ({payments.filter((p) => (st === "ALL" ? true : p.status === st)).length})
            </button>
          ))}
        </div>

        {/* Payments Table */}
        {loading ? (
          <div className="p-12 text-center text-slate-500">Loading payment transactions...</div>
        ) : filteredPayments.length === 0 ? (
          <div className="p-12 text-center text-slate-500 bg-slate-900/40 border border-slate-800/60 rounded-2xl">
            No payment transactions found. Initiate orders via AI Shopping.
          </div>
        ) : (
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-950/60 text-slate-400 text-xs">
                    <th className="p-4 font-semibold">Transaction ID</th>
                    <th className="p-4 font-semibold">Gateway Order ID</th>
                    <th className="p-4 font-semibold">Authoritative Amount</th>
                    <th className="p-4 font-semibold">Status</th>
                    <th className="p-4 font-semibold">Receipt</th>
                    <th className="p-4 font-semibold">Created At</th>
                    <th className="p-4 font-semibold text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {filteredPayments.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-800/30 transition font-mono text-xs">
                      <td className="p-4 font-bold text-slate-200">{p.id.slice(0, 8)}...</td>
                      <td className="p-4 text-slate-300">{p.razorpay_order_id || "—"}</td>
                      <td className="p-4 font-bold text-emerald-400 text-sm">
                        ₹{parseFloat(p.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })} {p.currency}
                      </td>
                      <td className="p-4">
                        <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold border uppercase ${getStatusBadge(p.status)}`}>
                          {p.status}
                        </span>
                      </td>
                      <td className="p-4 text-slate-400">{p.receipt}</td>
                      <td className="p-4 text-slate-400 font-sans text-[11px]">{new Date(p.created_at).toLocaleString()}</td>
                      <td className="p-4 text-right space-x-2 font-sans">
                        <button
                          onClick={() => setSelectedTx(p)}
                          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs transition"
                        >
                          View Trace
                        </button>
                        {(p.status === "UNKNOWN" || p.status === "RECONCILING" || p.status === "ORDER_CREATED") && (
                          <button
                            onClick={() => handleReconcile(p.id)}
                            disabled={reconcilingId === p.id}
                            className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded text-xs transition disabled:opacity-50"
                          >
                            {reconcilingId === p.id ? "Reconciling..." : "Reconcile"}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Transaction Trace Modal / Drawer */}
        {selectedTx && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-6">
              <div className="flex justify-between items-start border-b border-slate-800 pb-4">
                <div>
                  <h3 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                    <span>⚡</span> End-to-End Transaction Trace
                  </h3>
                  <p className="text-xs text-slate-400 font-mono mt-0.5">TX ID: {selectedTx.id}</p>
                </div>
                <button onClick={() => setSelectedTx(null)} className="text-slate-400 hover:text-white p-1">
                  ✕
                </button>
              </div>

              {/* Lifecycle Step Flow */}
              <div className="space-y-3 font-mono text-xs">
                <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-1.5">
                  <div className="flex justify-between text-slate-400">
                    <span>1. Purchase Intent ID:</span>
                    <span className="text-indigo-300">{selectedTx.purchase_intent_id}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>2. Transaction Authorization ID:</span>
                    <span className="text-cyan-300">{selectedTx.authorization_id}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>3. Razorpay Order ID:</span>
                    <span className="text-emerald-300">{selectedTx.razorpay_order_id || "N/A"}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>4. Gateway Payment ID:</span>
                    <span className="text-emerald-300">{selectedTx.razorpay_payment_id || "Awaiting Webhook"}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>5. Authoritative Amount:</span>
                    <span className="text-emerald-400 font-bold">₹{parseFloat(selectedTx.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })} {selectedTx.currency}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>6. Idempotency Key:</span>
                    <span className="text-slate-300">{selectedTx.idempotency_key}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>7. Current Status:</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${getStatusBadge(selectedTx.status)}`}>
                      {selectedTx.status}
                    </span>
                  </div>
                  {selectedTx.captured_at && (
                    <div className="flex justify-between text-slate-400">
                      <span>8. Captured At:</span>
                      <span className="text-emerald-300">{new Date(selectedTx.captured_at).toLocaleString()}</span>
                    </div>
                  )}
                  {selectedTx.failure_code && (
                    <div className="flex justify-between text-red-400">
                      <span>Failure Reason:</span>
                      <span>{selectedTx.failure_code}: {selectedTx.failure_message}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => handleReconcile(selectedTx.id)}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition"
                >
                  Poll / Reconcile Status
                </button>
                <button
                  onClick={() => setSelectedTx(null)}
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
          <span>Agentic Commerce OS — Payment Console</span>
          <span className="text-[11px] text-slate-600">Deterministic Governance Layer Active</span>
        </div>
      </footer>
    </div>
  );
}
