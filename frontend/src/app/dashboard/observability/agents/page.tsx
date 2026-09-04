"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { API_BASE_URL } from '@/lib/api';
import { DashboardNav } from '@/components/dashboard/DashboardNav';

interface AgentMetrics {
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  average_latency_ms: number;
  p95_latency_ms: number | string;
  total_tool_calls: number;
  total_tokens_used: number;
}

interface AgentTrace {
  id: string;
  trace_id: string;
  agent_id: string;
  agent_type: string;
  agent_version: string;
  model: string;
  provider: string;
  status: string;
  token_usage: number;
  latency_ms: number;
  tool_call_count: number;
  started_at: string;
  completed_at?: string;
  steps: Array<{
    id: string;
    sequence_number: number;
    step_type: string;
    tool_name?: string;
    decision?: string;
    duration_ms: number;
    status: string;
  }>;
}

export default function AgentObservabilityPage() {
  const [metrics, setMetrics] = useState<AgentMetrics | null>(null);
  const [traces, setTraces] = useState<AgentTrace[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAgentData = async () => {
    setLoading(true);
    try {
      // 1. Fetch metrics
      const resMetrics = await fetch(`${API_BASE_URL}/audit/metrics`);
      if (resMetrics.ok) {
        const data = await resMetrics.json();
        setMetrics(data.agent);
      }

      // 2. Fetch agent traces
      const resTraces = await fetch(`${API_BASE_URL}/audit/agents/shopping_agent_v1/traces`);
      if (resTraces.ok) {
        const traceData = await resTraces.json();
        setTraces(traceData);
      }
    } catch {
      // Backend may be offline during build
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgentData();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col justify-between">
      <DashboardNav />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-bold text-white">
                Agent Observability & Performance
              </h1>
            </div>
            <p className="text-slate-400 text-xs sm:text-sm mt-1">
              Database-derived execution telemetry, tool call distributions, latency benchmarks, and step analytics.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard/observability"
              className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 transition"
            >
              🔍 Trace Explorer
            </Link>
          </div>
        </div>

        {/* Aggregate KPI Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <div className="p-5 bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl">
            <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Total Executions</span>
            <p className="text-2xl font-extrabold text-slate-100 mt-2">{metrics?.total_runs ?? 0}</p>
            <p className="text-xs text-emerald-400 mt-1">
              {metrics ? `${Math.round((metrics.successful_runs / (metrics.total_runs || 1)) * 100)}% Success Rate` : "N/A"}
            </p>
          </div>

          <div className="p-5 bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl">
            <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Avg / p95 Latency</span>
            <p className="text-2xl font-extrabold text-indigo-300 mt-2">
              {metrics?.average_latency_ms ? `${metrics.average_latency_ms}ms` : "0ms"}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              p95: <span className="font-mono text-purple-300">{metrics?.p95_latency_ms ?? "N/A"}</span>
            </p>
          </div>

          <div className="p-5 bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl">
            <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Tool Calls Executed</span>
            <p className="text-2xl font-extrabold text-cyan-300 mt-2">{metrics?.total_tool_calls ?? 0}</p>
            <p className="text-xs text-slate-400 mt-1">
              {metrics?.total_runs ? `${(metrics.total_tool_calls / metrics.total_runs).toFixed(1)} calls / run` : "0 calls / run"}
            </p>
          </div>

          <div className="p-5 bg-slate-900/90 border border-slate-800 rounded-xl shadow-xl">
            <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Token Usage</span>
            <p className="text-2xl font-extrabold text-amber-300 mt-2">{metrics?.total_tokens_used ?? 0}</p>
            <p className="text-xs text-slate-400 mt-1">Structured LLM telemetry</p>
          </div>
        </div>

        {/* Traces & Step Breakdown List */}
        <div className="mt-8 bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-2xl">
          <h3 className="text-lg font-bold text-slate-100 mb-4 flex items-center gap-2">
            <span>📊</span> Recent Agent Traces & Step Telemetry
          </h3>

          {loading ? (
            <p className="text-sm text-slate-500 py-8 text-center animate-pulse">Loading agent telemetry from database...</p>
          ) : traces.length === 0 ? (
            <p className="text-sm text-slate-500 py-8 text-center">No agent traces recorded yet. Run a shopping flow to populate telemetry.</p>
          ) : (
            <div className="space-y-4">
              {traces.map((trace) => (
                <div key={trace.id} className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
                        {trace.agent_id}
                      </span>
                      <span className="text-xs text-slate-400 font-mono">Trace: {trace.trace_id}</span>
                      <span className="text-xs text-slate-400">Model: {trace.model}</span>
                    </div>
                    <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
                      <span>Latency: <strong className="text-indigo-300">{Math.round(trace.latency_ms)}ms</strong></span>
                      <span>Tokens: <strong className="text-amber-300">{trace.token_usage}</strong></span>
                      <span>Tools: <strong className="text-cyan-300">{trace.tool_call_count}</strong></span>
                    </div>
                  </div>

                  {trace.steps && trace.steps.length > 0 && (
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-2">
                      {trace.steps.map((step) => (
                        <div key={step.id} className="p-2.5 rounded-lg bg-slate-900 border border-slate-800/60 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-200">Step #{step.sequence_number}: {step.tool_name || step.step_type}</span>
                            <span className="text-emerald-400 font-mono text-[11px]">{Math.round(step.duration_ms)}ms</span>
                          </div>
                          {step.decision && <p className="text-[11px] text-slate-400 mt-1 truncate">{step.decision}</p>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
      <footer className="border-t border-slate-900 bg-slate-950 text-slate-500 text-xs py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <span>Agentic Commerce OS — Agent Analytics</span>
          <span className="text-[11px] text-slate-600">Live Telemetry Active</span>
        </div>
      </footer>
    </div>
  );
}
