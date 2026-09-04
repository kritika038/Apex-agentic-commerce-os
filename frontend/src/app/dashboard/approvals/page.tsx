'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient, extractErrorMessage } from '@/lib/api';
import { DashboardNav } from '@/components/dashboard/DashboardNav';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

interface ApprovalItem {
  id: string;
  purchase_intent_id: string;
  policy_evaluation_id: string;
  amount: string;
  currency: string;
  risk_level: string;
  status: string;
  reason: string;
  approved_by_user_id?: string;
  expires_at?: string;
  created_at?: string;
}

interface NegotiatedOfferItem {
  id: string;
  tenant_id: string;
  customer_id: string;
  product_id: string;
  original_unit_price: number | string;
  offered_unit_price: number | string;
  quantity: number;
  discount_percent: number | string;
  status: string;
  decision_reason?: string;
  negotiated_by?: string;
  counter_unit_price?: number | string | null;
  expires_at?: string;
  created_at?: string;
}

export default function ApprovalsPage() {
  const [activeSection, setActiveSection] = useState<'transactions' | 'negotiations'>('transactions');

  // Transaction Approvals State
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [filter, setFilter] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [alert, setAlert] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Negotiation Approvals State
  const [negotiations, setNegotiations] = useState<NegotiatedOfferItem[]>([]);
  const [negotiationFilter, setNegotiationFilter] = useState('ALL');
  const [counterModalOffer, setCounterModalOffer] = useState<NegotiatedOfferItem | null>(null);
  const [counterPrice, setCounterPrice] = useState<number | string>('');
  const [counterReason, setCounterReason] = useState('Merchant counter-offer based on margin constraints.');

  const fetchApprovals = useCallback(async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/approvals');
      setApprovals(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchNegotiations = useCallback(async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/negotiation/merchant/list');
      setNegotiations(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeSection === 'transactions') {
      fetchApprovals();
    } else {
      fetchNegotiations();
    }
  }, [activeSection, fetchApprovals, fetchNegotiations]);

  const handleAction = async (id: string, action: 'approve' | 'reject') => {
    setActionLoading(id);
    setAlert(null);
    try {
      const res = await apiClient.post(`/approvals/${id}/${action}`, {
        reason: 'Action performed by merchant operator via Approval Center.',
      });

      if (res.status === 200 || res.status === 201) {
        if (action === 'approve') {
          setAlert({
            type: 'success',
            message: `✓ Request ${id.slice(0, 8)} APPROVED! Authorization generated with valid window. Note: No payment execution has occurred.`,
          });
        } else {
          setAlert({
            type: 'success',
            message: `✗ Request ${id.slice(0, 8)} REJECTED. Linked Purchase Intent marked as REJECTED.`,
          });
        }
        fetchApprovals();
      } else {
        setAlert({ type: 'error', message: 'Action rejected by policy or unauthorized.' });
      }
    } catch (err: unknown) {
      setAlert({ type: 'error', message: extractErrorMessage(err, 'Failed to submit approval action.') });
    } finally {
      setActionLoading(null);
    }
  };

  // Negotiation Merchant Actions
  const handleNegotiationApprove = async (id: string) => {
    setActionLoading(id);
    setAlert(null);
    try {
      await apiClient.post(`/negotiation/${id}/merchant/approve`, {
        reason: 'Approved by merchant operator in Human-in-the-Loop review.',
      });
      setAlert({
        type: 'success',
        message: `✓ Offer ${id.slice(0, 8)} APPROVED! Customer can now proceed to authoritative checkout.`,
      });
      fetchNegotiations();
    } catch (err: unknown) {
      setAlert({ type: 'error', message: extractErrorMessage(err, 'Failed to approve negotiation offer.') });
    } finally {
      setActionLoading(null);
    }
  };

  const handleNegotiationReject = async (id: string) => {
    setActionLoading(id);
    setAlert(null);
    try {
      await apiClient.post(`/negotiation/${id}/merchant/reject`, {
        reason: 'Requested discount exceeds maximum allowable margin by merchant.',
      });
      setAlert({
        type: 'success',
        message: `✗ Offer ${id.slice(0, 8)} REJECTED.`,
      });
      fetchNegotiations();
    } catch (err: unknown) {
      setAlert({ type: 'error', message: extractErrorMessage(err, 'Failed to reject negotiation offer.') });
    } finally {
      setActionLoading(null);
    }
  };

  const handleNegotiationCounter = async () => {
    if (!counterModalOffer) return;
    const priceNum = Number(counterPrice);
    if (!priceNum || priceNum <= 0) {
      setAlert({ type: 'error', message: 'Please enter a valid counter-offer price.' });
      return;
    }
    setActionLoading(counterModalOffer.id);
    setAlert(null);
    try {
      await apiClient.post(`/negotiation/${counterModalOffer.id}/merchant/counter`, {
        counter_unit_price: priceNum,
        reason: counterReason || 'Merchant counter-offer.',
      });
      setAlert({
        type: 'success',
        message: `✓ Counter-offer of ₹${priceNum.toLocaleString('en-IN')} submitted for offer ${counterModalOffer.id.slice(0, 8)}.`,
      });
      setCounterModalOffer(null);
      fetchNegotiations();
    } catch (err: unknown) {
      setAlert({ type: 'error', message: extractErrorMessage(err, 'Failed to send counter-offer.') });
    } finally {
      setActionLoading(null);
    }
  };

  const filteredApprovals = approvals.filter((a) => {
    if (filter === 'ALL') return true;
    return a.status === filter;
  });

  const filteredNegotiations = negotiations.filter((n) => {
    if (negotiationFilter === 'ALL') return true;
    return n.status === negotiationFilter;
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col justify-between">
      <DashboardNav />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        {/* Navigation / Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-6 border-b border-slate-800">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-bold text-white">
                Human-in-the-Loop Approval Center
              </h1>
              <span className="px-2.5 py-0.5 bg-indigo-950 border border-indigo-700/60 text-indigo-300 text-[10px] font-mono font-semibold rounded-full">
                Phase 4 Gateway
              </span>
            </div>
            <p className="text-slate-400 text-xs sm:text-sm mt-1">
              Deterministic Governance Review &amp; Buyer-Merchant Negotiation Queue.
            </p>
          </div>
          <Button
            onClick={activeSection === 'transactions' ? fetchApprovals : fetchNegotiations}
            variant="secondary"
            size="sm"
          >
            ↻ Refresh Queue
          </Button>
        </div>

        {/* Section Tabs */}
        <div className="flex border-b border-slate-800 gap-6 text-sm font-semibold">
          <button
            onClick={() => setActiveSection('transactions')}
            className={`pb-3 relative transition flex items-center gap-2 ${
              activeSection === 'transactions'
                ? 'text-indigo-400 border-b-2 border-indigo-500'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>Transaction Approvals</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] bg-slate-800 text-slate-300">
              {approvals.length}
            </span>
          </button>
          <button
            onClick={() => setActiveSection('negotiations')}
            className={`pb-3 relative transition flex items-center gap-2 ${
              activeSection === 'negotiations'
                ? 'text-indigo-400 border-b-2 border-indigo-500'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>Price Negotiations</span>
            <span className="px-2 py-0.5 rounded-full text-[10px] bg-indigo-950 text-indigo-300 border border-indigo-800/50">
              {negotiations.length}
            </span>
            {negotiations.some((n) => n.status === 'HUMAN_APPROVAL_REQUIRED') && (
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            )}
          </button>
        </div>

        {/* Alert Notification */}
        {alert && (
          <div
            className={`p-4 rounded-xl text-xs font-mono border ${
              alert.type === 'success'
                ? 'bg-emerald-950/80 border-emerald-700 text-emerald-300'
                : 'bg-rose-950/80 border-rose-700 text-rose-300'
            }`}
          >
            {alert.message}
          </div>
        )}

        {/* SECTION 1: TRANSACTION APPROVALS */}
        {activeSection === 'transactions' && (
          <div className="space-y-6">
            {/* Filters */}
            <div className="flex gap-2">
              {['ALL', 'PENDING', 'APPROVED', 'REJECTED'].map((st) => (
                <button
                  key={st}
                  onClick={() => setFilter(st)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                    filter === st
                      ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                      : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                  }`}
                >
                  {st} ({st === 'ALL' ? approvals.length : approvals.filter((a) => a.status === st).length})
                </button>
              ))}
            </div>

            {/* Approvals Table */}
            <div className="rounded-2xl bg-slate-900/90 border border-slate-800 overflow-hidden shadow-lg">
              {loading ? (
                <div className="p-12 text-center text-xs text-slate-400">Loading approval records...</div>
              ) : filteredApprovals.length === 0 ? (
                <div className="p-12 text-center text-xs text-slate-400">
                  No approval requests matching filter &quot;{filter}&quot;.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950/70 border-b border-slate-800 text-[11px] text-slate-400 uppercase font-semibold">
                      <tr>
                        <th className="py-3 px-4">Approval ID</th>
                        <th className="py-3 px-4">Purchase Intent</th>
                        <th className="py-3 px-4">Requested Amount</th>
                        <th className="py-3 px-4">Risk Level</th>
                        <th className="py-3 px-4">Reason / Rule</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/80">
                      {filteredApprovals.map((a) => (
                        <tr key={a.id} className="hover:bg-slate-850/40 transition-colors">
                          <td className="py-3 px-4 font-mono text-[11px] text-indigo-300">
                            {a.id.slice(0, 10)}...
                          </td>
                          <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                            {a.purchase_intent_id.slice(0, 10)}...
                          </td>
                          <td className="py-3 px-4 font-bold text-white">
                            ₹{Number(a.amount).toLocaleString('en-IN')} {a.currency}
                          </td>
                          <td className="py-3 px-4">
                            <Badge
                              variant={
                                a.risk_level === 'HIGH'
                                  ? 'error'
                                  : a.risk_level === 'MEDIUM'
                                  ? 'warning'
                                  : 'success'
                              }
                              size="sm"
                            >
                              {a.risk_level}
                            </Badge>
                          </td>
                          <td className="py-3 px-4 text-slate-300 max-w-xs truncate">{a.reason}</td>
                          <td className="py-3 px-4">
                            <Badge
                              variant={
                                a.status === 'APPROVED'
                                  ? 'success'
                                  : a.status === 'REJECTED'
                                  ? 'error'
                                  : 'warning'
                              }
                              size="sm"
                              dot={a.status === 'PENDING'}
                            >
                              {a.status}
                            </Badge>
                          </td>
                          <td className="py-3 px-4">
                            {a.status === 'PENDING' ? (
                              <div className="flex gap-2">
                                <button
                                  onClick={() => handleAction(a.id, 'approve')}
                                  disabled={actionLoading === a.id}
                                  className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[11px] font-bold transition disabled:opacity-50"
                                >
                                  Approve
                                </button>
                                <button
                                  onClick={() => handleAction(a.id, 'reject')}
                                  disabled={actionLoading === a.id}
                                  className="px-2.5 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded text-[11px] font-bold transition disabled:opacity-50"
                                >
                                  Reject
                                </button>
                              </div>
                            ) : (
                              <span className="text-[11px] text-slate-500 font-mono">Completed</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* SECTION 2: PRICE NEGOTIATIONS */}
        {activeSection === 'negotiations' && (
          <div className="space-y-6">
            {/* Filters */}
            <div className="flex flex-wrap gap-2">
              {['ALL', 'HUMAN_APPROVAL_REQUIRED', 'AUTO_ACCEPTED', 'MERCHANT_APPROVED', 'COUNTER_OFFERED', 'MERCHANT_REJECTED', 'CUSTOMER_ACCEPTED'].map((st) => (
                <button
                  key={st}
                  onClick={() => setNegotiationFilter(st)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                    negotiationFilter === st
                      ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                      : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                  }`}
                >
                  {st.replace(/_/g, ' ')} ({st === 'ALL' ? negotiations.length : negotiations.filter((n) => n.status === st).length})
                </button>
              ))}
            </div>

            {/* Negotiations Table */}
            <div className="rounded-2xl bg-slate-900/90 border border-slate-800 overflow-hidden shadow-lg">
              {loading ? (
                <div className="p-12 text-center text-xs text-slate-400">Loading negotiation records...</div>
              ) : filteredNegotiations.length === 0 ? (
                <div className="p-12 text-center text-xs text-slate-400">
                  No negotiation requests matching filter &quot;{negotiationFilter}&quot;.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950/70 border-b border-slate-800 text-[11px] text-slate-400 uppercase font-semibold">
                      <tr>
                        <th className="py-3 px-4">Offer ID</th>
                        <th className="py-3 px-4">Customer</th>
                        <th className="py-3 px-4">Original Unit</th>
                        <th className="py-3 px-4">Requested Unit</th>
                        <th className="py-3 px-4">Qty &amp; Discount</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Decision Reason</th>
                        <th className="py-3 px-4">Merchant Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/80">
                      {filteredNegotiations.map((n) => (
                        <tr key={n.id} className="hover:bg-slate-850/40 transition-colors">
                          <td className="py-3 px-4 font-mono text-[11px] text-indigo-300">
                            {n.id.slice(0, 8)}...
                          </td>
                          <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                            {n.customer_id.slice(0, 10)}
                          </td>
                          <td className="py-3 px-4 font-medium text-slate-300">
                            ₹{Number(n.original_unit_price).toLocaleString('en-IN')}
                          </td>
                          <td className="py-3 px-4 font-bold text-white">
                            ₹{Number(n.offered_unit_price).toLocaleString('en-IN')}
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex flex-col">
                              <span className="font-semibold text-white">{n.quantity} unit{n.quantity > 1 ? 's' : ''}</span>
                              <span className="text-[10px] text-amber-400 font-mono">
                                {Number(n.discount_percent).toFixed(1)}% off
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <Badge
                              variant={
                                n.status === 'AUTO_ACCEPTED' || n.status === 'MERCHANT_APPROVED' || n.status === 'CUSTOMER_ACCEPTED'
                                  ? 'success'
                                  : n.status === 'MERCHANT_REJECTED' || n.status === 'CUSTOMER_REJECTED' || n.status === 'EXPIRED'
                                  ? 'error'
                                  : 'warning'
                              }
                              size="sm"
                              dot={n.status === 'HUMAN_APPROVAL_REQUIRED'}
                            >
                              {n.status.replace(/_/g, ' ')}
                            </Badge>
                          </td>
                          <td className="py-3 px-4 text-slate-300 max-w-xs truncate text-[11px]">
                            {n.decision_reason || '—'}
                          </td>
                          <td className="py-3 px-4">
                            {n.status === 'HUMAN_APPROVAL_REQUIRED' ? (
                              <div className="flex gap-2">
                                <button
                                  onClick={() => handleNegotiationApprove(n.id)}
                                  disabled={actionLoading === n.id}
                                  className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[11px] font-bold transition disabled:opacity-50"
                                >
                                  Approve
                                </button>
                                <button
                                  onClick={() => {
                                    setCounterModalOffer(n);
                                    setCounterPrice(Math.round(Number(n.original_unit_price) * 0.95));
                                  }}
                                  disabled={actionLoading === n.id}
                                  className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-[11px] font-bold transition disabled:opacity-50"
                                >
                                  Counter
                                </button>
                                <button
                                  onClick={() => handleNegotiationReject(n.id)}
                                  disabled={actionLoading === n.id}
                                  className="px-2.5 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded text-[11px] font-bold transition disabled:opacity-50"
                                >
                                  Reject
                                </button>
                              </div>
                            ) : n.status === 'COUNTER_OFFERED' || n.status === 'MERCHANT_COUNTERED' ? (
                              <span className="text-[11px] text-cyan-400 font-mono">
                                Counter: ₹{Number(n.counter_unit_price || 0).toLocaleString('en-IN')}
                              </span>
                            ) : (
                              <span className="text-[11px] text-slate-500 font-mono">Completed</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Counter Offer Modal */}
        {counterModalOffer && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
              <div className="flex justify-between items-center pb-2 border-b border-slate-800">
                <h3 className="text-base font-bold text-white">Merchant Counter-Offer</h3>
                <button
                  onClick={() => setCounterModalOffer(null)}
                  className="text-slate-400 hover:text-white text-xs font-bold"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 space-y-1">
                  <div className="flex justify-between text-slate-400">
                    <span>Original Unit Price:</span>
                    <span className="text-white font-bold">
                      ₹{Number(counterModalOffer.original_unit_price).toLocaleString('en-IN')}
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Customer Requested:</span>
                    <span className="text-amber-400 font-bold">
                      ₹{Number(counterModalOffer.offered_unit_price).toLocaleString('en-IN')}
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Quantity:</span>
                    <span className="text-white">{counterModalOffer.quantity}</span>
                  </div>
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">
                    Your Counter-Offer Unit Price (₹ INR):
                  </label>
                  <input
                    type="number"
                    value={counterPrice}
                    onChange={(e) => setCounterPrice(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white font-bold focus:outline-none focus:border-indigo-500 text-sm"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-medium mb-1">Counter Rationale / Note:</label>
                  <textarea
                    value={counterReason}
                    onChange={(e) => setCounterReason(e.target.value)}
                    rows={2}
                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <Button
                  onClick={() => setCounterModalOffer(null)}
                  variant="outline"
                  size="sm"
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleNegotiationCounter}
                  disabled={actionLoading === counterModalOffer.id}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-4 py-2"
                >
                  {actionLoading === counterModalOffer.id ? 'Submitting...' : 'Send Counter Offer'} &rarr;
                </Button>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="border-t border-slate-900 bg-slate-950 text-slate-500 text-xs py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <span>Agentic Commerce OS — Approval Center</span>
          <span className="text-[11px] text-slate-600">Deterministic Governance Layer Active</span>
        </div>
      </footer>
    </div>
  );
}

