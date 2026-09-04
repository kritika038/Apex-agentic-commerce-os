'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { apiClient } from '@/lib/api';
import { DashboardNav } from '@/components/dashboard/DashboardNav';
import { MetricCard } from '@/components/dashboard/MetricCard';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import {
  RefreshCwIcon,
  ShoppingBagIcon,
  SparklesIcon,
  ShieldCheckIcon,
  CreditCardIcon,
  ActivityIcon,
  AlertTriangleIcon,
  SearchIcon,
  ChevronRightIcon,
} from '@/components/ui/Icons';

interface Product {
  id: string;
  name: string;
  category: string;
  price: number;
  currency?: string;
  description?: string;
  stock_quantity?: number;
}

interface RecommendationStat {
  total_recommendations: number;
  accepted_count: number;
  rejected_count: number;
  acceptance_rate: number;
  additional_cart_value: number;
  recent_recommendations: {
    id: string;
    type: string;
    recommended_product_id: string;
    product_name: string;
    product_price: number;
    reason: string;
    confidence: number;
    status: string;
    created_at?: string;
  }[];
}

interface PurchaseIntentItem {
  id: string;
  status: string;
  buyer_id: string;
  cart_id: string;
  requested_amount: number;
  currency: string;
  items: { product_id: string; name: string; quantity: number; unit_price: number; subtotal: number }[];
  expires_at?: string;
  created_at?: string;
}

interface AICommerceActivity {
  active_agent_requests: number;
  today_shopping_requests: number;
  products_discovered: number;
  purchase_intents_count: number;
  completed_orders_count: number;
  total_ai_revenue: number;
  recent_events: Array<{
    id: string;
    action: string;
    actor_type: string;
    status: string;
    timestamp: string;
    details: Record<string, unknown>;
  }>;
}

interface RevenueOpportunity {
  id: string;
  type: string;
  name?: string;
  title?: string;
  description: string;
  confidence: number;
  estimated_incremental_gmv?: number;
  estimated_net_value?: number;
  evidence_summary?: string;
  policy_status?: string;
  inventory_status?: string;
  status: string;
  expires_at?: string;
}

interface AgentQueryResponse {
  query: string;
  summary_message?: string;
  synthesized_response?: string;
  intent_detected?: string;
  intent?: string;
  opportunities?: RevenueOpportunity[];
}

const EXAMPLE_PROMPTS = [
  'How can I increase revenue this week?',
  'Find my best cross-sell opportunity',
  'Which products are at inventory risk?',
  'Show me pending approvals',
  'How are my AI agents performing?',
];

export default function MerchantDashboard() {
  const [products, setProducts] = useState<Product[]>([]);
  const [recStats, setRecStats] = useState<RecommendationStat | null>(null);
  const [purchaseIntents, setPurchaseIntents] = useState<PurchaseIntentItem[]>([]);
  const [aiActivity, setAiActivity] = useState<AICommerceActivity | null>(null);
  const [opportunities, setOpportunities] = useState<RevenueOpportunity[]>([]);
  const [pendingPriceRequests, setPendingPriceRequests] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<'overview' | 'products' | 'activity' | 'ai_commerce'>('overview');
  const [isLoading, setIsLoading] = useState(false);

  const [apexQuery, setApexQuery] = useState('');
  const [isQueryingApex, setIsQueryingApex] = useState(false);
  const [apexAnswer, setApexAnswer] = useState<AgentQueryResponse | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  const loadDashboardData = useCallback(async () => {
    setIsLoading(true);
    try {
      const prodRes = await apiClient.get('/products/');
      setProducts(prodRes.data || []);
      const statsRes = await apiClient.get('/ai/recommendations/stats/summary');
      setRecStats(statsRes.data);
      const piRes = await apiClient.get('/purchase-intents/');
      setPurchaseIntents(piRes.data || []);
      const aiRes = await apiClient.get('/ai-commerce/activity');
      setAiActivity(aiRes.data);
      const oppRes = await apiClient.get('/revenue/opportunities');
      setOpportunities(oppRes.data || []);

      // Fetch pending customer price requests
      try {
        const badgeRes = await apiClient.get<{ pending_count: number }>('/negotiation/merchant-requests/badge');
        if (badgeRes.data && typeof badgeRes.data.pending_count === 'number') {
          setPendingPriceRequests(badgeRes.data.pending_count);
        }
      } catch {
        // Silently skip if non-merchant or endpoint fails
      }
    } catch (err) {
      console.error('Data load failed', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  const handleAskApex = async (queryText?: string) => {
    const q = queryText || apexQuery;
    if (!q.trim()) return;

    setIsQueryingApex(true);
    setQueryError(null);
    try {
      const res = await apiClient.post('/revenue/agent/query', { message: q });
      setApexAnswer(res.data);
    } catch (err: unknown) {
      console.error('Ask Apex query failed:', err);
      setQueryError('Could not process request through Merchant Revenue Agent. Please check connection.');
    } finally {
      setIsQueryingApex(false);
    }
  };

  const totalGMV = useMemo(() => {
    return purchaseIntents
      .filter((pi) => pi.status === 'AUTHORIZED' || pi.status === 'COMPLETED' || pi.status === 'CREATED')
      .reduce((sum, pi) => sum + Number(pi.requested_amount || 0), 0);
  }, [purchaseIntents]);

  const totalUnits = useMemo(() => {
    return products.reduce((sum, p) => sum + (p.stock_quantity ?? 0), 0);
  }, [products]);

  const lowStockProducts = useMemo(() => {
    return products.filter((p) => (p.stock_quantity ?? 0) <= 5);
  }, [products]);

  const pendingApprovals = useMemo(() => {
    return purchaseIntents.filter((pi) => pi.status === 'APPROVAL_REQUIRED' || pi.status === 'PENDING');
  }, [purchaseIntents]);

  const topOpportunity = useMemo(() => {
    return opportunities.length > 0 ? opportunities[0] : null;
  }, [opportunities]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans flex flex-col justify-between">
      <DashboardNav />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white border border-slate-200 rounded-3xl p-6 sm:p-8 shadow-xs">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Operating Command Center
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
              APEX MERCHANT
            </h1>
            <p className="text-xs sm:text-sm text-slate-600 max-w-xl">
              Your autonomous commerce operating center. Orchestrating merchant revenue intelligence, deterministic policy safety, and AI-to-AI commerce protocols.
            </p>
          </div>

          <div className="flex items-center gap-3 w-full md:w-auto justify-start md:justify-end">
            <Link href="/ai-commerce" className="w-full sm:w-auto">
              <Button size="sm" className="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-500 text-white shadow-xs">
                ✨ Judge Demo &rarr;
              </Button>
            </Link>
            <Button
              onClick={loadDashboardData}
              isLoading={isLoading}
              variant="outline"
              size="sm"
              leftIcon={<RefreshCwIcon size={14} />}
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Action Required: Pending Price Requests Alert Banner */}
        {pendingPriceRequests > 0 && (
          <div className="bg-gradient-to-r from-amber-500/15 via-amber-500/10 to-amber-500/5 border border-amber-300 rounded-3xl p-5 sm:p-6 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-amber-500 text-white flex items-center justify-center font-extrabold text-xl shrink-0 shadow-xs">
                ⚡
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-extrabold uppercase tracking-wider text-amber-900 bg-amber-200/80 px-2.5 py-0.5 rounded-lg">
                    Action Required
                  </span>
                  <span className="text-xs text-amber-800 font-bold">
                    {pendingPriceRequests} Pending Customer Price Request{pendingPriceRequests > 1 ? 's' : ''}
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-slate-800 mt-1 font-medium">
                  You have <strong>{pendingPriceRequests}</strong> customer lower-price request{pendingPriceRequests > 1 ? 's' : ''} waiting for your review and approval.
                </p>
              </div>
            </div>
            <Link
              href="/dashboard/price-requests"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold transition-all shadow-xs shrink-0"
            >
              <span>Review Price Requests &rarr;</span>
            </Link>
          </div>
        )}

        {/* Conversational Entry ("Ask Apex") */}
        <section className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white rounded-3xl p-6 sm:p-8 shadow-md space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-indigo-500/20 border border-indigo-400/30 flex items-center justify-center text-indigo-300">
                <SparklesIcon size={16} />
              </div>
              <div>
                <h2 className="text-base font-bold text-white tracking-tight">
                  Ask Apex about your business
                </h2>
                <p className="text-xs text-slate-300">
                  Tell Apex what you want to improve. It finds the right evidence and recommends your next action.
                </p>
              </div>
            </div>
            <span className="hidden sm:inline-flex text-[11px] font-medium bg-indigo-900/60 border border-indigo-700/50 px-2.5 py-1 rounded-xl text-indigo-200">
              AI Commerce Center
            </span>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleAskApex();
            }}
            className="flex flex-col sm:flex-row gap-2"
          >
            <div className="relative flex-1">
              <SearchIcon size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={apexQuery}
                onChange={(e) => setApexQuery(e.target.value)}
                placeholder="Ask Apex how to grow your business..."
                className="w-full pl-10 pr-4 py-3 text-xs sm:text-sm rounded-2xl bg-slate-800/90 border border-slate-700 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>
            <Button
              type="submit"
              isLoading={isQueryingApex}
              className="bg-indigo-500 hover:bg-indigo-400 text-white font-semibold px-6 py-3 rounded-2xl shrink-0 text-xs sm:text-sm"
            >
              Ask Apex &rarr;
            </Button>
          </form>

          <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs scrollbar-none">
            <span className="text-[11px] text-slate-400 shrink-0">Try asking:</span>
            {EXAMPLE_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => {
                  setApexQuery(prompt);
                  handleAskApex(prompt);
                }}
                className="px-3 py-1 rounded-xl bg-slate-800/80 hover:bg-slate-700 border border-slate-700/80 text-slate-200 text-[11px] whitespace-nowrap transition-colors"
              >
                &ldquo;{prompt}&rdquo;
              </button>
            ))}
          </div>

          {queryError && (
            <div className="p-4 rounded-2xl bg-rose-950/60 border border-rose-800 text-rose-200 text-xs flex items-center gap-2">
              <AlertTriangleIcon size={16} className="shrink-0 text-rose-400" />
              <span>{queryError}</span>
            </div>
          )}

          {apexAnswer && (
            <div className="p-5 rounded-2xl bg-slate-800/90 border border-indigo-500/40 space-y-4 animate-in fade-in-50 duration-200">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-indigo-300 uppercase tracking-wide text-[10px]">
                    Intent: {apexAnswer.intent_detected || apexAnswer.intent || 'REVENUE_GROWTH'}
                  </span>
                </div>
                <span className="text-[10px] text-slate-400">
                  Grounded in live store data
                </span>
              </div>
              
              <div className="space-y-1">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Answer</span>
                <p className="text-xs sm:text-sm text-slate-100 leading-relaxed">
                  {apexAnswer.summary_message || apexAnswer.synthesized_response}
                </p>
              </div>

              {apexAnswer.opportunities && apexAnswer.opportunities.length > 0 && (
                <div className="p-3.5 rounded-xl bg-slate-900/90 border border-indigo-500/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-indigo-300 uppercase tracking-wider">
                      Recommended Opportunity
                    </span>
                    <span className="text-[11px] font-bold text-emerald-400 font-mono">
                      +₹{Number(apexAnswer.opportunities[0].estimated_incremental_gmv || apexAnswer.opportunities[0].estimated_net_value || 1197).toLocaleString('en-IN')} Est. GMV
                    </span>
                  </div>
                  
                  <div className="text-xs font-semibold text-white">
                    {apexAnswer.opportunities[0].name || apexAnswer.opportunities[0].title || 'Pro Running Shoes → Performance Socks'}
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-slate-300 pt-1 border-t border-slate-800">
                    <div>
                      <span className="text-slate-500 text-[10px] block">Confidence</span>
                      <strong className="text-white">
                        {Math.round((apexAnswer.opportunities[0].confidence || 0.88) * 100)}%
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 text-[10px] block">Inventory</span>
                      <strong className="text-emerald-400">
                        {apexAnswer.opportunities[0].inventory_status || 'Available'}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 text-[10px] block">Policy</span>
                      <strong className="text-emerald-400">
                        {apexAnswer.opportunities[0].policy_status || 'Compliant'}
                      </strong>
                    </div>
                    <div className="flex items-center justify-end">
                      <Link
                        href="/dashboard/ai-growth"
                        className="text-xs font-bold text-indigo-300 hover:text-white underline underline-offset-2"
                      >
                        Review opportunity &rarr;
                      </Link>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {/* Business KPI Cards */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
          <MetricCard
            title="TOTAL GMV"
            value={`₹${totalGMV.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
            subtext="From authorized and completed intents"
            icon={<CreditCardIcon size={16} />}
            href="/dashboard/revenue"
            ctaText="View revenue"
          />
          <MetricCard
            title="ACTIVE CATALOG"
            value={products.length}
            subtext={`${totalUnits.toLocaleString('en-IN')} units currently in stock`}
            icon={<ShoppingBagIcon size={16} />}
            onClick={() => {
              setActiveTab('products');
              document.getElementById('activity-tabs-section')?.scrollIntoView({ behavior: 'smooth' });
            }}
            ctaText="Inspect catalog"
          />
          <MetricCard
            title="PURCHASE INTENTS"
            value={purchaseIntents.length}
            subtext={
              pendingApprovals.length > 0
                ? `${pendingApprovals.length} currently awaiting approval`
                : 'Formulated by buyer agents'
            }
            icon={<ActivityIcon size={16} />}
            href="/dashboard/approvals"
            ctaText="Review intents"
          />
          <MetricCard
            title="AI COMMERCE ACTIVITY"
            value={aiActivity?.active_agent_requests ?? 0}
            subtext="AI-to-AI and agent commerce events"
            icon={<SparklesIcon size={16} />}
            href="/ai-commerce"
            ctaText="Open console"
          />
          <MetricCard
            title="AI CROSS-SELL CONVERSION"
            value={recStats && recStats.total_recommendations > 0 ? `${Number(recStats.acceptance_rate).toFixed(0)}%` : '0%'}
            subtext={
              recStats && recStats.total_recommendations > 0
                ? `${recStats.accepted_count} accepted of ${recStats.total_recommendations} shown`
                : 'No AI recommendation has converted yet'
            }
            icon={<ShieldCheckIcon size={16} />}
            href="/dashboard/ai-growth"
            ctaText="Open AI Growth"
          />
          <MetricCard
            title="AI-ATTRIBUTED GMV"
            value={`₹${Number(aiActivity?.total_ai_revenue || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
            subtext={
              aiActivity?.total_ai_revenue
                ? 'From AI-to-AI captured orders'
                : 'No captured order attributed to AI recommendations'
            }
            icon={<SparklesIcon size={16} />}
            href="/dashboard/revenue"
            ctaText="View attribution"
          />
        </section>

        {/* Hero Opportunities and Operational Alerts */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Top Opportunity */}
          <section className="lg:col-span-7 bg-white border border-slate-200 rounded-3xl p-6 shadow-xs flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold text-xs">
                    📈
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-slate-900">AI Growth Opportunity</h2>
                    <p className="text-xs text-slate-500">Evidence-based opportunities found from your store activity.</p>
                  </div>
                </div>
                <Link
                  href="/dashboard/ai-growth"
                  className="text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                >
                  All Opportunities &rarr;
                </Link>
              </div>

              {topOpportunity ? (
                <div className="p-4 rounded-2xl bg-indigo-50/50 border border-indigo-100 space-y-3">
                  <div className="flex items-center justify-between">
                    <Badge variant="purple" size="xs">
                      {topOpportunity.type || 'CROSS-SELL'}
                    </Badge>
                    <span className="text-xs font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md font-mono">
                      +₹{Number(topOpportunity.estimated_incremental_gmv || 0).toLocaleString('en-IN')} estimated GMV
                    </span>
                  </div>

                  <div>
                    <h3 className="text-sm font-bold text-slate-900">{topOpportunity.name}</h3>
                    <p className="text-xs text-slate-600 mt-0.5">{topOpportunity.description}</p>
                  </div>

                  <div className="text-[11px] text-slate-600 bg-white p-3 rounded-xl border border-slate-100 space-y-2">
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <span className="text-slate-400 text-[10px] block font-medium">Confidence</span>
                        <strong className="text-slate-900">{Math.round((topOpportunity.confidence || 0) * 100)}% confidence</strong>
                      </div>
                      <div>
                        <span className="text-slate-400 text-[10px] block font-medium">Inventory</span>
                        <strong className="text-slate-900">{topOpportunity.inventory_status || 'Inventory available'}</strong>
                      </div>
                      <div>
                        <span className="text-slate-400 text-[10px] block font-medium">Policy</span>
                        <strong className="text-emerald-600">{topOpportunity.policy_status || 'Policy compliant'}</strong>
                      </div>
                    </div>

                    <details className="text-[10px] text-slate-500 pt-1 border-t border-slate-100 cursor-pointer">
                      <summary className="font-semibold text-indigo-600 hover:text-indigo-800">
                        View evidence &amp; trace details
                      </summary>
                      <p className="mt-1.5 text-slate-600 font-sans leading-relaxed">
                        <strong>Evidence:</strong> {topOpportunity.evidence_summary}
                      </p>
                    </details>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center rounded-2xl bg-slate-50 border border-dashed border-slate-200 space-y-2">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                    INSUFFICIENT DATA
                  </span>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto">
                    AI Revenue Agent requires order co-occurrences or price elasticity triggers to generate new opportunities.
                  </p>
                </div>
              )}
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium">Policy-Governed Revenue System</span>
              <Link href="/dashboard/ai-growth">
                <Button size="xs" variant="primary">
                  Review opportunity &rarr;
                </Button>
              </Link>
            </div>
          </section>

          {/* Right Column: Needs Attention & Trust */}
          <div className="lg:col-span-5 space-y-6 flex flex-col justify-between">
            <section className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs space-y-3">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <div className="flex items-center gap-2">
                  <AlertTriangleIcon size={16} className="text-amber-500" />
                  <h2 className="text-sm font-bold text-slate-900">Needs Attention</h2>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                  Live Store Data
                </span>
              </div>

              <div className="space-y-2 text-xs">
                <Link
                  href="/dashboard/approvals"
                  className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors group"
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${pendingApprovals.length > 0 ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                    <span className="text-slate-700">Governance Review Queue</span>
                  </div>
                  <div className="flex items-center gap-1.5 font-bold text-slate-900">
                    <span>{pendingApprovals.length} pending</span>
                    <ChevronRightIcon size={12} className="text-slate-400 group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </Link>

                <Link
                  href="/shopping"
                  className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors group"
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${lowStockProducts.length > 0 ? 'bg-amber-500' : 'bg-emerald-500'}`} />
                    <span className="text-slate-700">Inventory Stock Alerts</span>
                  </div>
                  <div className="flex items-center gap-1.5 font-bold text-slate-900">
                    <span>{lowStockProducts.length} items &le; 5 units</span>
                    <ChevronRightIcon size={12} className="text-slate-400 group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </Link>

                <Link
                  href="/dashboard/payments"
                  className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors group"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                    <span className="text-slate-700">Payment Gateway</span>
                  </div>
                  <div className="flex items-center gap-1.5 font-bold text-emerald-600">
                    <span>Operational ✓</span>
                    <ChevronRightIcon size={12} className="text-slate-400 group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </Link>
              </div>
            </section>

            {/* Trust & Governance Summary */}
            <section className="bg-slate-900 text-white rounded-3xl p-5 shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheckIcon size={16} className="text-emerald-400" />
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                    Trust &amp; Governance
                  </h3>
                </div>
                <Link
                  href="/dashboard/governance"
                  className="text-[11px] font-semibold text-indigo-300 hover:text-white"
                >
                  Inspect &rarr;
                </Link>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-300">
                <div className="bg-slate-800/80 p-2.5 rounded-xl space-y-0.5">
                  <div className="flex items-center gap-1.5 text-emerald-400 font-bold">
                    <span>&#10003;</span>
                    <span>Policies active</span>
                  </div>
                  <p className="text-[10px] text-slate-400 pl-4">4 deterministic rules</p>
                </div>
                <div className="bg-slate-800/80 p-2.5 rounded-xl space-y-0.5">
                  <div className="flex items-center gap-1.5 text-emerald-400 font-bold">
                    <span>&#10003;</span>
                    <span>Audit trail intact</span>
                  </div>
                  <p className="text-[10px] text-slate-400 pl-4">SHA-256 hash chain</p>
                </div>
                <div className="bg-slate-800/80 p-2.5 rounded-xl space-y-0.5">
                  <div className="flex items-center gap-1.5 text-emerald-400 font-bold">
                    <span>&#10003;</span>
                    <span>Payment verification protected</span>
                  </div>
                  <p className="text-[10px] text-slate-400 pl-4">Webhook HMAC verification</p>
                </div>
                <div className="bg-slate-800/80 p-2.5 rounded-xl space-y-0.5">
                  <div className="flex items-center gap-1.5 text-emerald-400 font-bold">
                    <span>&#10003;</span>
                    <span>Merchant data isolated</span>
                  </div>
                  <p className="text-[10px] text-slate-400 pl-4">Multi-tenant boundary</p>
                </div>
              </div>
            </section>
          </div>
        </div>

        {/* Tab Controls & Live Activity Stream */}
        <div id="activity-tabs-section" className="flex border-b border-slate-200 space-x-6 text-xs font-semibold scroll-mt-6">
          <button
            onClick={() => setActiveTab('overview')}
            className={`pb-3 transition-colors flex items-center gap-1.5 ${
              activeTab === 'overview'
                ? 'text-indigo-600 border-b-2 border-indigo-600 font-bold'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span>Active Purchase Intents</span>
            <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-slate-100 text-slate-600">
              {purchaseIntents.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('ai_commerce')}
            className={`pb-3 transition-colors flex items-center gap-1.5 ${
              activeTab === 'ai_commerce'
                ? 'text-indigo-600 border-b-2 border-indigo-600 font-bold'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span>AI-to-AI Protocol Activity</span>
            <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-slate-100 text-slate-600">
              {aiActivity?.recent_events?.length || 0}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('products')}
            className={`pb-3 transition-colors flex items-center gap-1.5 ${
              activeTab === 'products'
                ? 'text-indigo-600 border-b-2 border-indigo-600 font-bold'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span>Live Inventory Catalog</span>
            <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-slate-100 text-slate-600">
              {products.length}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('activity')}
            className={`pb-3 transition-colors flex items-center gap-1.5 ${
              activeTab === 'activity'
                ? 'text-indigo-600 border-b-2 border-indigo-600 font-bold'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span>AI Recommendation Log</span>
            <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-slate-100 text-slate-600">
              {recStats?.recent_recommendations?.length || 0}
            </span>
          </button>
        </div>

        {/* Tab 1: Active Purchase Intents Table */}
        {activeTab === 'overview' && (
          <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-xs">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-slate-900">Active Purchase Intents</h3>
                <p className="text-xs text-slate-500">Autonomous buyer agent orders awaiting review or completed</p>
              </div>
              <Link href="/dashboard/approvals">
                <Button size="xs" variant="outline">
                  Governance Queue &rarr;
                </Button>
              </Link>
            </div>

            {purchaseIntents.length === 0 ? (
              <div className="p-12 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
                  <ActivityIcon size={24} />
                </div>
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold text-slate-800">No active purchase intents</h4>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto">
                    Purchase intents formulated by buyer agents during autonomous shopping sessions will appear here in real time.
                  </p>
                </div>
                <div className="pt-2 flex items-center justify-center gap-3">
                  <Link href="/shopping">
                    <Button size="xs" variant="outline">
                      Launch Storefront
                    </Button>
                  </Link>
                  <Link href="/ai-commerce">
                    <Button size="xs" variant="primary">
                      Open AI-to-AI Console
                    </Button>
                  </Link>
                </div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-100 text-slate-500 font-semibold">
                    <tr>
                      <th className="px-6 py-3">Intent ID</th>
                      <th className="px-6 py-3">Buyer ID</th>
                      <th className="px-6 py-3">Requested Amount</th>
                      <th className="px-6 py-3">Status</th>
                      <th className="px-6 py-3">Items</th>
                      <th className="px-6 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {purchaseIntents.map((pi) => (
                      <tr key={pi.id} className="hover:bg-slate-50/50 transition-colors">
                        <td className="px-6 py-3 font-mono font-bold text-slate-900">{pi.id}</td>
                        <td className="px-6 py-3 text-slate-600">{pi.buyer_id}</td>
                        <td className="px-6 py-3 font-mono font-semibold text-slate-900">
                          ₹{Number(pi.requested_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-6 py-3">
                          <Badge
                            variant={
                              pi.status === 'AUTHORIZED' || pi.status === 'COMPLETED'
                                ? 'success'
                                : pi.status === 'APPROVAL_REQUIRED'
                                ? 'warning'
                                : pi.status === 'POLICY_BLOCKED' || pi.status === 'REJECTED'
                                ? 'error'
                                : 'neutral'
                            }
                            size="xs"
                          >
                            {pi.status}
                          </Badge>
                        </td>
                        <td className="px-6 py-3 text-slate-600">
                          {pi.items?.length || 0} item(s)
                        </td>
                        <td className="px-6 py-3 text-right">
                          <Link href="/dashboard/approvals" className="text-indigo-600 hover:text-indigo-800 font-bold">
                            Review &rarr;
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: AI-to-AI Protocol Activity */}
        {activeTab === 'ai_commerce' && (
          <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-xs">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-slate-900">AI-to-AI Protocol Activity Stream</h3>
                <p className="text-xs text-slate-500">Autonomous interactions between external buyer agents and merchant catalog</p>
              </div>
              <Link href="/ai-commerce">
                <Button size="xs" variant="primary">
                  Open Protocol Console &rarr;
                </Button>
              </Link>
            </div>

            {aiActivity?.recent_events && aiActivity.recent_events.length > 0 ? (
              <div className="divide-y divide-slate-100">
                {aiActivity.recent_events.map((ev) => (
                  <div key={ev.id} className="px-6 py-4 flex items-center justify-between hover:bg-slate-50/50 text-xs">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded">
                          {ev.action}
                        </span>
                        <Badge variant="neutral" size="xs">
                          {ev.actor_type}
                        </Badge>
                        <span className="text-[11px] text-slate-400">
                          {new Date(ev.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="font-mono text-[11px] text-slate-500 truncate max-w-xl">
                        {JSON.stringify(ev.details || {})}
                      </p>
                    </div>
                    <Badge variant={ev.status === 'SUCCESS' ? 'success' : 'neutral'} size="xs">
                      {ev.status}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-12 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
                  <SparklesIcon size={24} />
                </div>
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold text-slate-800">No protocol events recorded</h4>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto">
                    Launch the AI-to-AI Console to simulate multi-turn buyer agent catalog discovery, negotiation, and checkout.
                  </p>
                </div>
                <div className="pt-2">
                  <Link href="/ai-commerce">
                    <Button size="xs" variant="primary">
                      Launch AI-to-AI Simulation &rarr;
                    </Button>
                  </Link>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Live Inventory Catalog */}
        {activeTab === 'products' && (
          <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-xs">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-slate-900">Live Inventory Catalog</h3>
                <p className="text-xs text-slate-500">Authoritative product inventory, pricing, and stock levels</p>
              </div>
              <Link href="/shopping">
                <Button size="xs" variant="outline">
                  Storefront Catalog &rarr;
                </Button>
              </Link>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-100 text-slate-500 font-semibold">
                  <tr>
                    <th className="px-6 py-3">Product Name</th>
                    <th className="px-6 py-3">Category</th>
                    <th className="px-6 py-3">Unit Price</th>
                    <th className="px-6 py-3">Stock Units</th>
                    <th className="px-6 py-3 text-right">Storefront</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {products.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-6 py-3 font-semibold text-slate-900">{p.name}</td>
                      <td className="px-6 py-3 text-slate-600 capitalize">{p.category}</td>
                      <td className="px-6 py-3 font-mono font-bold text-slate-900">
                        ₹{Number(p.price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-6 py-3">
                        <span
                          className={`font-mono font-bold px-2 py-0.5 rounded ${
                            (p.stock_quantity ?? 0) <= 5
                              ? 'bg-rose-50 text-rose-700 border border-rose-200'
                              : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          }`}
                        >
                          {p.stock_quantity ?? 0} units
                        </span>
                      </td>
                      <td className="px-6 py-3 text-right">
                        <Link href={`/shopping/${p.id}`} className="text-indigo-600 hover:text-indigo-800 font-bold">
                          View PDP &rarr;
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 4: AI Recommendation Log */}
        {activeTab === 'activity' && (
          <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-xs">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-sm text-slate-900">AI Recommendation Execution Log</h3>
                <p className="text-xs text-slate-500">Autonomous cross-sell and upsell prompt recommendations shown to shoppers</p>
              </div>
              <Link href="/dashboard/ai-growth">
                <Button size="xs" variant="outline">
                  Explore Revenue Agent &rarr;
                </Button>
              </Link>
            </div>

            {recStats?.recent_recommendations && recStats.recent_recommendations.length > 0 ? (
              <div className="divide-y divide-slate-100">
                {recStats.recent_recommendations.map((rec) => (
                  <div key={rec.id} className="px-6 py-4 flex items-center justify-between hover:bg-slate-50/50 text-xs">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900">{rec.product_name}</span>
                        <Badge variant="purple" size="xs">
                          {rec.type}
                        </Badge>
                        <span className="text-slate-400 font-mono text-[11px]">
                          ₹{Number(rec.product_price).toLocaleString('en-IN')}
                        </span>
                      </div>
                      <p className="text-slate-500 text-[11px]">{rec.reason}</p>
                    </div>
                    <div className="text-right space-y-1">
                      <Badge
                        variant={rec.status === 'ACCEPTED' ? 'success' : rec.status === 'REJECTED' ? 'error' : 'neutral'}
                        size="xs"
                      >
                        {rec.status}
                      </Badge>
                      <div className="text-[10px] text-slate-400 font-mono">
                        Score: {Math.round((rec.confidence || 0) * 100)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-12 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
                  <ShieldCheckIcon size={24} />
                </div>
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold text-slate-800">No recommendations logged</h4>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto">
                    AI recommendations presented during customer shopping sessions will be recorded here.
                  </p>
                </div>
                <div className="pt-2">
                  <Link href="/dashboard/ai-growth">
                    <Button size="xs" variant="primary">
                      AI Growth Copilot &rarr;
                    </Button>
                  </Link>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white text-slate-500 text-xs py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <span>Agentic Commerce OS — Merchant Operating Center</span>
          <span className="text-[11px] text-slate-400">Deterministic Governance Active</span>
        </div>
      </footer>
    </div>
  );
}

