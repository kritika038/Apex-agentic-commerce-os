'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { API_BASE_URL } from '@/lib/api';
import { DashboardNav } from '@/components/dashboard/DashboardNav';

interface RevenueOpportunity {
  id: string;
  type: string;
  title: string;
  description: string;
  reason: string;
  confidence: number;
  proposed_discount_percent: number;
  estimated_incremental_orders: number;
  estimated_incremental_gmv: number;
  estimated_discount_cost: number;
  estimated_net_value: number;
  risk_level: string;
  status: string;
  trace_id?: string;
  rejection_reason?: string;
}

interface RevenueMetrics {
  total_opportunities: number;
  projected_incremental_gmv: number;
  actual_incremental_gmv: number;
  approval_rate: number;
  executed_campaigns: number;
  policy_blocks: number;
  measurement_status: string;
}

interface SimulationResult {
  opportunity_id: string;
  baseline_gmv: number;
  projected_orders: number;
  projected_gmv: number;
  discount_cost: number;
  incremental_gmv: number;
  net_incremental_value: number;
  policy_compliant: boolean;
  policy_check_details: string;
  risk_level: string;
}

const API_BASE = API_BASE_URL;

export default function RevenueAutopilotPage() {
  const [opportunities, setOpportunities] = useState<RevenueOpportunity[]>([]);
  const [metrics, setMetrics] = useState<RevenueMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedOpp, setSelectedOpp] = useState<RevenueOpportunity | null>(null);
  const [simDiscount, setSimDiscount] = useState<number>(5);
  const [simOrders, setSimOrders] = useState<number>(20);
  const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchRevenueData = React.useCallback(async () => {
    setLoading(true);
    try {
      const [oppRes, metricRes] = await Promise.all([
        fetch(`${API_BASE}/revenue/opportunities`),
        fetch(`${API_BASE}/revenue/metrics`)
      ]);
      if (oppRes.ok) {
        const oppData = await oppRes.json();
        setOpportunities(oppData);
        if (oppData.length > 0 && !selectedOpp) {
          setSelectedOpp(oppData[0]);
          setSimDiscount(Number(oppData[0].proposed_discount_percent));
          setSimOrders(oppData[0].estimated_incremental_orders || 20);
        }
      }
      if (metricRes.ok) {
        setMetrics(await metricRes.json());
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [selectedOpp]);

  useEffect(() => {
    fetchRevenueData();
  }, [fetchRevenueData]);

  const handleGenerate = async () => {
    setLoading(true);
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE}/revenue/opportunities/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ min_confidence: 0.70 })
      });
      if (res.ok) {
        setActionMessage({ type: 'success', text: 'Discovered high-affinity revenue opportunities from active catalog.' });
        fetchRevenueData();
      }
    } catch {
      setActionMessage({ type: 'error', text: 'Failed to generate opportunities.' });
    } finally {
      setLoading(false);
    }
  };

  const handleSimulate = async () => {
    if (!selectedOpp) return;
    setLoading(true);
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE}/revenue/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          opportunity_id: selectedOpp.id,
          discount_percent: simDiscount,
          target_orders: simOrders
        })
      });
      if (res.ok) {
        const data = await res.json();
        setSimulationResult(data);
      }
    } catch {
      setActionMessage({ type: 'error', text: 'Simulation failed.' });
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (id: string) => {
    setLoading(true);
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE}/revenue/opportunities/${id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Merchant operator approved revenue campaign' })
      });
      if (res.ok) {
        setActionMessage({ type: 'success', text: 'Opportunity APPROVED by merchant operator.' });
        fetchRevenueData();
      } else {
        const err = await res.json();
        setActionMessage({ type: 'error', text: err.detail || 'Approval rejected by policy.' });
      }
    } catch {
      setActionMessage({ type: 'error', text: 'Approval failed.' });
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async (id: string) => {
    setLoading(true);
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE}/revenue/opportunities/${id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Merchant operator rejected proposal due to margin target.' })
      });
      if (res.ok) {
        setActionMessage({ type: 'success', text: 'Opportunity REJECTED by merchant operator.' });
        fetchRevenueData();
      }
    } catch {
      setActionMessage({ type: 'error', text: 'Rejection failed.' });
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async (id: string) => {
    setLoading(true);
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE}/revenue/opportunities/${id}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idempotency_key: `idemp_exec_ui_${Date.now()}` })
      });
      if (res.ok) {
        setActionMessage({ type: 'success', text: 'Campaign EXECUTED atomically with live inventory check.' });
        fetchRevenueData();
      } else {
        const err = await res.json();
        setActionMessage({ type: 'error', text: err.detail || 'Execution failed.' });
      }
    } catch {
      setActionMessage({ type: 'error', text: 'Execution failed.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans pb-16 flex flex-col justify-between">
      <DashboardNav />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-6">
        {/* Page Sub-Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-white">Revenue Opportunities</h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800/60 font-mono">
                POLICY-GOVERNED
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Evidence-based revenue opportunities projected and simulated with strict policy constraints.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-600/30 transition-all disabled:opacity-50"
            >
              {loading ? 'Analyzing...' : '⚡ Scan & Discover Opportunities'}
            </button>
          </div>
        </div>
        {/* Banner Alert */}
        {actionMessage && (
          <div
            className={`p-3.5 rounded-xl border text-xs font-mono flex items-center justify-between ${
              actionMessage.type === 'success'
                ? 'bg-emerald-950/60 border-emerald-800/60 text-emerald-300'
                : 'bg-rose-950/60 border-rose-800/60 text-rose-300'
            }`}
          >
            <span>{actionMessage.text}</span>
            <button onClick={() => setActionMessage(null)} className="hover:text-white">✕</button>
          </div>
        )}

        {/* Top KPI Cards */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3.5">
            <div className="text-slate-400 text-[11px] font-medium uppercase tracking-wider">Total Opportunities</div>
            <div className="text-2xl font-bold text-white mt-1 font-mono">{metrics?.total_opportunities ?? opportunities.length}</div>
            <div className="text-[10px] text-emerald-400 mt-0.5">Live Store Data</div>
          </div>
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3.5">
            <div className="text-slate-400 text-[11px] font-medium uppercase tracking-wider flex items-center gap-1">
              Projected Value
              <span className="text-[9px] px-1 py-0.2 rounded bg-amber-950 text-amber-300 font-mono">SIMULATED</span>
            </div>
            <div className="text-2xl font-bold text-amber-400 mt-1 font-mono">₹{metrics?.projected_incremental_gmv ? Number(metrics.projected_incremental_gmv).toLocaleString() : '0'}</div>
            <div className="text-[10px] text-slate-500 mt-0.5">Estimated Uplift</div>
          </div>
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3.5">
            <div className="text-slate-400 text-[11px] font-medium uppercase tracking-wider flex items-center gap-1">
              Actual GMV
              <span className="text-[9px] px-1 py-0.2 rounded bg-emerald-950 text-emerald-300 font-mono">ACTUAL</span>
            </div>
            <div className="text-2xl font-bold text-emerald-400 mt-1 font-mono">₹{metrics?.actual_incremental_gmv ? Number(metrics.actual_incremental_gmv).toLocaleString() : '0'}</div>
            <div className="text-[10px] text-emerald-500 mt-0.5">Executed Settlements</div>
          </div>
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3.5">
            <div className="text-slate-400 text-[11px] font-medium uppercase tracking-wider">Approval Rate</div>
            <div className="text-2xl font-bold text-indigo-400 mt-1 font-mono">{metrics?.approval_rate ?? 0}%</div>
            <div className="text-[10px] text-slate-500 mt-0.5">Human Governed</div>
          </div>
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3.5">
            <div className="text-slate-400 text-[11px] font-medium uppercase tracking-wider">Live Campaigns</div>
            <div className="text-2xl font-bold text-cyan-400 mt-1 font-mono">{metrics?.executed_campaigns ?? 0}</div>
            <div className="text-[10px] text-slate-500 mt-0.5">Active in Store</div>
          </div>
          <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-3.5">
            <div className="text-slate-400 text-[11px] font-medium uppercase tracking-wider">Policy Blocks</div>
            <div className="text-2xl font-bold text-rose-400 mt-1 font-mono">{metrics?.policy_blocks ?? 0}</div>
            <div className="text-[10px] text-rose-400 mt-0.5">AI cannot override policy</div>
          </div>
        </div>

        {/* Main 2-Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: Discovered Opportunities List */}
          <div className="lg:col-span-7 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 font-mono flex items-center gap-2">
                Discovered Opportunities
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">
                  {opportunities.length}
                </span>
              </h2>
              <span className="text-xs text-slate-500 font-mono">Live Store Data</span>
            </div>

            {opportunities.length === 0 ? (
              <div className="p-8 rounded-xl border border-slate-800 bg-slate-900/40 text-center space-y-3">
                <div className="text-3xl">🛍️</div>
                <div className="text-sm text-slate-400 font-mono">No active revenue opportunities generated yet.</div>
                <button
                  onClick={handleGenerate}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold font-mono"
                >
                  Scan Merchant Catalog Now
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {opportunities.map((opp) => {
                  const isSelected = selectedOpp?.id === opp.id;
                  return (
                    <div
                      key={opp.id}
                      onClick={() => {
                        setSelectedOpp(opp);
                        setSimDiscount(Number(opp.proposed_discount_percent));
                        setSimOrders(opp.estimated_incremental_orders || 20);
                        setSimulationResult(null);
                      }}
                      className={`p-4 rounded-xl border transition-all cursor-pointer ${
                        isSelected
                          ? 'border-emerald-500/60 bg-emerald-950/20 shadow-lg shadow-emerald-950/30'
                          : 'border-slate-800 bg-slate-900/60 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase bg-slate-800 text-indigo-300 border border-slate-700">
                              {opp.type}
                            </span>
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                                opp.status === 'EXECUTED'
                                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                                  : opp.status === 'APPROVED'
                                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                  : opp.status === 'REJECTED'
                                  ? 'bg-rose-950 text-rose-300 border border-rose-800'
                                  : 'bg-amber-950 text-amber-300 border border-amber-800'
                              }`}
                            >
                              {opp.status === 'EXECUTED' ? 'LIVE' : opp.status}
                            </span>
                            <span className="text-xs text-slate-400 font-mono">
                              Match: {Math.round(opp.confidence * 100)}%
                            </span>
                          </div>
                          <h3 className="text-base font-bold text-white mt-1.5">{opp.title}</h3>
                          <p className="text-xs text-slate-300 mt-1">{opp.description}</p>
                        </div>
                        <div className="text-right flex-shrink-0 font-mono">
                          <div className="text-[10px] text-slate-400">PROJECTED NET VALUE</div>
                          <div className="text-lg font-bold text-emerald-400">
                            +₹{Number(opp.estimated_net_value).toLocaleString()}
                          </div>
                          <div className="text-[10px] text-slate-500">
                            Disc: {opp.proposed_discount_percent}% | ~{opp.estimated_incremental_orders} orders
                          </div>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="mt-3.5 pt-3 border-t border-slate-800/80 flex items-center justify-between">
                        <div className="text-[11px] text-slate-400 font-mono flex items-center gap-1.5">
                          <span>Risk:</span>
                          <span className={opp.risk_level === 'LOW' ? 'text-emerald-400' : 'text-amber-400 font-bold'}>
                            {opp.risk_level}
                          </span>
                          {opp.trace_id && (
                            <Link
                              href={`/dashboard/observability?trace_id=${opp.trace_id}`}
                              className="text-indigo-400 hover:text-indigo-300 underline ml-2"
                            >
                              Trace: {opp.trace_id.slice(0, 12)}...
                            </Link>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {opp.status === 'GENERATED' || opp.status === 'SIMULATED' ? (
                            <>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleApprove(opp.id);
                                }}
                                className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold font-mono"
                              >
                                Approve
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleReject(opp.id);
                                }}
                                className="px-3 py-1 rounded bg-slate-800 hover:bg-rose-950 hover:text-rose-300 text-slate-300 text-xs font-mono"
                              >
                                Reject
                              </button>
                            </>
                          ) : opp.status === 'APPROVED' ? (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleExecute(opp.id);
                              }}
                              className="px-3 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold font-mono"
                            >
                              ⚡ Launch Campaign
                            </button>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Right: Revenue Simulator & Why Apex Rejected This */}
          <div className="lg:col-span-5 space-y-4">
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-xl">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-white font-mono flex items-center gap-2">
                    <span>🔬</span>
                    Revenue Simulator
                  </h3>
                  <p className="text-[11px] text-slate-400 font-sans mt-0.5">
                    See the expected impact before launching a campaign.
                  </p>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800/60 font-mono">
                  POLICY-CONTROLLED
                </span>
              </div>

              {selectedOpp ? (
                <div className="space-y-4">
                  <div className="text-xs text-slate-300 font-mono">
                    Target: <span className="text-white font-bold">{selectedOpp.title}</span>
                  </div>

                  {/* Sliders */}
                  <div className="space-y-3 bg-slate-950/60 p-3.5 rounded-xl border border-slate-800">
                    <div>
                      <div className="flex justify-between text-xs font-mono text-slate-300 mb-1">
                        <span>Campaign Discount %</span>
                        <span className={`font-bold ${simDiscount > 5 ? 'text-rose-400' : 'text-emerald-400'}`}>
                          {simDiscount}% {simDiscount > 5 ? '(Outside policy)' : '(Compliant)'}
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="25"
                        step="1"
                        value={simDiscount}
                        onChange={(e) => setSimDiscount(Number(e.target.value))}
                        className="w-full accent-emerald-500 bg-slate-800"
                      />
                      <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-0.5">
                        <span>0% (Full Price)</span>
                        <span className="text-emerald-400">5% (Maximum allowed)</span>
                        <span className="text-rose-400">25% (Outside policy)</span>
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-xs font-mono text-slate-300 mb-1">
                        <span>Expected Orders Volume</span>
                        <span className="text-cyan-400 font-bold">{simOrders} units</span>
                      </div>
                      <input
                        type="range"
                        min="5"
                        max="100"
                        step="5"
                        value={simOrders}
                        onChange={(e) => setSimOrders(Number(e.target.value))}
                        className="w-full accent-cyan-500 bg-slate-800"
                      />
                    </div>

                    <button
                      onClick={handleSimulate}
                      disabled={loading}
                      className="w-full py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold font-mono transition-all shadow-lg shadow-indigo-600/30"
                    >
                      Run Revenue Simulation
                    </button>
                  </div>

                  {/* Simulation Output Card */}
                  {simulationResult && (
                    <div
                      className={`p-4 rounded-xl border space-y-2.5 font-mono ${
                        simulationResult.policy_compliant
                          ? 'border-emerald-800/80 bg-emerald-950/20'
                          : 'border-rose-800/80 bg-rose-950/30'
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-400">POLICY COMPLIANCE:</span>
                        <span
                          className={`font-bold ${
                            simulationResult.policy_compliant ? 'text-emerald-400' : 'text-rose-400'
                          }`}
                        >
                          {simulationResult.policy_compliant ? '✓ PASS (Policy Compliant)' : '❌ BLOCKED (Outside policy)'}
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-300">
                        {simulationResult.policy_compliant
                          ? simulationResult.policy_check_details
                          : 'Apex will not launch campaigns outside merchant policy.'}
                      </div>

                      <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800 text-xs">
                        <div>
                          <div className="text-[10px] text-slate-400">PROJECTED VALUE</div>
                          <div className="text-sm font-bold text-white">
                            ₹{Number(simulationResult.projected_gmv).toLocaleString()}
                          </div>
                        </div>
                        <div>
                          <div className="text-[10px] text-slate-400">DISCOUNT COST</div>
                          <div className="text-sm font-bold text-rose-400">
                            -₹{Number(simulationResult.discount_cost).toLocaleString()}
                          </div>
                        </div>
                        <div>
                          <div className="text-[10px] text-slate-400">NET INCREMENTAL VALUE</div>
                          <div className="text-base font-bold text-emerald-400">
                            +₹{Number(simulationResult.net_incremental_value).toLocaleString()}
                          </div>
                        </div>
                        <div>
                          <div className="text-[10px] text-slate-400">RISK TIER</div>
                          <div
                            className={`text-sm font-bold ${
                              simulationResult.risk_level === 'LOW'
                                ? 'text-emerald-400'
                                : simulationResult.risk_level === 'MEDIUM'
                                ? 'text-amber-400'
                                : 'text-rose-400'
                            }`}
                          >
                            {simulationResult.risk_level}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-xs text-slate-500 font-mono text-center py-6">
                  Select an opportunity from the left panel to test what-if parameters.
                </div>
              )}
            </div>

            {/* "Why Apex Rejected This" Dedicated Decision Panel */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold uppercase tracking-wider text-rose-400 font-mono flex items-center gap-2">
                  <span>🛡️</span>
                  Why Apex Rejected This
                </h3>
                <span className="text-[10px] px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800 font-mono">
                  BLOCKED
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed font-sans">
                The AI recommendation exceeds the merchant&apos;s configured discount limit.
              </p>

              <div className="p-3.5 rounded-xl border border-slate-800 bg-slate-950/70 space-y-2 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-400">AI suggestion:</span>
                  <span className="text-rose-400 font-bold">23.00% discount</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Merchant policy:</span>
                  <span className="text-emerald-400 font-bold">Maximum allowed: 5.00%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Decision:</span>
                  <span className="text-rose-400 font-bold">BLOCKED (AI cannot override policy)</span>
                </div>
                <div className="flex justify-between pt-1 border-t border-slate-800 text-[11px]">
                  <span className="text-slate-500">Principle:</span>
                  <span className="text-indigo-400 font-semibold">AI can recommend. Policy controls execution.</span>
                </div>
              </div>

              {/* Progressive Disclosure: Technical Decision Inspection */}
              <details className="text-[11px] text-slate-400 pt-1 cursor-pointer">
                <summary className="font-semibold text-indigo-400 hover:text-indigo-300">
                  Inspect technical decision &amp; trace
                </summary>
                <div className="mt-2 p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-1 font-mono text-[10px]">
                  <div>Rule: <span className="text-slate-200">MAX_DISCOUNT_PERCENT_GUARD (Cap: 5.0%)</span></div>
                  <div>Policy Version: <span className="text-slate-200">v1.4-deterministic</span></div>
                  <div>Evaluation ID: <span className="text-slate-200">eval_margin_ceiling_01</span></div>
                  <div>Audit Event: <span className="text-slate-200">OPP_POLICY_REJECTED (Committed to SHA-256 Ledger)</span></div>
                </div>
              </details>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
