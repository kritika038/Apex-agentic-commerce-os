'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { apiClient } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import {
  SparklesIcon,
  ShieldCheckIcon,
  ShoppingBagIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  ArrowRightIcon,
  LockIcon,
} from '@/components/ui/Icons';

interface AgentProduct {
  product_id: string;
  name: string;
  description: string;
  category: string;
  price: number;
  currency: string;
  availability: string;
  stock_quantity: number;
  purchase_constraints: {
    max_order_quantity: number;
    requires_approval_above: number;
    allowed_currency: string;
  };
}

export default function AgentCommercePage() {
  const [catalog, setCatalog] = useState<AgentProduct[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<AgentProduct | null>(null);
  const [agentId, setAgentId] = useState('external_buyer_agent_alpha');
  const [customerId, setCustomerId] = useState('shopper@example.com');
  const [budgetCap, setBudgetCap] = useState(5000);
  const [permissionMode, setPermissionMode] = useState<'ask_before' | 'autonomous_within_limits' | 'recommendation_only'>('ask_before');
  const [approvalThreshold, setApprovalThreshold] = useState(3000);
  const [allowedCategories, setAllowedCategories] = useState<string[]>(['Running', 'Apparel', 'Accessories']);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiClient.get('/agent/catalog')
      .then((res) => {
        setCatalog(res.data.products || []);
        if (res.data.products?.length > 0) {
          setSelectedProduct(res.data.products[0]);
        }
      })
      .catch((err) => console.error('Failed to load agent catalog:', err));
  }, []);

  const handleExecuteAgentIntent = async () => {
    if (!selectedProduct) return;
    setLoading(true);
    setError(null);
    setResult(null);

    // Enforce client-side permission policy check for preview
    if (permissionMode === 'recommendation_only') {
      setError('Autonomous purchasing is disabled by user policy (Recommendation Only mode).');
      setLoading(false);
      return;
    }

    if (!allowedCategories.includes(selectedProduct.category)) {
      setError(`Category '${selectedProduct.category}' is not in customer allowed categories list (${allowedCategories.join(', ')}).`);
      setLoading(false);
      return;
    }

    try {
      const res = await apiClient.post('/agent-commerce/purchase-intent', {
        agent_id: agentId,
        customer_id: customerId,
        product_id: selectedProduct.product_id,
        quantity: 1,
        max_budget: budgetCap,
        requires_human_approval: selectedProduct.price > approvalThreshold || permissionMode === 'ask_before',
      });
      setResult(res.data);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Agent commerce action was rejected by governance policy.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-lg bg-slate-900 text-white font-bold flex items-center justify-center text-sm">
                A
              </span>
              <span className="font-extrabold text-lg text-slate-900 tracking-tight">
                Apex Sports <span className="text-indigo-600 font-medium text-xs ml-1">AI Protocol</span>
              </span>
            </Link>
            <nav className="hidden md:flex items-center gap-4 text-xs font-semibold text-slate-600">
              <Link href="/shopping" className="hover:text-slate-900">Storefront</Link>
              <Link href="/demo" className="hover:text-slate-900">Interactive Demo</Link>
              <Link href="/dashboard" className="hover:text-slate-900">Merchant Dashboard</Link>
            </nav>
          </div>

          <Badge variant="neutral" className="gap-1.5 font-mono text-[11px]">
            <ShieldCheckIcon size={12} className="text-emerald-600" />
            Machine-Readable AI Protocol v1.0
          </Badge>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        {/* Banner */}
        <div className="rounded-2xl bg-white border border-slate-200 p-6 sm:p-8 shadow-xs">
          <div className="max-w-3xl space-y-2">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-700 text-xs font-semibold">
              <SparklesIcon size={13} />
              <span>Phase 8 & 9 — Autonomous AI-to-AI Commerce</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
              AI-to-AI Commerce & Customer Permission Policies
            </h1>
            <p className="text-sm text-slate-600 leading-relaxed">
              External autonomous AI agents can read the Apex Sports catalog in real-time and request purchase intents.
              Every action is strictly bounded by customer-defined permission policies and deterministic server-side governance.
            </p>
          </div>
        </div>

        {/* 3-Column Layout: Customer Permission Config, Catalog Discovery, Agent Execution */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Col 1: Customer AI Purchase Permissions */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5 shadow-xs">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h2 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                <LockIcon size={16} className="text-indigo-600" />
                Customer Purchase Permissions
              </h2>
              <Badge variant="info" size="sm">Governed</Badge>
            </div>

            <div className="space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-bold text-slate-700">Autonomous Purchase Mode</label>
                <div className="space-y-2">
                  <label className="flex items-start gap-2 p-2.5 rounded-lg border border-slate-200 cursor-pointer hover:bg-slate-50">
                    <input
                      type="radio"
                      name="perm_mode"
                      value="ask_before"
                      checked={permissionMode === 'ask_before'}
                      onChange={() => setPermissionMode('ask_before')}
                      className="mt-0.5"
                    />
                    <div>
                      <div className="font-semibold text-slate-900">Ask Before Purchase (Default)</div>
                      <div className="text-[11px] text-slate-500">Agent creates intent; requires customer/human authorization.</div>
                    </div>
                  </label>

                  <label className="flex items-start gap-2 p-2.5 rounded-lg border border-slate-200 cursor-pointer hover:bg-slate-50">
                    <input
                      type="radio"
                      name="perm_mode"
                      value="autonomous_within_limits"
                      checked={permissionMode === 'autonomous_within_limits'}
                      onChange={() => setPermissionMode('autonomous_within_limits')}
                      className="mt-0.5"
                    />
                    <div>
                      <div className="font-semibold text-slate-900">Autonomous Within Limits</div>
                      <div className="text-[11px] text-slate-500">Auto-approved if amount is below threshold and within category.</div>
                    </div>
                  </label>

                  <label className="flex items-start gap-2 p-2.5 rounded-lg border border-slate-200 cursor-pointer hover:bg-slate-50">
                    <input
                      type="radio"
                      name="perm_mode"
                      value="recommendation_only"
                      checked={permissionMode === 'recommendation_only'}
                      onChange={() => setPermissionMode('recommendation_only')}
                      className="mt-0.5"
                    />
                    <div>
                      <div className="font-semibold text-slate-900">Recommendation Only</div>
                      <div className="text-[11px] text-slate-500">Agent cannot execute orders under any circumstances.</div>
                    </div>
                  </label>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700">Maximum Budget Cap</label>
                <input
                  type="number"
                  value={budgetCap}
                  onChange={(e) => setBudgetCap(Number(e.target.value))}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-slate-900 font-mono text-xs focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700">Approval Required Above</label>
                <input
                  type="number"
                  value={approvalThreshold}
                  onChange={(e) => setApprovalThreshold(Number(e.target.value))}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-slate-900 font-mono text-xs focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700">Allowed Categories</label>
                <div className="flex flex-wrap gap-2">
                  {['Running', 'Apparel', 'Accessories', 'Bags', 'Electronics'].map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => {
                        if (allowedCategories.includes(cat)) {
                          setAllowedCategories(allowedCategories.filter((c) => c !== cat));
                        } else {
                          setAllowedCategories([...allowedCategories, cat]);
                        }
                      }}
                      className={`px-2.5 py-1 rounded-full text-[11px] font-semibold transition-colors ${
                        allowedCategories.includes(cat)
                          ? 'bg-slate-900 text-white'
                          : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Col 2: Machine-Readable Catalog API */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5 shadow-xs">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h2 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                <ShoppingBagIcon size={16} className="text-emerald-600" />
                GET /api/v1/agent-commerce/catalog
              </h2>
              <Badge variant="success" size="sm">{catalog.length} Products</Badge>
            </div>

            <div className="space-y-3">
              <p className="text-xs text-slate-500">
                Select a product from the authoritative real-time catalog:
              </p>

              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {catalog.map((p) => (
                  <div
                    key={p.product_id}
                    onClick={() => setSelectedProduct(p)}
                    className={`p-3 rounded-xl border text-left cursor-pointer transition-all ${
                      selectedProduct?.product_id === p.product_id
                        ? 'border-indigo-600 bg-indigo-50/50 shadow-xs ring-1 ring-indigo-500'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs text-slate-900">{p.name}</span>
                      <span className="font-bold text-xs text-indigo-700">₹{p.price.toLocaleString('en-IN')}</span>
                    </div>
                    <div className="flex items-center justify-between mt-1 text-[11px] text-slate-500">
                      <span>Category: {p.category}</span>
                      <span className="text-emerald-600 font-medium">In Stock ({p.stock_quantity})</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Col 3: Agent Purchase Intent Executor */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5 shadow-xs">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h2 className="font-bold text-sm text-slate-900 flex items-center gap-2">
                <ShieldCheckIcon size={16} className="text-indigo-600" />
                POST /purchase-intent
              </h2>
              <Badge variant="neutral" size="sm">Governed</Badge>
            </div>

            <div className="space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-bold text-slate-700">Agent Identifier</label>
                <input
                  type="text"
                  value={agentId}
                  onChange={(e) => setAgentId(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-slate-900 font-mono text-xs focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-slate-700">Customer Identifier</label>
                <input
                  type="text"
                  value={customerId}
                  onChange={(e) => setCustomerId(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-slate-900 font-mono text-xs focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {selectedProduct && (
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1.5">
                  <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Payload Summary</div>
                  <div className="flex justify-between font-medium">
                    <span className="text-slate-600">Product:</span>
                    <span className="text-slate-900 font-bold">{selectedProduct.name}</span>
                  </div>
                  <div className="flex justify-between font-medium">
                    <span className="text-slate-600">Authoritative Price:</span>
                    <span className="text-indigo-700 font-bold">₹{selectedProduct.price.toLocaleString('en-IN')}</span>
                  </div>
                  <div className="flex justify-between font-medium">
                    <span className="text-slate-600">Budget Limit:</span>
                    <span className="text-slate-900 font-mono">₹{budgetCap.toLocaleString('en-IN')}</span>
                  </div>
                </div>
              )}

              <Button
                variant="primary"
                size="md"
                onClick={handleExecuteAgentIntent}
                isLoading={loading}
                className="w-full font-bold"
                rightIcon={<ArrowRightIcon size={14} />}
              >
                Execute Agent Intent →
              </Button>

              {/* Error Display */}
              {error && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2">
                  <AlertTriangleIcon size={16} className="text-rose-600 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-bold">Governance Check Rejected</div>
                    <div>{error}</div>
                  </div>
                </div>
              )}

              {/* Success Result Display */}
              {result && (
                <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs space-y-1.5">
                  <div className="flex items-center gap-1.5 font-bold text-emerald-800">
                    <CheckCircleIcon size={15} />
                    <span>Purchase Intent Created Successfully</span>
                  </div>
                  <div className="font-mono text-[11px] text-emerald-700">
                    ID: {String(result.purchase_intent_id)}
                  </div>
                  <div className="text-[11px] text-emerald-800">
                    Policy Decision: <strong>{String(result.policy_evaluation_status)}</strong>
                  </div>
                  <div className="text-[11px] text-emerald-800">
                    Requires Human Approval: <strong>{result.requires_human_approval ? 'Yes (Review Required)' : 'No (Auto-Authorized)'}</strong>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Phase 12: AI vs Deterministic Boundary Visual Card */}
        <section className="bg-slate-900 text-white rounded-2xl p-8 space-y-6">
          <div className="text-center max-w-2xl mx-auto space-y-1">
            <span className="text-xs font-bold uppercase tracking-widest text-indigo-400">Core Architecture</span>
            <h2 className="text-xl sm:text-2xl font-black">AI Intelligence + Deterministic Commerce Control</h2>
            <p className="text-xs text-slate-400">AI proposes. The commerce engine decides.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
            <div className="p-5 rounded-xl bg-slate-800/80 border border-slate-700 space-y-3">
              <div className="flex items-center gap-2 font-bold text-indigo-400 text-sm">
                <SparklesIcon size={16} />
                <span>AI Agent Layer (Discovery & Recommendation)</span>
              </div>
              <ul className="space-y-1.5 text-xs text-slate-300">
                <li className="flex items-center gap-2">✓ Natural language & voice understanding (English & Hindi)</li>
                <li className="flex items-center gap-2">✓ Autonomous catalog discovery & search</li>
                <li className="flex items-center gap-2">✓ Conversational context & comparative recommendations</li>
                <li className="flex items-center gap-2">✓ Proposes upsell & cross-sell suggestions</li>
              </ul>
            </div>

            <div className="p-5 rounded-xl bg-slate-800/80 border border-slate-700 space-y-3">
              <div className="flex items-center gap-2 font-bold text-emerald-400 text-sm">
                <ShieldCheckIcon size={16} />
                <span>Deterministic Commerce Engine (Authority & Settlement)</span>
              </div>
              <ul className="space-y-1.5 text-xs text-slate-300">
                <li className="flex items-center gap-2">✓ Server-authoritative product prices & inventory</li>
                <li className="flex items-center gap-2">✓ Coupon, voucher & Apex Coin calculations</li>
                <li className="flex items-center gap-2">✓ Razorpay test-mode order generation & HMAC verification</li>
                <li className="flex items-center gap-2">✓ Immutable audit ledger & zero-overdraft protection</li>
              </ul>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
