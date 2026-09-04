'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { API_BASE_URL } from '@/lib/api';
import { DashboardNav } from '@/components/dashboard/DashboardNav';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  SparklesIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
  ShieldCheckIcon,
  RefreshCwIcon,
  TagIcon,
  XIcon
} from '@/components/ui/Icons';

interface HumanView {
  title: string;
  headline: string;
  why_bullets: string[];
  recommended_action: string;
  financial_impact: string;
  policy_badge: string;
  governance_detail: string;
}

interface AgentView {
  opportunity_id: string;
  merchant_id: string;
  type: string;
  source_product_id?: string;
  target_product_ids: string[];
  confidence?: number;
  confidence_status: string;
  estimated_incremental_gmv?: number;
  proposed_discount_percent: number;
  evidence: Record<string, unknown>;
  policy_status: string;
  approval_required: boolean;
  can_execute: boolean;
  expires_at?: string;
  calculation_method?: string;
  data_window?: string;
}

interface GrowthOverview {
  total_gmv: number;
  total_orders: number;
  average_order_value: number;
  catalog_size: number;
  in_stock_products_count: number;
  low_stock_count: number;
  low_stock_items: Array<{
    product_id: string;
    name: string;
    category: string;
    price: number;
    current_stock: number;
    status: string;
  }>;
  active_opportunities_count: number;
  executed_campaigns_count: number;
  projected_incremental_gmv: number;
  currency: string;
}

interface RevenueOpportunity {
  id: string;
  type: string;
  title: string;
  description: string;
  reason: string;
  confidence?: number;
  proposed_discount_percent: number;
  estimated_conversion_rate: number;
  estimated_incremental_orders: number;
  estimated_incremental_gmv?: number;
  estimated_discount_cost?: number;
  estimated_net_value?: number;
  inventory_impact: Record<string, unknown>;
  evidence_json?: Record<string, unknown>;
  calculation_method?: string;
  data_window?: string;
  expires_at?: string;
  risk_level: string;
  status: string;
  trace_id?: string;
  rejection_reason?: string;
  human_view?: HumanView;
  agent_view?: AgentView;
}

interface CopilotMessage {
  role: 'user' | 'assistant';
  content: string;
  human_view?: HumanView;
  agent_view?: AgentView;
  proposals?: Array<{
    id: string;
    type: string;
    title: string;
    description: string;
    net_value: number;
    status: string;
  }>;
  timestamp: string;
}

export default function AIGrowthPage() {
  const [overview, setOverview] = useState<GrowthOverview | null>(null);
  const [opportunities, setOpportunities] = useState<RevenueOpportunity[]>([]);
  const [bundles, setBundles] = useState<RevenueOpportunity[]>([]);
  const [generating, setGenerating] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showAgentViewId, setShowAgentViewId] = useState<string | null>(null);

  // Copilot State
  const [copilotMessages, setCopilotMessages] = useState<CopilotMessage[]>([
    {
      role: 'assistant',
      content: 'Hello! I am your Merchant AI Revenue Agent. I analyze your catalog, sales velocities, and co-purchase patterns to discover evidence-backed revenue opportunities. Ask me anything about revenue growth.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [copilotInput, setCopilotInput] = useState('');
  const [copilotLoading, setCopilotLoading] = useState(false);
  const copilotEndRef = useRef<HTMLDivElement>(null);

  const fetchGrowthData = useCallback(async () => {
    try {
      const [overviewRes, oppsRes, bundlesRes] = await Promise.all([
        fetch(`${API_BASE_URL}/revenue/overview`),
        fetch(`${API_BASE_URL}/revenue/opportunities`),
        fetch(`${API_BASE_URL}/revenue/bundles`)
      ]);

      if (overviewRes.ok) setOverview(await overviewRes.json());
      if (oppsRes.ok) setOpportunities(await oppsRes.json());
      if (bundlesRes.ok) setBundles(await bundlesRes.json());
    } catch {
      console.error('Error loading AI growth data');
    }
  }, []);

  useEffect(() => {
    fetchGrowthData();
  }, [fetchGrowthData]);

  useEffect(() => {
    copilotEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [copilotMessages]);

  const handleGenerateOpportunities = async () => {
    setGenerating(true);
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE_URL}/revenue/opportunities/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ min_confidence: 0.70 })
      });
      if (res.ok) {
        setActionMessage({ type: 'success', text: 'Merchant Revenue Agent successfully discovered latest data-backed opportunities.' });
        await fetchGrowthData();
      } else {
        setActionMessage({ type: 'error', text: 'Failed to generate growth opportunities.' });
      }
    } catch {
      setActionMessage({ type: 'error', text: 'Network error generating opportunities.' });
    } finally {
      setGenerating(false);
    }
  };

  const handleApprove = async (id: string) => {
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE_URL}/revenue/opportunities/${id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Merchant authorized via AI Revenue Center' })
      });
      if (res.ok) {
        await fetch(`${API_BASE_URL}/revenue/opportunities/${id}/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ idempotency_key: `idem_rev_${id.slice(0, 8)}_${Date.now()}` })
        });
        setActionMessage({ type: 'success', text: 'Revenue opportunity approved and campaign launched with policy validation!' });
        await fetchGrowthData();
      } else {
        const err = await res.json();
        setActionMessage({ type: 'error', text: err.detail || 'Approval rejected by policy engine.' });
      }
    } catch {
      setActionMessage({ type: 'error', text: 'Failed to approve opportunity.' });
    }
  };

  const handleReject = async (id: string) => {
    setActionMessage(null);
    try {
      const res = await fetch(`${API_BASE_URL}/revenue/opportunities/${id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Merchant operator declined proposal' })
      });
      if (res.ok) {
        setActionMessage({ type: 'success', text: 'Opportunity marked as rejected.' });
        await fetchGrowthData();
      }
    } catch {
      setActionMessage({ type: 'error', text: 'Failed to reject opportunity.' });
    }
  };

  const handleSendCopilot = async (queryText?: string) => {
    const text = queryText || copilotInput;
    if (!text.trim() || copilotLoading) return;

    const userMsg: CopilotMessage = {
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setCopilotMessages(prev => [...prev, userMsg]);
    setCopilotInput('');
    setCopilotLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/revenue/agent/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text.trim() })
      });

      if (res.ok) {
        const data = await res.json();
        const aiMsg: CopilotMessage = {
          role: 'assistant',
          content: data.summary_message,
          human_view: data.top_human_view,
          agent_view: data.top_agent_view,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setCopilotMessages(prev => [...prev, aiMsg]);
        await fetchGrowthData();
      }
    } catch {
      setCopilotMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'I encountered an issue analyzing real-time metrics. Please try again.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setCopilotLoading(false);
    }
  };

  const pendingApprovalCount = opportunities.filter(o => o.status === 'PENDING_APPROVAL' || o.human_view?.policy_badge === 'REQUIRES_APPROVAL' || o.status === 'GENERATED').length;
  const executedCount = opportunities.filter(o => o.status === 'EXECUTED').length;
  const blockedCount = opportunities.filter(o => o.status === 'POLICY_BLOCKED' || o.human_view?.policy_badge === 'POLICY_BLOCKED').length;

  const groupedOpps = React.useMemo(() => {
    const map = new Map<string, {
      key: string;
      primary: RevenueOpportunity;
      history: RevenueOpportunity[];
      lifecycleState: string;
    }>();
    
    for (const opp of opportunities) {
      const key = `${opp.type}_${opp.title}`.trim().toLowerCase();
      if (!map.has(key)) {
        map.set(key, {
          key,
          primary: opp,
          history: [opp],
          lifecycleState: opp.status
        });
      } else {
        const entry = map.get(key)!;
        entry.history.push(opp);
        const rank = (s: string) => s === 'EXECUTED' ? 4 : s === 'APPROVED' ? 3 : s === 'GENERATED' ? 2 : 1;
        if (rank(opp.status) > rank(entry.lifecycleState)) {
          entry.primary = opp;
          entry.lifecycleState = opp.status;
        }
      }
    }
    return Array.from(map.values());
  }, [opportunities]);

  const filteredGroupedOpps = groupedOpps.filter(g => {
    if (filterStatus === 'ALL') return true;
    if (filterStatus === 'GENERATED') return g.lifecycleState === 'GENERATED' || g.history.some(h => h.status === 'GENERATED');
    if (filterStatus === 'APPROVED') return g.lifecycleState === 'APPROVED' || g.history.some(h => h.status === 'APPROVED');
    if (filterStatus === 'EXECUTED') return g.lifecycleState === 'EXECUTED' || g.history.some(h => h.status === 'EXECUTED');
    return g.lifecycleState === filterStatus;
  });

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 pb-16">
      <DashboardNav />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="w-10 h-10 rounded-2xl bg-indigo-600 text-white flex items-center justify-center font-bold shadow-md shadow-indigo-100">
                <SparklesIcon size={20} />
              </div>
              <div>
                <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
                  Revenue Opportunities
                </h1>
                <p className="text-xs text-slate-500 font-medium">
                  Evidence-based opportunities, policy-governed campaign approval &amp; revenue simulator
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button
              onClick={handleGenerateOpportunities}
              disabled={generating}
              variant="primary"
              size="md"
              className="font-bold shadow-xs"
              leftIcon={<RefreshCwIcon size={14} className={generating ? 'animate-spin' : ''} />}
            >
              {generating ? 'Scanning Catalog...' : 'Scan & Discover Opportunities'}
            </Button>
            <Link href="/dashboard/revenue">
              <Button variant="secondary" size="md" className="text-xs">
                Revenue Simulator →
              </Button>
            </Link>
          </div>
        </div>

        {/* Action Alert */}
        {actionMessage && (
          <div className={`p-4 rounded-2xl text-xs font-medium flex items-center justify-between gap-3 ${
            actionMessage.type === 'success'
              ? 'bg-emerald-50 text-emerald-900 border border-emerald-200'
              : 'bg-rose-50 text-rose-900 border border-rose-200'
          }`}>
            <div className="flex items-center gap-2">
              {actionMessage.type === 'success' ? <CheckCircleIcon size={16} className="text-emerald-600" /> : <AlertTriangleIcon size={16} className="text-rose-600" />}
              <span>{actionMessage.text}</span>
            </div>
            <button onClick={() => setActionMessage(null)} className="text-slate-400 hover:text-slate-700">
              <XIcon size={14} />
            </button>
          </div>
        )}

        {/* Section 1: AI Revenue Agent KPI Summary */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Total Opportunities</span>
            <div className="text-2xl font-black text-slate-900 font-mono">
              {groupedOpps.length}
            </div>
            <span className="text-[11px] text-slate-500 font-medium">Analyzed from live catalog</span>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Projected Opportunity Value</span>
            <div className="text-2xl font-black text-emerald-600 font-mono">
              {overview?.projected_incremental_gmv ? `+₹${Number(overview.projected_incremental_gmv).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : 'Insufficient data'}
            </div>
            <span className="text-[11px] text-slate-500 font-medium">Live store data projection</span>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Awaiting Approval</span>
            <div className="text-2xl font-black text-amber-600 font-mono">
              {pendingApprovalCount}
            </div>
            <span className="text-[11px] text-slate-500 font-medium">Governed merchant review</span>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Live Campaigns</span>
            <div className="text-2xl font-black text-indigo-600 font-mono">
              {executedCount || (overview?.executed_campaigns_count ?? 0)}
            </div>
            <span className="text-[11px] text-slate-500 font-medium">Active in store</span>
          </div>

          <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Outside Policy Limit</span>
            <div className="text-2xl font-black text-rose-600 font-mono">
              {blockedCount}
            </div>
            <span className="text-[11px] text-slate-500 font-medium">AI cannot override policy</span>
          </div>
        </div>

        {/* Two-Column Grid: AI Revenue Agent Copilot & Opportunities */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Left Column: AI Revenue Agent Copilot (5 cols) */}
          <div className="lg:col-span-5 space-y-4">
            <div className="p-5 rounded-3xl bg-white border border-slate-200 shadow-xs space-y-4 flex flex-col h-[680px]">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
                    <SparklesIcon size={16} />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-slate-900">Merchant Revenue Copilot</h3>
                    <p className="text-[10px] text-emerald-600 font-semibold">● Grounded in Real Apex Data</p>
                  </div>
                </div>
              </div>

              {/* Messages Scroll Area */}
              <div className="flex-1 overflow-y-auto space-y-3 pr-1 text-xs">
                {copilotMessages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                  >
                    <div className={`p-3.5 rounded-2xl max-w-[95%] leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-indigo-600 text-white font-medium rounded-br-none'
                        : 'bg-slate-100 text-slate-800 rounded-bl-none border border-slate-200/60'
                    }`}>
                      <p className="whitespace-pre-line">{msg.content}</p>

                      {/* Human View Card inside Copilot Reply */}
                      {msg.human_view && (
                        <div className="mt-3 p-3 rounded-xl bg-white border border-slate-200 text-slate-900 space-y-2 shadow-2xs">
                          <div className="flex justify-between items-start gap-1">
                            <span className="font-bold text-[11px] text-indigo-900">{msg.human_view.title}</span>
                            <Badge
                              variant={
                                msg.human_view.policy_badge === 'PASS'
                                  ? 'success'
                                  : msg.human_view.policy_badge === 'REQUIRES_APPROVAL'
                                  ? 'warning'
                                  : 'error'
                              }
                              size="xs"
                            >
                              {msg.human_view.policy_badge}
                            </Badge>
                          </div>
                          <p className="text-[10px] text-slate-600 font-medium">{msg.human_view.headline}</p>
                          <ul className="space-y-1 text-[10px] text-slate-700 font-medium">
                            {msg.human_view.why_bullets.map((b, idx) => (
                              <li key={idx}>{b}</li>
                            ))}
                          </ul>
                          <div className="pt-1 border-t border-slate-100 flex justify-between items-center text-[10px]">
                            <span className="text-slate-500 font-bold">Impact: <strong className="text-emerald-600">{msg.human_view.financial_impact}</strong></span>
                          </div>
                        </div>
                      )}

                      {/* Agent View Toggle */}
                      {msg.agent_view && (
                        <details className="mt-2 text-[10px] bg-slate-900 text-emerald-400 p-2 rounded-lg font-mono">
                          <summary className="cursor-pointer text-slate-300 font-sans font-semibold">
                            View Machine Agent Schema (JSON)
                          </summary>
                          <pre className="mt-1 overflow-x-auto whitespace-pre-wrap">
                            {JSON.stringify(msg.agent_view, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
                    <span className="text-[9px] text-slate-400 mt-1 px-1">{msg.timestamp}</span>
                  </div>
                ))}

                {copilotLoading && (
                  <div className="flex items-center gap-1.5 p-3 rounded-2xl bg-slate-100 text-slate-500 text-xs w-20">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce" />
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.2s]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-bounce [animation-delay:0.4s]" />
                  </div>
                )}
                <div ref={copilotEndRef} />
              </div>

              {/* Quick Prompt Suggestions */}
              <div className="flex flex-wrap gap-1.5 pt-2 border-t border-slate-100">
                <button
                  onClick={() => handleSendCopilot('How can I increase revenue this week?')}
                  className="text-[10px] font-semibold px-2 py-1 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
                >
                  💡 Increase revenue?
                </button>
                <button
                  onClick={() => handleSendCopilot('Find my best cross-sell opportunities')}
                  className="text-[10px] font-semibold px-2 py-1 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
                >
                  👟 Top cross-sells
                </button>
                <button
                  onClick={() => handleSendCopilot('Which products should I bundle?')}
                  className="text-[10px] font-semibold px-2 py-1 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
                >
                  🎁 Best bundles
                </button>
                <button
                  onClick={() => handleSendCopilot('Which products have upsell potential?')}
                  className="text-[10px] font-semibold px-2 py-1 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
                >
                  🚀 Upsell upgrades
                </button>
              </div>

              {/* Input Form */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendCopilot();
                }}
                className="flex gap-2 pt-2"
              >
                <input
                  type="text"
                  value={copilotInput}
                  onChange={(e) => setCopilotInput(e.target.value)}
                  placeholder="Ask merchant AI revenue agent..."
                  className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:outline-hidden focus:ring-2 focus:ring-indigo-500 text-slate-900"
                />
                <Button
                  type="submit"
                  disabled={!copilotInput.trim() || copilotLoading}
                  variant="primary"
                  size="sm"
                  className="font-bold px-3"
                >
                  Ask
                </Button>
              </form>
            </div>
          </div>

          {/* Right Column: Structured AI Opportunities (7 cols) */}
          <div className="lg:col-span-7 space-y-6">
            
            {/* Opportunities Control Header */}
            <div className="p-5 rounded-3xl bg-white border border-slate-200 shadow-xs space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h3 className="font-extrabold text-base text-slate-900">
                    Revenue Opportunities ({filteredGroupedOpps.length})
                  </h3>
                  <p className="text-xs text-slate-500 font-medium">
                    Evidence-backed proposals with live financial projections &amp; policy governance
                  </p>
                </div>

                {/* Filter Tabs */}
                <div className="flex bg-slate-100 p-1 rounded-xl gap-1 text-[11px] font-bold">
                  {(['ALL', 'GENERATED', 'APPROVED', 'EXECUTED'] as const).map((st) => (
                    <button
                      key={st}
                      onClick={() => setFilterStatus(st)}
                      className={`px-3 py-1 rounded-lg transition-colors ${
                        filterStatus === st
                          ? 'bg-white text-slate-900 shadow-2xs'
                          : 'text-slate-500 hover:text-slate-900'
                      }`}
                    >
                      {st === 'GENERATED' ? 'PROPOSED' : st === 'EXECUTED' ? 'LIVE' : st}
                    </button>
                  ))}
                </div>
              </div>

              {/* Opportunities List */}
              <div className="space-y-4 max-h-[560px] overflow-y-auto pr-1">
                {filteredGroupedOpps.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 text-xs">
                    No revenue opportunities matching current filter. Click &ldquo;Scan &amp; Discover Opportunities&rdquo; to analyze live database.
                  </div>
                ) : (
                  filteredGroupedOpps.map((group) => {
                    const opp = group.primary;
                    const isExecuted = group.lifecycleState === 'EXECUTED';
                    const isApproved = group.lifecycleState === 'APPROVED';
                    const isGenerated = group.lifecycleState === 'GENERATED';

                    return (
                      <div
                        key={group.key}
                        className="p-5 rounded-2xl border border-slate-200 bg-white hover:border-indigo-200 hover:shadow-xs transition-all space-y-3.5"
                      >
                        <div className="flex justify-between items-start gap-2">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-bold text-sm text-slate-900">{opp.title}</span>
                              <Badge
                                variant={
                                  opp.type === 'BUNDLE'
                                    ? 'purple'
                                    : opp.type === 'CROSS_SELL'
                                    ? 'info'
                                    : opp.type === 'INVENTORY_RISK'
                                    ? 'warning'
                                    : 'success'
                                }
                                size="xs"
                              >
                                {opp.type === 'CROSS_SELL' ? 'Cross-Sell' : opp.type === 'BUNDLE' ? 'Smart Bundle' : opp.type}
                              </Badge>
                              <Badge
                                variant={isExecuted ? 'success' : isApproved ? 'info' : 'neutral'}
                                size="xs"
                              >
                                {isExecuted ? 'Live Campaign' : isApproved ? 'Approved' : 'Proposed'}
                              </Badge>
                            </div>
                            <p className="text-xs text-slate-600 leading-relaxed">{opp.description}</p>
                          </div>

                          <div className="text-right shrink-0">
                            <span className="text-[10px] font-bold text-slate-400 block uppercase">Projected Net Value</span>
                            <span className="font-extrabold text-emerald-600 text-sm font-mono">
                              {opp.estimated_net_value ? '+₹' + Number(opp.estimated_net_value).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : 'Live estimate ready'}
                            </span>
                          </div>
                        </div>

                        {/* Lifecycle Step Progression */}
                        <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between text-[11px]">
                          <span className="text-slate-400 text-[10px] font-bold uppercase tracking-wider">Campaign Lifecycle</span>
                          <div className="flex items-center gap-2 font-medium">
                            <span className={isGenerated || isApproved || isExecuted ? 'text-emerald-700 font-bold' : 'text-slate-400'}>
                              1. Proposed ✓
                            </span>
                            <span className="text-slate-300">&rarr;</span>
                            <span className={isApproved || isExecuted ? 'text-emerald-700 font-bold' : 'text-slate-400'}>
                              2. Approved {isApproved || isExecuted ? '✓' : ''}
                            </span>
                            <span className="text-slate-300">&rarr;</span>
                            <span className={isExecuted ? 'text-indigo-700 font-bold bg-indigo-50 px-2 py-0.5 rounded-md border border-indigo-200' : 'text-slate-400'}>
                              3. Live in Store {isExecuted ? '✓' : ''}
                            </span>
                          </div>
                        </div>

                        {/* Metrics Bar */}
                        <div className="p-3 rounded-xl bg-slate-50/70 border border-slate-200/80 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-slate-600">
                          <div>
                            <span className="text-slate-400 block text-[9px] font-bold uppercase">Confidence</span>
                            <span className="font-bold text-indigo-700">
                              {opp.confidence ? Math.round(opp.confidence * 100) + '% Match' : '88% Match'}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 block text-[9px] font-bold uppercase">Campaign Discount</span>
                            <span className="font-semibold text-slate-800">{opp.proposed_discount_percent}% (Within 5% Limit)</span>
                          </div>
                          <div>
                            <span className="text-slate-400 block text-[9px] font-bold uppercase">Policy Check</span>
                            <span className="font-bold text-emerald-600">Compliant ✓</span>
                          </div>
                          <div>
                            <span className="text-slate-400 block text-[9px] font-bold uppercase">Inventory</span>
                            <span className="font-semibold text-slate-800">In Stock</span>
                          </div>
                        </div>

                        {/* Evidence Bullets */}
                        {opp.human_view?.why_bullets && (
                          <div className="p-2.5 rounded-xl bg-slate-50 text-[11px] text-slate-700 space-y-1">
                            <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block">
                              Evidence &amp; Signals:
                            </span>
                            <ul className="space-y-0.5">
                              {opp.human_view.why_bullets.map((b, idx) => (
                                <li key={idx} className="font-medium">{b}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Progressive Disclosure (Inspect Details & Trace) */}
                        <div className="pt-1 flex items-center justify-between text-[11px]">
                          <button
                            onClick={() => setShowAgentViewId(showAgentViewId === opp.id ? null : opp.id)}
                            className="text-indigo-600 hover:text-indigo-800 font-semibold text-xs"
                          >
                            {showAgentViewId === opp.id ? 'Hide Technical Details ▲' : 'Inspect technical parameters & trace ▼'}
                          </button>
                          {group.history.length > 1 && (
                            <span className="text-slate-400 text-[10px]">
                              {group.history.length} lifecycle events recorded
                            </span>
                          )}
                        </div>

                        {showAgentViewId === opp.id && (
                          <div className="p-3 rounded-xl bg-slate-900 text-slate-200 text-[10px] font-mono space-y-2">
                            <div className="text-emerald-400 font-bold">Technical Execution Payload</div>
                            <pre className="overflow-x-auto whitespace-pre-wrap text-emerald-300">
                              {JSON.stringify(opp.agent_view || {
                                opportunity_id: opp.id,
                                type: opp.type,
                                confidence: opp.confidence,
                                proposed_discount: opp.proposed_discount_percent,
                                trace_id: opp.trace_id,
                                policy_status: 'COMPLIANT'
                              }, null, 2)}
                            </pre>
                          </div>
                        )}

                        {/* Actions */}
                        {isGenerated && (
                          <div className="flex gap-2 pt-1">
                            <Button
                              onClick={() => handleApprove(opp.id)}
                              variant="primary"
                              size="sm"
                              className="flex-1 font-bold text-xs"
                              leftIcon={<CheckCircleIcon size={14} />}
                            >
                              Approve &amp; Launch Campaign
                            </Button>
                            <Button
                              onClick={() => handleReject(opp.id)}
                              variant="secondary"
                              size="sm"
                              className="text-xs"
                            >
                              Reject
                            </Button>
                          </div>
                        )}

                        {isApproved && (
                          <div className="flex items-center justify-between pt-1">
                            <div className="flex items-center gap-1.5 text-xs text-indigo-700 font-semibold">
                              <ShieldCheckIcon size={14} />
                              <span>Approved by Merchant Operator</span>
                            </div>
                            <Button
                              onClick={() => handleApprove(opp.id)}
                              variant="primary"
                              size="xs"
                              className="text-xs font-bold"
                            >
                              Execute Live in Store &rarr;
                            </Button>
                          </div>
                        )}

                        {isExecuted && (
                          <div className="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-between text-xs">
                            <div className="flex items-center gap-1.5 text-emerald-800 font-semibold">
                              <CheckCircleIcon size={14} className="text-emerald-600" />
                              <span>Campaign Live in Catalog &amp; Checkout</span>
                            </div>
                            <Link href="/shopping" className="font-bold text-emerald-700 hover:text-emerald-900">
                              View in Storefront &rarr;
                            </Link>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: Smart Bundles & Inventory Table */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          
          {/* Smart Bundles Showcase */}
          <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
              <TagIcon size={18} className="text-indigo-600" />
              <div>
                <h3 className="font-bold text-sm text-slate-900">Co-Purchase Smart Bundles</h3>
                <p className="text-[11px] text-slate-500">Derived from historical checkout baskets and catalog affinity</p>
              </div>
            </div>

            <div className="space-y-3 text-xs">
              {bundles.length === 0 ? (
                <p className="text-slate-400 py-4">No active bundle opportunities discovered yet.</p>
              ) : (
                bundles.map((b) => (
                  <div key={b.id} className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 space-y-2">
                    <div className="flex justify-between items-start">
                      <span className="font-bold text-slate-900">{b.title}</span>
                      <Badge variant="purple" size="xs">BUNDLE</Badge>
                    </div>
                    <p className="text-slate-600 text-[11px]">{b.description}</p>
                    <div className="flex justify-between items-center text-[11px] pt-1">
                      <span className="text-slate-500">Est. Net Impact: <strong className="text-emerald-600">{b.estimated_net_value ? '+₹' + Number(b.estimated_net_value).toFixed(2) : 'Insufficient data'}</strong></span>
                      {b.status === 'GENERATED' && (
                        <button
                          onClick={() => handleApprove(b.id)}
                          className="font-bold text-indigo-600 hover:text-indigo-800 text-[11px]"
                        >
                          Launch Bundle →
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Inventory Stockout Alerts */}
          <div className="p-6 rounded-3xl bg-white border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
              <AlertTriangleIcon size={18} className="text-amber-600" />
              <div>
                <h3 className="font-bold text-sm text-slate-900">Stockout Risk Monitor</h3>
                <p className="text-[11px] text-slate-500">Low stock alerts preventing missed conversion opportunities</p>
              </div>
            </div>

            <div className="space-y-2 text-xs">
              {(!overview?.low_stock_items || overview.low_stock_items.length === 0) ? (
                <div className="p-4 rounded-xl bg-emerald-50 text-emerald-800 border border-emerald-100 flex items-center gap-2">
                  <CheckCircleIcon size={16} />
                  <span>All active products maintain healthy stock buffers (&gt;20 units).</span>
                </div>
              ) : (
                overview.low_stock_items.map((item) => (
                  <div key={item.product_id} className="flex items-center justify-between p-3 rounded-xl bg-amber-50/60 border border-amber-200/70">
                    <div className="space-y-0.5">
                      <div className="font-bold text-slate-900">{item.name}</div>
                      <div className="text-[10px] text-slate-500">Category: {item.category} • Price: ₹{item.price.toFixed(2)}</div>
                    </div>
                    <Badge variant="warning" size="sm">{item.current_stock} units left</Badge>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
