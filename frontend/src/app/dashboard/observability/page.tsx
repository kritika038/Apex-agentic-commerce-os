"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { API_BASE_URL } from '@/lib/api';
import { DashboardNav } from '@/components/dashboard/DashboardNav';

interface AuditEventItem {
  id: string;
  sequence_number: number;
  timestamp: string;
  actor_type: string;
  actor_id?: string;
  action: string;
  event_type: string;
  tool_name?: string;
  resource_type?: string;
  resource_id?: string;
  purchase_intent_id?: string;
  payment_transaction_id?: string;
  previous_state?: string;
  new_state?: string;
  policy_result?: string;
  risk_level?: string;
  decision?: string;
  status: string;
  error_code?: string;
  reason?: string;
  metadata?: Record<string, unknown>;
  previous_event_hash: string;
  event_hash: string;
}

interface TraceSummary {
  trace_id: string;
  merchant_id: string;
  event_count: number;
  first_timestamp: string;
  last_timestamp: string;
  duration_ms: number;
  current_status: string;
  final_outcome: string;
  integrity: {
    is_valid: boolean;
    tampering_detected: boolean;
    detail: string;
  };
  agent_count: number;
  tool_call_count: number;
  policy_decision?: string;
  risk_level?: string;
  approval_status?: string;
  payment_status?: string;
  events: AuditEventItem[];
}

export default function ObservabilityDashboard() {
  const [searchInput, setSearchInput] = useState("");
  const [traceData, setTraceData] = useState<TraceSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<AuditEventItem | null>(null);
  const [recentTraces, setRecentTraces] = useState<string[]>([]);

  const fetchTrace = async (traceId: string) => {
    if (!traceId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/audit/traces/${encodeURIComponent(traceId.trim())}`);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `Trace '${traceId}' not found.`);
      }
      const data: TraceSummary = await res.json();
      setTraceData(data);
      setSearchInput(traceId);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load trace";
      setError(msg);
      setTraceData(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchRecentTraces = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/audit/events?page_size=20`);
      if (res.ok) {
        const data = await res.json();
        const itemsList = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : [];
        const uniqueTraces = Array.from(new Set(itemsList.map((i: { trace_id?: string }) => i.trace_id).filter(Boolean))) as string[];
        setRecentTraces(uniqueTraces.slice(0, 5));
        if (uniqueTraces.length > 0 && !searchInput) {
          fetchTrace(uniqueTraces[0]);
        }
      }
    } catch {
      // Backend may be offline during build
    }
  };

  // Fetch recent audit events on load to show quick-select traces
  useEffect(() => {
    fetchRecentTraces();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchTrace(searchInput);
  };

  const getActorBadgeColor = (actor: string) => {
    switch (actor.toUpperCase()) {
      case "USER":
        return "bg-blue-900/60 text-blue-300 border-blue-700";
      case "AGENT":
        return "bg-purple-900/60 text-purple-300 border-purple-700";
      case "SYSTEM":
        return "bg-amber-900/60 text-amber-300 border-amber-700";
      case "PROVIDER":
        return "bg-indigo-900/60 text-indigo-300 border-indigo-700";
      case "WEBHOOK":
        return "bg-emerald-900/60 text-emerald-300 border-emerald-700";
      default:
        return "bg-gray-800 text-gray-300 border-gray-700";
    }
  };

  const getStatusBadgeColor = (status: string) => {
    switch (status.toUpperCase()) {
      case "SUCCESS":
      case "CAPTURED":
      case "APPROVED":
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/40";
      case "FAILED":
      case "DENIED":
      case "REJECTED":
        return "bg-red-500/20 text-red-400 border-red-500/40";
      case "TIMEOUT":
      case "UNKNOWN":
        return "bg-amber-500/20 text-amber-400 border-amber-500/40";
      default:
        return "bg-cyan-500/20 text-cyan-400 border-cyan-500/40";
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col justify-between">
      <DashboardNav />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-bold text-white">
                Trace Explorer & Audit Ledger
              </h1>
            </div>
            <p className="text-slate-400 text-xs sm:text-sm mt-1">
              Cryptographically verified end-to-end lifecycle observability with SHA-256 tamper-evident hash chaining.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard/observability/agents"
              className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 transition"
            >
              🤖 Agent Analytics
            </Link>
          </div>
        </div>

        {/* Search Bar & Quick Traces */}
        <div className="mt-6 bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl">
          <form onSubmit={handleSearch} className="flex gap-3">
            <input
              type="text"
              placeholder="Search by Trace ID (e.g. trc_unified_e2e_99)..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="flex-1 px-4 py-2.5 rounded-lg bg-slate-950 border border-slate-700 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition disabled:opacity-50 shadow-md shadow-indigo-600/20"
            >
              {loading ? "Verifying..." : "Explore Trace"}
            </button>
          </form>

          {recentTraces.length > 0 && (
            <div className="flex items-center gap-2 mt-3 text-xs text-slate-400">
              <span className="font-semibold text-slate-500">Recent Traces:</span>
              <div className="flex flex-wrap gap-2">
                {recentTraces.map((trc) => (
                  <button
                    key={trc}
                    onClick={() => fetchTrace(trc)}
                    className="px-2.5 py-1 rounded bg-slate-800/80 hover:bg-slate-700 text-indigo-300 font-mono transition border border-slate-700"
                  >
                    {trc}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="p-4 rounded-xl bg-red-950/60 border border-red-800/80 text-red-300 text-sm flex items-center gap-3">
            <span className="text-xl">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {traceData && (
          <div className="space-y-6">
            {/* Cryptographic Integrity & Executive Summary Card */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-2xl">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="text-lg font-bold text-slate-100">Trace Summary</h2>
                    <span className="font-mono text-xs px-3 py-1 rounded-full bg-slate-800 text-indigo-300 border border-slate-700">
                      {traceData.trace_id}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    First Event: {new Date(traceData.first_timestamp).toLocaleString()} • Duration: {traceData.duration_ms}ms
                  </p>
                </div>

                {/* Cryptographic Hash-Chain Badge */}
                <div className="flex items-center gap-2">
                  {traceData.integrity.is_valid ? (
                    <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-950/60 border border-emerald-500/50 text-emerald-300 text-xs font-semibold">
                      <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                      <span>✓ SHA-256 Hash Chain Intact ({traceData.event_count} Events)</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-950/80 border border-red-500 text-red-300 text-xs font-semibold">
                      <span className="h-2 w-2 rounded-full bg-red-500"></span>
                      <span>⚠️ Hash Chain Tampered / Broken!</span>
                    </div>
                  )}
                </div>
              </div>

              {/* KPI Metrics Strip */}
              <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mt-4">
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                  <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">Final Outcome</span>
                  <p className="text-sm font-bold text-slate-200 mt-1">{traceData.final_outcome}</p>
                </div>
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                  <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">Policy Decision</span>
                  <p className="text-sm font-bold text-indigo-300 mt-1">{traceData.policy_decision || "N/A"}</p>
                </div>
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                  <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">Risk Level</span>
                  <p className="text-sm font-bold text-amber-300 mt-1">{traceData.risk_level || "N/A"}</p>
                </div>
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                  <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">Payment State</span>
                  <p className="text-sm font-bold text-emerald-400 mt-1">{traceData.payment_status || "N/A"}</p>
                </div>
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                  <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">Agent Runs</span>
                  <p className="text-sm font-bold text-purple-300 mt-1">{traceData.agent_count}</p>
                </div>
                <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                  <span className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">Tool Calls</span>
                  <p className="text-sm font-bold text-cyan-300 mt-1">{traceData.tool_call_count}</p>
                </div>
              </div>
            </div>

            {/* Vertical Interactive Lifecycle Timeline */}
            <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-2xl">
              <h3 className="text-base font-bold text-slate-100 mb-6 flex items-center gap-2">
                <span>⏱️</span> Chronological Event Stream & Hash Signatures
              </h3>

              <div className="relative border-l-2 border-slate-800 ml-4 space-y-6">
                {traceData.events.map((event) => (
                  <div key={event.id} className="relative pl-8 group">
                    {/* Node Dot */}
                    <div className="absolute -left-[9px] top-1.5 h-4 w-4 rounded-full border-2 border-slate-950 bg-indigo-500 group-hover:scale-125 transition"></div>

                    <div
                      onClick={() => setSelectedEvent(event)}
                      className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 hover:border-indigo-500/50 transition cursor-pointer shadow-md"
                    >
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-mono font-bold text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                            #{event.sequence_number.toString().padStart(2, "0")}
                          </span>
                          <span className={`text-[11px] font-bold px-2 py-0.5 rounded border ${getActorBadgeColor(event.actor_type)}`}>
                            {event.actor_type}
                          </span>
                          <h4 className="text-sm font-semibold text-slate-100">{event.action}</h4>
                          <span className={`text-[11px] font-bold px-2 py-0.5 rounded border ${getStatusBadgeColor(event.status)}`}>
                            {event.status}
                          </span>
                        </div>

                        <span className="text-xs text-slate-400 font-mono">
                          {new Date(event.timestamp).toLocaleTimeString()}
                        </span>
                      </div>

                      {event.reason && (
                        <p className="text-xs text-slate-300 mt-2 bg-slate-900/60 p-2 rounded border border-slate-800/60">
                          {event.reason}
                        </p>
                      )}

                      {/* Hash Chaining Preview */}
                      <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-900 text-[11px] font-mono text-slate-400">
                        <span>Prev: <span className="text-slate-400">{event.previous_event_hash.slice(0, 10)}...</span></span>
                        <span>Hash: <span className="text-indigo-400">{event.event_hash.slice(0, 10)}...</span></span>
                        <span className="text-indigo-400 text-xs font-sans group-hover:underline">Inspect Details →</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

      {/* Event Detail Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-3xl w-full max-h-[85vh] overflow-y-auto p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono font-bold px-2 py-0.5 rounded bg-slate-800 text-indigo-300">
                    Step #{selectedEvent.sequence_number}
                  </span>
                  <h3 className="text-lg font-bold text-slate-100">{selectedEvent.action}</h3>
                </div>
                <p className="text-xs text-slate-400 mt-1">{new Date(selectedEvent.timestamp).toUTCString()}</p>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="px-3 py-1 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition"
              >
                ✕ Close
              </button>
            </div>

            <div className="mt-4 space-y-4 text-xs">
              {/* Correlation IDs */}
              <div className="grid grid-cols-2 gap-3 p-3 bg-slate-950 rounded-lg border border-slate-800 font-mono">
                <div><span className="text-slate-400 font-sans">Trace ID:</span> <span className="text-indigo-300">{selectedEvent.id}</span></div>
                <div><span className="text-slate-400 font-sans">Actor:</span> <span className="text-slate-200">{selectedEvent.actor_type}</span></div>
                {selectedEvent.purchase_intent_id && <div><span className="text-slate-400 font-sans">Intent ID:</span> <span className="text-slate-200">{selectedEvent.purchase_intent_id}</span></div>}
                {selectedEvent.payment_transaction_id && <div><span className="text-slate-400 font-sans">Payment ID:</span> <span className="text-slate-200">{selectedEvent.payment_transaction_id}</span></div>}
              </div>

              {/* Cryptographic Hashes */}
              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 font-mono space-y-1">
                <span className="text-slate-400 font-sans font-semibold text-[11px]">Cryptographic Signatures (SHA-256):</span>
                <div className="text-slate-400 truncate">Previous Hash: <span className="text-slate-300">{selectedEvent.previous_event_hash}</span></div>
                <div className="text-indigo-400 truncate">Event Hash: <span className="text-indigo-300 font-bold">{selectedEvent.event_hash}</span></div>
              </div>

              {/* Sanitized Metadata JSON */}
              <div>
                <span className="text-slate-400 font-semibold text-[11px] block mb-1">Sanitized Event Metadata (Redacted):</span>
                <pre className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-emerald-400 font-mono overflow-x-auto text-[11px]">
                  {JSON.stringify(selectedEvent.metadata || {}, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
      </main>
      <footer className="border-t border-slate-900 bg-slate-950 text-slate-500 text-xs py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <span>Agentic Commerce OS — Trace Explorer & Audit Ledger</span>
          <span className="text-[11px] text-slate-600">SHA-256 Hash Chained</span>
        </div>
      </footer>
    </div>
  );
}
