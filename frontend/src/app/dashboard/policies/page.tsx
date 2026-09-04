"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { API_BASE_URL } from '@/lib/api';
import { DashboardNav } from '@/components/dashboard/DashboardNav';

const API_BASE = API_BASE_URL;

interface Policy {
  id: string;
  name: string;
  version: number;
  max_transaction_amount: string;
  approval_threshold: string;
  low_risk_limit: string;
  max_discount_percent: string;
  max_quantity: number;
  allowed_currency: string;
  auto_approval_enabled: boolean;
  authorization_expiration_minutes: number;
  is_active: boolean;
  created_at: string;
}

export default function PoliciesPage() {
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [history, setHistory] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  // Form state
  const [name, setName] = useState("");
  const [maxAmount, setMaxAmount] = useState("10000.00");
  const [approvalThreshold, setApprovalThreshold] = useState("5000.00");
  const [lowRiskLimit, setLowRiskLimit] = useState("2000.00");
  const [maxDiscount, setMaxDiscount] = useState("5.00");
  const [maxQuantity, setMaxQuantity] = useState(5);
  const [currency, setCurrency] = useState("INR");
  const [autoApproval, setAutoApproval] = useState(true);
  const [authExpiration, setAuthExpiration] = useState(10);

  const fetchPolicy = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/policies`);
      if (res.ok) {
        const data: Policy = await res.json();
        setPolicy(data);
        setName(data.name);
        setMaxAmount(String(data.max_transaction_amount));
        setApprovalThreshold(String(data.approval_threshold));
        setLowRiskLimit(String(data.low_risk_limit));
        setMaxDiscount(String(data.max_discount_percent));
        setMaxQuantity(data.max_quantity);
        setCurrency(data.allowed_currency);
        setAutoApproval(data.auto_approval_enabled);
        setAuthExpiration(data.authorization_expiration_minutes);
      }
      
      const resHist = await fetch(`${API_BASE}/policies/history`);
      if (resHist.ok) {
        const histData = await resHist.json();
        setHistory(histData);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicy();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSuccessMsg("");
    setErrorMsg("");

    try {
      // First get a login token for admin to authenticate policy update
      const loginRes = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          username: "admin@demo-sports.test",
          password: "password123"
        })
      });
      const loginData = await loginRes.json();
      const token = loginData.access_token;

      let res;
      if (policy) {
        res = await fetch(`${API_BASE}/policies/${policy.id}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            name,
            max_transaction_amount: parseFloat(maxAmount),
            approval_threshold: parseFloat(approvalThreshold),
            low_risk_limit: parseFloat(lowRiskLimit),
            max_discount_percent: parseFloat(maxDiscount),
            max_quantity: Number(maxQuantity),
            allowed_currency: currency,
            auto_approval_enabled: autoApproval,
            authorization_expiration_minutes: Number(authExpiration)
          })
        });
      } else {
        res = await fetch(`${API_BASE}/policies`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            name,
            max_transaction_amount: parseFloat(maxAmount),
            approval_threshold: parseFloat(approvalThreshold),
            low_risk_limit: parseFloat(lowRiskLimit),
            max_discount_percent: parseFloat(maxDiscount),
            max_quantity: Number(maxQuantity),
            allowed_currency: currency,
            auto_approval_enabled: autoApproval,
            authorization_expiration_minutes: Number(authExpiration)
          })
        });
      }

      if (res.ok) {
        const saved = await res.json();
        setPolicy(saved);
        setSuccessMsg(`Policy updated successfully! Activated Version ${saved.version}. Historical evaluations remain bound to previous snapshots.`);
        fetchPolicy();
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || "Failed to update policy.");
      }
    } catch (err: unknown) {
      const e = err as { message?: string };
      setErrorMsg(e?.message || "Network error updating policy.");
    } finally {
      setSaving(false);
    }
  };

  if (loading && !policy) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
        <div className="text-slate-400">Loading policy configuration...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col justify-between">
      <DashboardNav />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        {/* Navigation Bar */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-6 border-b border-slate-800">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-bold text-white">
                Financial Policy Controls
              </h1>
              {policy && (
                <span className="px-2.5 py-0.5 bg-indigo-900/60 border border-indigo-700/50 text-indigo-300 text-[10px] font-mono font-semibold rounded-full">
                  Active: v{policy.version}
                </span>
              )}
            </div>
            <p className="text-slate-400 text-xs sm:text-sm mt-1">
              Deterministic authorization layer rules. Governs all AI Buyer & Sales Agent transactions.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              href="/dashboard/approvals"
              className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition"
            >
              Approval Queue →
            </Link>
          </div>
        </div>

        {/* Safety Warning Banner */}
        <div className="bg-amber-950/40 border border-amber-800/60 rounded-xl p-4 flex gap-4 items-start">
          <div className="text-2xl">⚠️</div>
          <div className="text-sm text-amber-200 space-y-1">
            <p className="font-semibold">Financial Safety Governance Notice</p>
            <p className="text-amber-300/80">
              Saving changes will generate an immutable new policy version. Existing historical evaluations are permanently locked to their respective evaluation snapshots and will never be overwritten.
            </p>
          </div>
        </div>

        {successMsg && (
          <div className="p-4 bg-emerald-950/60 border border-emerald-800 rounded-xl text-emerald-300 text-sm">
            ✓ {successMsg}
          </div>
        )}
        {errorMsg && (
          <div className="p-4 bg-red-950/60 border border-red-800 rounded-xl text-red-300 text-sm">
            ✗ {errorMsg}
          </div>
        )}

        {/* Policy Configuration Form */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <form onSubmit={handleSave} className="lg:col-span-2 bg-slate-900/90 border border-slate-800 rounded-2xl p-6 space-y-6">
            <h2 className="text-xl font-semibold text-slate-200 flex items-center gap-2">
              <span>⚙️</span> Policy Configuration
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Policy Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Allowed Currency</label>
                <input
                  type="text"
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500"
                  maxLength={3}
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Max Transaction Limit (₹)
                  <span className="text-slate-500 text-[10px] ml-1">Hard Cap</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={maxAmount}
                  onChange={(e) => setMaxAmount(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                  required
                />
                <p className="text-[11px] text-slate-500 mt-1">Transactions exceeding this will be DENIED.</p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Human Approval Threshold (₹)
                  <span className="text-amber-400/80 text-[10px] ml-1">Review Trigger</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={approvalThreshold}
                  onChange={(e) => setApprovalThreshold(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                  required
                />
                <p className="text-[11px] text-slate-500 mt-1">Requires merchant signoff if cart exceeds this.</p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Low-Risk Limit (₹)
                  <span className="text-emerald-400/80 text-[10px] ml-1">Low Band</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={lowRiskLimit}
                  onChange={(e) => setLowRiskLimit(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Max Item Quantity</label>
                <input
                  type="number"
                  value={maxQuantity}
                  onChange={(e) => setMaxQuantity(parseInt(e.target.value) || 1)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                  min={1}
                  max={100}
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Max Discount (%)</label>
                <input
                  type="number"
                  step="0.01"
                  value={maxDiscount}
                  onChange={(e) => setMaxDiscount(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Authorization Expiration (Mins)</label>
                <input
                  type="number"
                  value={authExpiration}
                  onChange={(e) => setAuthExpiration(parseInt(e.target.value) || 10)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 font-mono"
                  min={1}
                  max={1440}
                  required
                />
              </div>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <input
                type="checkbox"
                id="autoApprove"
                checked={autoApproval}
                onChange={(e) => setAutoApproval(e.target.checked)}
                className="rounded border-slate-800 bg-slate-950 text-indigo-600 focus:ring-indigo-500"
              />
              <label htmlFor="autoApprove" className="text-xs text-slate-300">
                Enable automatic approval for low-risk transactions below threshold
              </label>
            </div>

            <div className="pt-4 border-t border-slate-800 flex justify-end">
              <button
                type="submit"
                disabled={saving}
                className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold shadow-lg shadow-indigo-600/30 transition disabled:opacity-50"
              >
                {saving ? "Saving Policy..." : "Publish New Policy Version"}
              </button>
            </div>
          </form>

          {/* Policy Version History */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 space-y-4">
            <h3 className="text-lg font-semibold text-slate-200">Version History</h3>
            <p className="text-xs text-slate-400">
              Audit log of immutable policy versions deployed for this merchant.
            </p>

            <div className="space-y-3 max-h-[450px] overflow-y-auto pr-1">
              {history.map((h) => (
                <div
                  key={h.id}
                  className={`p-3.5 rounded-xl border text-xs space-y-1.5 transition ${
                    h.is_active
                      ? "bg-indigo-950/40 border-indigo-700/60 text-slate-200"
                      : "bg-slate-950/60 border-slate-800/80 text-slate-400"
                  }`}
                >
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-slate-200">Version {h.version}</span>
                    {h.is_active ? (
                      <span className="px-2 py-0.5 bg-emerald-900/60 border border-emerald-700 text-emerald-300 rounded text-[10px]">
                        ACTIVE
                      </span>
                    ) : (
                      <span className="text-slate-500 text-[10px]">Archived</span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-1 text-[11px] font-mono pt-1">
                    <div>Cap: ₹{parseFloat(h.max_transaction_amount).toLocaleString("en-IN")}</div>
                    <div>Review: ₹{parseFloat(h.approval_threshold).toLocaleString("en-IN")}</div>
                    <div>Qty: {h.max_quantity} items</div>
                    <div>Exp: {h.authorization_expiration_minutes}m</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
      <footer className="border-t border-slate-900 bg-slate-950 text-slate-500 text-xs py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <span>Agentic Commerce OS — Financial Policy Engine</span>
          <span className="text-[11px] text-slate-600">Deterministic Evaluation Active</span>
        </div>
      </footer>
    </div>
  );
}
