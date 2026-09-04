'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  ShieldCheckIcon,
  RefreshCwIcon,
} from '@/components/ui/Icons';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Toast, ToastProps } from '@/components/ui/Toast';
import { apiClient, extractErrorMessage } from '@/lib/api';

interface PolicyRule {
  id: string;
  name: string;
  type: string;
  threshold: string;
  status: string;
  description: string;
}

interface ApprovalRequestItem {
  id: string;
  purchase_intent_id: string;
  amount: number;
  reason: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'EXPIRED';
  created_at: string;
  details?: Record<string, unknown>;
}

export default function GovernanceDashboardPage() {
  const [loading, setLoading] = useState(true);
  const [approvals, setApprovals] = useState<ApprovalRequestItem[]>([]);
  const [toast, setToast] = useState<ToastProps | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);

  const POLICY_RULES: PolicyRule[] = [
    {
      id: 'pol_1',
      name: 'Autonomous Agent Spend Cap',
      type: 'THRESHOLD',
      threshold: '₹5,000.00',
      status: 'ENFORCED',
      description: 'Transactions exceeding ₹5,000 require explicit human 2FA/approval.',
    },
    {
      id: 'pol_2',
      name: 'Maximum Transaction Ceiling',
      type: 'HARD_LIMIT',
      threshold: '₹10,000.00',
      status: 'ENFORCED',
      description: 'Transactions above ₹10,000 are rejected immediately with POLICY_BLOCKED.',
    },
    {
      id: 'pol_3',
      name: 'Basket Quantity Limit',
      type: 'QUANTITY_GUARD',
      threshold: '5 Items Max',
      status: 'ENFORCED',
      description: 'Orders with >5 items are rejected to prevent automated inventory scalping.',
    },
    {
      id: 'pol_4',
      name: 'Price & Inventory Authority',
      type: 'DETERMINISTIC_LOCK',
      threshold: 'SQL Database Only',
      status: 'ENFORCED',
      description: 'Zero LLM price modification authority. Immutable server price snapshots.',
    },
  ];

  const fetchApprovals = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get('/approvals');
      setApprovals(res.data || []);
    } catch {
      // Fallback empty list
      setApprovals([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, []);

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type, onClose: () => setToast(null) });
  };

  const handleApprove = async (id: string) => {
    try {
      setActionLoadingId(id);
      await apiClient.post(`/approvals/${id}/approve`, {
        reason: 'Authorized via Merchant Governance Console',
      });
      showToast('Transaction approved. Authorization snapshot created.', 'success');
      fetchApprovals();
    } catch (err) {
      showToast(extractErrorMessage(err, 'Failed to approve request.'), 'error');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleReject = async (id: string) => {
    try {
      setActionLoadingId(id);
      await apiClient.post(`/approvals/${id}/reject`, {
        reason: 'Declined by Merchant Admin',
      });
      showToast('Transaction rejected. Buyer notified.', 'info');
      fetchApprovals();
    } catch (err) {
      showToast(extractErrorMessage(err, 'Failed to reject request.'), 'error');
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      {/* Toast Notification */}
      {toast && <Toast {...toast} onClose={() => setToast(null)} />}

      {/* Header */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/dashboard" className="text-slate-500 hover:text-slate-900 text-sm font-medium">
              ← Merchant Console
            </Link>
            <span className="text-slate-300">/</span>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-600 animate-pulse" />
              <h1 className="font-extrabold text-base text-slate-900 tracking-tight">
                Governance Control Center
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/dashboard/audit"
              className="text-xs font-semibold px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
            >
              Audit Ledger →
            </Link>
            <Button
              onClick={fetchApprovals}
              variant="outline"
              size="sm"
              leftIcon={<RefreshCwIcon size={14} className={loading ? 'animate-spin' : ''} />}
            >
              Refresh
            </Button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 flex-1 w-full">
        {/* Governance Operations Sub-Hub */}
        <section className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { label: 'Policies', href: '/dashboard/policies', icon: '⚖️', desc: 'Safety rules & thresholds' },
            { label: 'Approvals', href: '/dashboard/approvals', icon: '✍️', desc: 'Human-in-the-loop review' },
            { label: 'Audit', href: '/dashboard/audit', icon: '🔗', desc: 'SHA-256 chained ledger' },
            { label: 'Monitoring', href: '/dashboard/observability', icon: '📊', desc: 'Agent step execution traces' },
            { label: 'Security Lab', href: '/dashboard/security-lab', icon: '🛡️', desc: 'Red-team injection testing' },
            { label: 'Controls', href: '/dashboard/control-plane', icon: '⚙️', desc: 'Firewall & settlement locks' },
          ].map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className="bg-white border border-slate-200 hover:border-indigo-300 hover:shadow-xs rounded-2xl p-4 transition-all group flex flex-col justify-between"
            >
              <div className="space-y-1">
                <div className="text-xl mb-1">{item.icon}</div>
                <h3 className="font-bold text-xs text-slate-900 group-hover:text-indigo-600 transition-colors">
                  {item.label}
                </h3>
                <p className="text-[10px] text-slate-500 leading-tight">
                  {item.desc}
                </p>
              </div>
              <span className="text-[10px] font-bold text-indigo-600 mt-2 flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform">
                Open &rarr;
              </span>
            </Link>
          ))}
        </section>

        {/* State Machine Legend */}
        <section className="bg-white border border-slate-200 rounded-3xl p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
              <ShieldCheckIcon size={18} className="text-indigo-600" />
              <span>Deterministic State Separation Architecture</span>
            </div>
            <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
              Zero State Ambiguity
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 text-xs">
            <div className="p-3 rounded-2xl bg-amber-50 border border-amber-200 space-y-1">
              <span className="font-bold text-amber-900 block">APPROVAL_REQUIRED</span>
              <p className="text-amber-700 text-[11px] leading-tight">
                Spend &gt;₹5,000. Pauses execution for explicit human OTP or merchant approval.
              </p>
            </div>

            <div className="p-3 rounded-2xl bg-rose-50 border border-rose-200 space-y-1">
              <span className="font-bold text-rose-900 block">POLICY_BLOCKED</span>
              <p className="text-rose-700 text-[11px] leading-tight">
                Spend &gt;₹10,000 or quantity &gt;5. Deterministically rejected by rules engine.
              </p>
            </div>

            <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200 space-y-1">
              <span className="font-bold text-slate-900 block">PAYMENT_PENDING</span>
              <p className="text-slate-600 text-[11px] leading-tight">
                Razorpay checkout opened. Awaiting gateway authorization callback.
              </p>
            </div>

            <div className="p-3 rounded-2xl bg-indigo-50 border border-indigo-200 space-y-1">
              <span className="font-bold text-indigo-900 block">PAYMENT_VERIFIED</span>
              <p className="text-indigo-700 text-[11px] leading-tight">
                Server verified HMAC-SHA256 signature using RAZORPAY_KEY_SECRET.
              </p>
            </div>

            <div className="p-3 rounded-2xl bg-emerald-50 border border-emerald-200 space-y-1">
              <span className="font-bold text-emerald-900 block">ORDER_CONFIRMED</span>
              <p className="text-emerald-700 text-[11px] leading-tight">
                Inventory decremented, rewards credited, and immutable audit event committed.
              </p>
            </div>
          </div>
        </section>

        {/* Active Policy Rules */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">Active Governance Rules</h2>
              <p className="text-xs text-slate-500">Configured safety boundaries for autonomous and conversational commerce</p>
            </div>
            <Badge variant="success" size="sm">
              All 4 Rules Enforced
            </Badge>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {POLICY_RULES.map((rule) => (
              <div
                key={rule.id}
                className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-3 flex flex-col justify-between"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-indigo-600 uppercase tracking-wider">{rule.type}</span>
                    <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                      {rule.status}
                    </span>
                  </div>
                  <h3 className="font-bold text-sm text-slate-900">{rule.name}</h3>
                  <p className="text-xs text-slate-600 leading-relaxed">{rule.description}</p>
                </div>
                <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                  <span className="text-slate-500 font-medium">Limit:</span>
                  <span className="font-extrabold text-slate-900 font-mono">{rule.threshold}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Pending Approval Requests */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">
                Approval Queue ({approvals.filter((a) => a.status === 'PENDING').length} Pending)
              </h2>
              <p className="text-xs text-slate-500">Transactions exceeding autonomous thresholds requiring human authorization</p>
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-xs">
            {approvals.length === 0 ? (
              <div className="p-12 text-center space-y-2">
                <div className="w-12 h-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl mx-auto font-bold">
                  ✓
                </div>
                <h3 className="font-bold text-sm text-slate-900">No Pending Approvals</h3>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  All transactions are within policy boundaries or have already been evaluated.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {approvals.map((item) => (
                  <div key={item.id} className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-900">
                          #{item.id.substring(0, 8)}
                        </span>
                        <Badge
                          variant={
                            item.status === 'PENDING'
                              ? 'warning'
                              : item.status === 'APPROVED'
                              ? 'success'
                              : 'error'
                          }
                          size="xs"
                        >
                          {item.status}
                        </Badge>
                      </div>
                      <p className="text-xs text-slate-700 font-medium">{item.reason}</p>
                      <span className="text-[11px] text-slate-500 block">
                        Amount: <strong className="text-slate-900 font-mono">₹{Number(item.amount).toLocaleString('en-IN')}</strong> • Created {new Date(item.created_at).toLocaleTimeString()}
                      </span>
                    </div>

                    {item.status === 'PENDING' && (
                      <div className="flex items-center gap-2 shrink-0">
                        <Button
                          onClick={() => handleApprove(item.id)}
                          isLoading={actionLoadingId === item.id}
                          variant="primary"
                          size="sm"
                        >
                          Approve
                        </Button>
                        <Button
                          onClick={() => handleReject(item.id)}
                          isLoading={actionLoadingId === item.id}
                          variant="outline"
                          size="sm"
                        >
                          Reject
                        </Button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
