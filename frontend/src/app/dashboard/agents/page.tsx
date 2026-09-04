"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { API_BASE_URL } from '@/lib/api';
import { DashboardNav } from '@/components/dashboard/DashboardNav';

const API_BASE = API_BASE_URL;

interface Agent {
  id: string;
  name: string;
  type: string;
  version: string;
  model: string;
  status: string;
  permissions: string[];
}

const ALL_SYSTEM_PERMISSIONS = [
  { key: "READ_PRODUCTS", label: "Search & Read Catalog", category: "catalog" },
  { key: "READ_INVENTORY", label: "Check Stock Levels", category: "inventory" },
  { key: "CREATE_CART", label: "Initialize Cart", category: "cart" },
  { key: "READ_CART", label: "Inspect Cart Items", category: "cart" },
  { key: "MODIFY_CART", label: "Add/Remove Cart Items", category: "cart" },
  { key: "CALCULATE_CART", label: "Calculate Cart Subtotals", category: "cart" },
  { key: "RECOMMEND_PRODUCT", label: "Propose Found Products", category: "commerce" },
  { key: "CREATE_RECOMMENDATION", label: "Contextual Upsell/Cross-sell", category: "commerce" },
  { key: "CREATE_PAYMENT_ORDER", label: "Create Payment Order (Phase 5)", category: "payment" },
  { key: "READ_PAYMENT_STATUS", label: "Read Settlement Status", category: "payment" },
  { key: "MANAGE_POLICY", label: "Mutate Financial Policies", category: "security" }
];

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchAgents() {
      try {
        setLoading(true);
        const res = await fetch(`${API_BASE}/agents`);
        if (res.ok) {
          const data = await res.json();
          setAgents(data);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    fetchAgents();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col justify-between">
      <DashboardNav />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        {/* Navigation Bar */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-6 border-b border-slate-800">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white">
              Agent Permissions & Least Privilege Matrix
            </h1>
            <p className="text-slate-400 text-xs sm:text-sm mt-1">
              Database-backed permission scopes enforced at the Tool Registry and Policy Engine layers.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              href="/dashboard/policies"
              className="px-3.5 py-2 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition"
            >
              Policy Rules →
            </Link>
          </div>
        </div>

        {/* Security Matrix Overview Banner */}
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 flex items-start gap-4">
          <div className="text-2xl">🛡️</div>
          <div className="space-y-1 text-sm text-slate-300">
            <h3 className="font-semibold text-slate-100">Deterministic Least Privilege Principle</h3>
            <p className="text-slate-400">
              Autonomous agents can never grant themselves permissions, modify merchant financial policies, or execute payment charges without human authorization.
            </p>
          </div>
        </div>

        {/* Permissions Table Matrix */}
        {loading ? (
          <div className="p-12 text-center text-slate-500">Loading agent permissions...</div>
        ) : (
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-950/60 text-slate-400 text-xs">
                    <th className="p-4 font-semibold">Permission Capability</th>
                    <th className="p-4 font-semibold">Category</th>
                    {agents.map((ag) => (
                      <th key={ag.id} className="p-4 font-semibold text-center">
                        <div className="font-bold text-slate-200">{ag.name}</div>
                        <div className="text-[10px] text-slate-500 font-mono">{ag.model} (v{ag.version})</div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {ALL_SYSTEM_PERMISSIONS.map((perm) => (
                    <tr key={perm.key} className="hover:bg-slate-800/30 transition">
                      <td className="p-4">
                        <div className="font-medium text-slate-200">{perm.label}</div>
                        <div className="text-[11px] font-mono text-slate-500">{perm.key}</div>
                      </td>
                      <td className="p-4 text-xs">
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px] uppercase font-mono">
                          {perm.category}
                        </span>
                      </td>
                      {agents.map((ag) => {
                        const hasPerm = ag.permissions.includes(perm.key);
                        return (
                          <td key={ag.id} className="p-4 text-center">
                            {hasPerm ? (
                              <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-emerald-950/80 border border-emerald-700/80 text-emerald-400 text-sm font-bold shadow-sm shadow-emerald-900/40">
                                ✓
                              </span>
                            ) : (
                              <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-red-950/40 border border-red-900/40 text-red-500/70 text-xs">
                                ✗
                              </span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
      <footer className="border-t border-slate-900 bg-slate-950 text-slate-500 text-xs py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <span>Agentic Commerce OS — Agent Permissions Matrix</span>
          <span className="text-[11px] text-slate-600">Least Privilege Enforced</span>
        </div>
      </footer>
    </div>
  );
}
