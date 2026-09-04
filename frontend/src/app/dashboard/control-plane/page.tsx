'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { apiClient } from '@/lib/api';
import { DashboardNav } from '@/components/dashboard/DashboardNav';

interface AgentFirewallRule {
  agent_id: string;
  name: string;
  type: string;
  version: string;
  status: string;
  granted_permissions: string[];
  forbidden_permissions: string[];
  allowed_tools: string[];
  isolation_level: string;
  can_authorize_payments: boolean;
  can_modify_prices: boolean;
}

interface FirewallResponse {
  merchant_id: string;
  firewall_status: string;
  total_agents: number;
  agents: AgentFirewallRule[];
  global_security_invariants: string[];
}

interface AuditEvent {
  id: string;
  trace_id: string;
  actor_type: string;
  actor_id: string;
  action: string;
  decision?: string;
  risk_level?: string;
  status: string;
  reason?: string;
  created_at: string;
  metadata_json?: Record<string, unknown>;
}

export default function ControlPlanePage() {
  const [firewall, setFirewall] = useState<FirewallResponse | null>(null);
  const [recentEvents, setRecentEvents] = useState<AuditEvent[]>([]);
  const [selectedTraceId, setSelectedTraceId] = useState<string>('');
  const [traceEvents, setTraceEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedScenario, setSelectedScenario] = useState<string>('SCENARIO_A');

  const fetchTraceDetails = async (traceId: string) => {
    setSelectedTraceId(traceId);
    try {
      const { data } = await apiClient.get(`/audit/traces/${traceId}`);
      if (data && data.events) {
        setTraceEvents(data.events);
      }
    } catch (err) {
      console.error('Error fetching trace details:', err);
    }
  };

  const fetchInitialData = React.useCallback(async () => {
    setLoading(true);
    try {
      // 1. Fetch Firewall Matrix
      const { data: fwData } = await apiClient.get('/agents/firewall');
      setFirewall(fwData);

      // 2. Fetch Recent Audit Events
      const { data: eventsData } = await apiClient.get('/audit/events?limit=20');
      if (eventsData && eventsData.items) {
        setRecentEvents(eventsData.items);
        if (eventsData.items.length > 0) {
          const firstTrace = eventsData.items[0].trace_id;
          setSelectedTraceId(firstTrace);
          fetchTraceDetails(firstTrace);
        }
      }
    } catch (err) {
      console.error('Error loading control plane data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  const getLayerBadge = (actorType: string, action: string) => {
    if (action.includes('PAYMENT') || action.includes('WEBHOOK') || action.includes('RECONCIL')) {
      return { label: 'PROVIDER SETTLEMENT', bg: 'bg-emerald-950/80 text-emerald-300 border-emerald-800/50' };
    }
    if (action.includes('APPROVAL') || actorType === 'USER') {
      return { label: 'HUMAN GOVERNANCE', bg: 'bg-amber-950/80 text-amber-300 border-amber-800/50' };
    }
    if (action.includes('POLICY') || action.includes('AUTHORIZ') || action.includes('INTENT')) {
      return { label: 'DETERMINISTIC ENGINE', bg: 'bg-sky-950/80 text-sky-300 border-sky-800/50' };
    }
    return { label: 'AI REASONING', bg: 'bg-indigo-950/80 text-indigo-300 border-indigo-800/50' };
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col justify-between">
      <DashboardNav />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white flex items-center gap-2">
              <span>Executive AI Commerce Control Plane</span>
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-indigo-950 text-indigo-400 border border-indigo-800/60">
              LIVE TELEMETRY
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Real-time governance dashboard visualizing AI reasoning boundaries, deterministic policies, and payment authority.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Link
            href="/dashboard/protocol"
            className="px-3.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-slate-300 hover:text-white transition-colors"
          >
            AI Protocol Explorer →
          </Link>
          <Link
            href="/dashboard/observability"
            className="px-3.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-slate-300 hover:text-white transition-colors"
          >
            Audit Trail Explorer →
          </Link>
          <button
            onClick={fetchInitialData}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-all disabled:opacity-50 font-mono"
          >
            {loading ? 'Refreshing...' : 'Refresh Telemetry'}
          </button>
        </div>
      </div>

      {/* Security Status Panel (Live Guarantees) */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Price Authority</div>
          <div className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            DATABASE_GROUNDED
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Payment Boundary</div>
          <div className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            RESTRICTED_AUTHORIZATION
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Policy Engine</div>
          <div className="text-xs font-bold text-sky-400 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-sky-400" />
            OUTSIDE_LLM_CONTEXT
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">State Machine</div>
          <div className="text-xs font-bold text-indigo-400 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-indigo-400" />
            UNKNOWN ≠ FAILED
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Audit Integrity</div>
          <div className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            SHA-256 HASH_CHAINED
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1">
          <div className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">Tenant Isolation</div>
          <div className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            STRICT_ROW_SCOPED
          </div>
        </div>
      </div>

      {/* 1. Live Architecture Visualization Card */}
      <div className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800/80 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <span>Live System Architecture Pipeline</span>
          </h2>
          <div className="flex items-center gap-4 text-[11px] font-mono">
            <span className="flex items-center gap-1.5 text-indigo-300">
              <span className="w-2.5 h-2.5 rounded bg-indigo-500" /> AI Layer
            </span>
            <span className="flex items-center gap-1.5 text-sky-300">
              <span className="w-2.5 h-2.5 rounded bg-sky-500" /> Deterministic Layer
            </span>
            <span className="flex items-center gap-1.5 text-amber-300">
              <span className="w-2.5 h-2.5 rounded bg-amber-500" /> Human Layer
            </span>
            <span className="flex items-center gap-1.5 text-emerald-300">
              <span className="w-2.5 h-2.5 rounded bg-emerald-500" /> Settlement Layer
            </span>
          </div>
        </div>

        {/* Pipeline Nodes */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5 pt-2">
          {/* Node 1 */}
          <div className="p-3 rounded-xl bg-indigo-950/40 border border-indigo-800/60 space-y-1 text-center">
            <div className="text-[9px] font-mono text-indigo-400 font-bold uppercase">AI Layer</div>
            <div className="font-semibold text-xs text-white">AI Buyer</div>
            <div className="text-[10px] text-slate-400 font-mono">Inbound Query</div>
          </div>

          {/* Node 2 */}
          <div className="p-3 rounded-xl bg-indigo-950/40 border border-indigo-800/60 space-y-1 text-center">
            <div className="text-[9px] font-mono text-indigo-400 font-bold uppercase">AI Layer</div>
            <div className="font-semibold text-xs text-white">Shopping Agent</div>
            <div className="text-[10px] text-slate-400 font-mono">Product Search</div>
          </div>

          {/* Node 3 */}
          <div className="p-3 rounded-xl bg-indigo-950/40 border border-indigo-800/60 space-y-1 text-center">
            <div className="text-[9px] font-mono text-indigo-400 font-bold uppercase">AI Layer</div>
            <div className="font-semibold text-xs text-white">Sales Agent</div>
            <div className="text-[10px] text-slate-400 font-mono">Recommendations</div>
          </div>

          {/* Node 4 */}
          <div className="p-3 rounded-xl bg-sky-950/40 border border-sky-800/60 space-y-1 text-center">
            <div className="text-[9px] font-mono text-sky-400 font-bold uppercase">Deterministic</div>
            <div className="font-semibold text-xs text-white">Firewall & Intent</div>
            <div className="text-[10px] text-slate-400 font-mono">Cart Total Check</div>
          </div>

          {/* Node 5 */}
          <div className="p-3 rounded-xl bg-sky-950/40 border border-sky-800/60 space-y-1 text-center">
            <div className="text-[9px] font-mono text-sky-400 font-bold uppercase">Deterministic</div>
            <div className="font-semibold text-xs text-white">Policy & Risk</div>
            <div className="text-[10px] text-slate-400 font-mono">Rule Evaluation</div>
          </div>

          {/* Node 6 */}
          <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-800/60 space-y-1 text-center">
            <div className="text-[9px] font-mono text-amber-400 font-bold uppercase">Governance</div>
            <div className="font-semibold text-xs text-white">Human Approval</div>
            <div className="text-[10px] text-slate-400 font-mono">Dual Custody</div>
          </div>

          {/* Node 7 */}
          <div className="p-3 rounded-xl bg-sky-950/40 border border-sky-800/60 space-y-1 text-center">
            <div className="text-[9px] font-mono text-sky-400 font-bold uppercase">Deterministic</div>
            <div className="font-semibold text-xs text-white">Authorization</div>
            <div className="text-[10px] text-slate-400 font-mono">10-min Token</div>
          </div>

          {/* Node 8 */}
          <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-800/60 space-y-1 text-center">
            <div className="text-[9px] font-mono text-emerald-400 font-bold uppercase">Settlement</div>
            <div className="font-semibold text-xs text-white">Razorpay Provider</div>
            <div className="text-[10px] text-slate-400 font-mono">HMAC & Captures</div>
          </div>
        </div>
      </div>

      {/* 2. Interactive Scenario Demo Selector */}
      <div className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800/80 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider font-mono">
            Interactive Scenario Selector
          </h2>
          <span className="text-xs text-slate-400 font-mono">1-Click Live Demonstration Flows</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <button
            onClick={() => setSelectedScenario('SCENARIO_A')}
            className={`p-3.5 rounded-xl border text-left transition-all ${
              selectedScenario === 'SCENARIO_A'
                ? 'bg-indigo-950/60 border-indigo-500 shadow-md shadow-indigo-950'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="text-[10px] font-mono text-indigo-400 font-bold">SCENARIO A</div>
            <div className="text-xs font-bold text-white mt-1">Low-Risk Purchase</div>
            <div className="text-[11px] text-slate-400 mt-1">Total &lt; ₹2,000 → Auto-authorized by Policy Engine.</div>
          </button>

          <button
            onClick={() => setSelectedScenario('SCENARIO_B')}
            className={`p-3.5 rounded-xl border text-left transition-all ${
              selectedScenario === 'SCENARIO_B'
                ? 'bg-amber-950/60 border-amber-500 shadow-md shadow-amber-950'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="text-[10px] font-mono text-amber-400 font-bold">SCENARIO B</div>
            <div className="text-xs font-bold text-white mt-1">High-Risk Approval</div>
            <div className="text-[11px] text-slate-400 mt-1">Total &gt; ₹5,000 → Pauses for Human Operator Approval.</div>
          </button>

          <button
            onClick={() => setSelectedScenario('SCENARIO_C')}
            className={`p-3.5 rounded-xl border text-left transition-all ${
              selectedScenario === 'SCENARIO_C'
                ? 'bg-emerald-950/60 border-emerald-500 shadow-md shadow-emerald-950'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="text-[10px] font-mono text-emerald-400 font-bold">SCENARIO C</div>
            <div className="text-xs font-bold text-white mt-1">Gateway Timeout Recovery</div>
            <div className="text-[11px] text-slate-400 mt-1">Network drop → UNKNOWN state → Reconciled safely.</div>
          </button>

          <button
            onClick={() => setSelectedScenario('SCENARIO_D')}
            className={`p-3.5 rounded-xl border text-left transition-all ${
              selectedScenario === 'SCENARIO_D'
                ? 'bg-rose-950/60 border-rose-500 shadow-md shadow-rose-950'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="text-[10px] font-mono text-rose-400 font-bold">SCENARIO D</div>
            <div className="text-xs font-bold text-white mt-1">Prompt Injection Block</div>
            <div className="text-[11px] text-slate-400 mt-1">Buyer forces ₹1 price → DB authority enforces true price.</div>
          </button>

          <button
            onClick={() => setSelectedScenario('SCENARIO_E')}
            className={`p-3.5 rounded-xl border text-left transition-all ${
              selectedScenario === 'SCENARIO_E'
                ? 'bg-sky-950/60 border-sky-500 shadow-md shadow-sky-950'
                : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`}
          >
            <div className="text-[10px] font-mono text-sky-400 font-bold">SCENARIO E</div>
            <div className="text-xs font-bold text-white mt-1">A2A Commerce Protocol</div>
            <div className="text-[11px] text-slate-400 mt-1">Autonomous bot executes end-to-end JSON transaction.</div>
          </button>
        </div>
      </div>

      {/* 3. Main Grid: "Why Did AI Do This?" Breakdown + Agent Permission Firewall */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: "Why Did AI Do This?" Inspector (7 Cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <span>Why Did AI Do This? — Transaction Decision Lineage</span>
            </h2>
            <div className="text-xs font-mono text-slate-400">
              Trace: <span className="text-indigo-400 font-bold">{selectedTraceId || 'No trace selected'}</span>
            </div>
          </div>

          {/* Trace Selector Dropdown */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-mono text-slate-400">Select Session Trace:</label>
            <select
              value={selectedTraceId}
              onChange={(e) => fetchTraceDetails(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500 flex-1"
            >
              {recentEvents.map((ev) => (
                <option key={ev.id} value={ev.trace_id}>
                  {ev.trace_id} — {ev.action} ({ev.actor_id})
                </option>
              ))}
            </select>
          </div>

          {/* Step Timeline */}
          <div className="space-y-3 pt-2">
            {traceEvents.length > 0 ? (
              traceEvents.map((step, idx) => {
                const badge = getLayerBadge(step.actor_type, step.action);
                return (
                  <div
                    key={step.id || idx}
                    className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-2 relative"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="w-5 h-5 rounded-full bg-slate-800 text-[10px] font-mono font-bold flex items-center justify-center text-slate-300">
                          {idx + 1}
                        </span>
                        <span className="font-bold text-xs text-white">{step.action}</span>
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${badge.bg}`}>
                          {badge.label}
                        </span>
                      </div>
                      <span className="text-[10px] font-mono text-slate-400">
                        {step.created_at ? new Date(step.created_at).toLocaleTimeString() : ''}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs font-mono text-slate-300 pt-1">
                      <div>
                        <span className="text-slate-500">Actor:</span>{' '}
                        <span className="text-slate-200">{step.actor_id} ({step.actor_type})</span>
                      </div>
                      <div>
                        <span className="text-slate-500">Status:</span>{' '}
                        <span className={step.status === 'SUCCESS' ? 'text-emerald-400' : 'text-amber-400'}>
                          {step.status}
                        </span>
                      </div>
                      {step.decision && (
                        <div>
                          <span className="text-slate-500">Decision:</span>{' '}
                          <span className="text-sky-400 font-bold">{step.decision}</span>
                        </div>
                      )}
                      {step.risk_level && (
                        <div>
                          <span className="text-slate-500">Risk Level:</span>{' '}
                          <span className={step.risk_level === 'LOW' ? 'text-emerald-400' : 'text-rose-400 font-bold'}>
                            {step.risk_level}
                          </span>
                        </div>
                      )}
                    </div>

                    {step.reason && (
                      <div className="p-2 rounded bg-slate-950/80 border border-slate-800 text-xs text-slate-300 font-mono">
                        <span className="text-slate-500">Reason:</span> {step.reason}
                      </div>
                    )}

                    {step.metadata_json && Object.keys(step.metadata_json).length > 0 && (
                      <details className="text-[11px] font-mono text-slate-400 pt-1">
                        <summary className="cursor-pointer hover:text-slate-200">View Metadata Snapshot</summary>
                        <pre className="mt-1 p-2 rounded bg-slate-950 border border-slate-800 text-[10px] text-indigo-300 overflow-x-auto">
                          {JSON.stringify(step.metadata_json, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="p-8 text-center rounded-xl bg-slate-900/30 border border-dashed border-slate-800 text-xs text-slate-400">
                Select a trace from above or trigger an AI request to inspect the live decision lineage.
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Agent Permission Firewall Matrix (5 Cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <span>Agent Permission Firewall</span>
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
              ACTIVE ENFORCEMENT
            </span>
          </div>

          <div className="space-y-3">
            {firewall && firewall.agents ? (
              firewall.agents.map((ag) => (
                <div
                  key={ag.agent_id}
                  className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80 space-y-2.5"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-white">{ag.name}</h4>
                      <span className="text-[10px] font-mono text-indigo-400">{ag.type} • v{ag.version}</span>
                    </div>
                    <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                      {ag.isolation_level}
                    </span>
                  </div>

                  {/* Granted Permissions */}
                  <div>
                    <div className="text-[10px] font-mono text-emerald-400 font-semibold mb-1">
                      ✓ GRANTED PERMISSIONS:
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {ag.granted_permissions.map((p) => (
                        <span key={p} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-800/40">
                          {p}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Forbidden Permissions */}
                  <div>
                    <div className="text-[10px] font-mono text-rose-400 font-semibold mb-1">
                      ✕ FORBIDDEN PERMISSIONS:
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {ag.forbidden_permissions.map((p) => (
                        <span key={p} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-rose-950/60 text-rose-300 border border-rose-800/40">
                          {p}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Security Invariants for this Agent */}
                  <div className="pt-2 border-t border-slate-800/80 grid grid-cols-2 gap-2 text-[10px] font-mono">
                    <div className="text-slate-400">
                      Can Authorize Pay: <span className={ag.can_authorize_payments ? 'text-rose-400' : 'text-emerald-400 font-bold'}>{ag.can_authorize_payments ? 'YES' : 'NO (BLOCKED)'}</span>
                    </div>
                    <div className="text-slate-400">
                      Can Modify Price: <span className={ag.can_modify_prices ? 'text-rose-400' : 'text-emerald-400 font-bold'}>{ag.can_modify_prices ? 'YES' : 'NO (BLOCKED)'}</span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-8 text-center text-xs text-slate-400">Loading Firewall Matrix...</div>
            )}
          </div>
        </div>
      </div>
      </main>
      <footer className="border-t border-slate-900 bg-slate-950 text-slate-500 text-xs py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <span>Agentic Commerce OS — Merchant Control Plane</span>
          <span className="text-[11px] text-slate-600">Deterministic Governance Layer Active</span>
        </div>
      </footer>
    </div>
  );
}
