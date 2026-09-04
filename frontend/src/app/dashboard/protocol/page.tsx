'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { apiClient } from '@/lib/api';
import { DashboardNav } from '@/components/dashboard/DashboardNav';

interface ProtocolCapabilities {
  protocol_version: string;
  merchant_id: string;
  merchant_name: string;
  supported_currency: string;
  operations: string[];
  capabilities: Record<string, boolean>;
  security_guarantees: Record<string, string>;
}

export default function ProtocolExplorerPage() {
  const [capabilities, setCapabilities] = useState<ProtocolCapabilities | null>(null);
  const [activeTab, setActiveTab] = useState<'discover' | 'recommend' | 'intent' | 'auth' | 'pay'>('discover');
  const [loading, setLoading] = useState<boolean>(false);
  const [requestPayload, setRequestPayload] = useState<string>('');
  const [responseStatus, setResponseStatus] = useState<number | null>(null);
  const [responseData, setResponseData] = useState<Record<string, unknown> | null>(null);
  const [lastTraceId, setLastTraceId] = useState<string>('');
  const [copied, setCopied] = useState<boolean>(false);

  const fetchCapabilities = async () => {
    try {
      const { data } = await apiClient.get('/protocol/capabilities');
      setCapabilities(data);
    } catch (err) {
      console.error('Error fetching capabilities:', err);
    }
  };

  const updateDefaultPayload = (tab: string) => {
    const trace = `trc_proto_${Math.random().toString(36).substring(2, 8)}`;
    setLastTraceId(trace);

    if (tab === 'discover') {
      setRequestPayload(JSON.stringify({
        query: "Running",
        category: "Footwear",
        max_price: 5000.0,
        currency: "INR",
        trace_id: trace
      }, null, 2));
    } else if (tab === 'recommend') {
      setRequestPayload(JSON.stringify({
        session_id: "sess_demo_01",
        buyer_preferences: { preferred_category: "Accessories" },
        trace_id: trace
      }, null, 2));
    } else if (tab === 'intent') {
      setRequestPayload(JSON.stringify({
        session_id: "sess_demo_01",
        buyer_id: "ai_buyer_external_01",
        constraints: { max_price: 5000.0, currency: "INR" },
        trace_id: trace
      }, null, 2));
    } else if (tab === 'auth') {
      setRequestPayload(JSON.stringify({
        purchase_intent_id: "pi_demo_sample_id"
      }, null, 2));
    } else if (tab === 'pay') {
      setRequestPayload(JSON.stringify({
        purchase_intent_id: "pi_demo_sample_id",
        authorization_id: "auth_demo_sample_id",
        idempotency_key: `idemp_${Math.random().toString(36).substring(2, 10)}`,
        trace_id: trace
      }, null, 2));
    }
  };

  useEffect(() => {
    fetchCapabilities();
    updateDefaultPayload('discover');
  }, []);

  const handleTabChange = (tab: 'discover' | 'recommend' | 'intent' | 'auth' | 'pay') => {
    setActiveTab(tab);
    updateDefaultPayload(tab);
    setResponseStatus(null);
    setResponseData(null);
  };

  const executeProtocolRequest = async () => {
    setLoading(true);
    setResponseStatus(null);
    setResponseData(null);

    try {
      let parsed: Record<string, unknown> = {};
      try {
        parsed = JSON.parse(requestPayload);
      } catch {
        alert('Invalid JSON in request payload.');
        setLoading(false);
        return;
      }

      let res;
      if (activeTab === 'discover') {
        res = await apiClient.post('/protocol/discover', parsed);
      } else if (activeTab === 'recommend') {
        res = await apiClient.post('/protocol/recommend', parsed);
      } else if (activeTab === 'intent') {
        res = await apiClient.post('/protocol/purchase-intent', parsed);
      } else if (activeTab === 'auth') {
        const piId = String(parsed.purchase_intent_id || 'sample');
        res = await apiClient.get(`/protocol/authorization/${piId}`);
      } else if (activeTab === 'pay') {
        res = await apiClient.post('/protocol/payment-request', parsed);
      }

      if (res) {
        setResponseStatus(res.status);
        setResponseData(res.data);
        if (res.data && res.data.trace_id) {
          setLastTraceId(res.data.trace_id);
        }
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { status: number; data: Record<string, unknown> }; message?: string };
      if (axiosErr.response) {
        setResponseStatus(axiosErr.response.status);
        setResponseData(axiosErr.response.data);
      } else {
        setResponseStatus(500);
        setResponseData({ error: axiosErr.message || 'Request failed' });
      }
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col justify-between">
      <DashboardNav />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white flex items-center gap-2">
                <span>AI-to-AI Commerce Protocol Explorer</span>
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono bg-sky-950 text-sky-400 border border-sky-800/60">
                SCHEMA v1.0.0
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Machine-readable JSON protocol enabling external autonomous AI agents to query catalog, request recommendations, create purchase intents, and execute authorized settlement.
            </p>
          </div>
          <div>
            <Link
              href="/dashboard/observability"
              className="px-3.5 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs font-mono text-slate-300 hover:text-white transition-colors"
            >
              Audit Trail →
            </Link>
          </div>
        </div>

      {/* Capabilities Overview Card */}
      {capabilities && (
        <div className="p-5 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-mono font-bold text-slate-300 uppercase tracking-wider">
              Merchant Protocol Capabilities Manifest
            </h2>
            <span className="text-[10px] font-mono text-emerald-400">
              GET /api/v1/protocol/capabilities
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
              <span className="text-slate-500">Merchant:</span>{' '}
              <span className="text-white font-bold">{capabilities.merchant_name}</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
              <span className="text-slate-500">Currency:</span>{' '}
              <span className="text-emerald-400 font-bold">{capabilities.supported_currency}</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
              <span className="text-slate-500">Price Grounding:</span>{' '}
              <span className="text-sky-400 font-bold">{capabilities.security_guarantees?.price_authority}</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
              <span className="text-slate-500">Audit Trail:</span>{' '}
              <span className="text-indigo-400 font-bold">{capabilities.security_guarantees?.audit_integrity}</span>
            </div>
          </div>
        </div>
      )}

      {/* Protocol Request / Response Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Operation Tabs & Request Builder (6 Cols) */}
        <div className="lg:col-span-6 space-y-4">
          {/* Operation Tabs */}
          <div className="flex flex-wrap gap-1.5 p-1 rounded-xl bg-slate-900 border border-slate-800">
            <button
              onClick={() => handleTabChange('discover')}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
                activeTab === 'discover'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              1. Discover
            </button>
            <button
              onClick={() => handleTabChange('recommend')}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
                activeTab === 'recommend'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              2. Recommend
            </button>
            <button
              onClick={() => handleTabChange('intent')}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
                activeTab === 'intent'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              3. Purchase Intent
            </button>
            <button
              onClick={() => handleTabChange('auth')}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
                activeTab === 'auth'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              4. Authorization Lookup
            </button>
            <button
              onClick={() => handleTabChange('pay')}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
                activeTab === 'pay'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              5. Payment Request
            </button>
          </div>

          {/* Request Header */}
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 font-mono text-xs">
                <span className="font-bold px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                  {activeTab === 'auth' ? 'GET' : 'POST'}
                </span>
                <span className="text-slate-300">
                  {activeTab === 'discover' && '/api/v1/protocol/discover'}
                  {activeTab === 'recommend' && '/api/v1/protocol/recommend'}
                  {activeTab === 'intent' && '/api/v1/protocol/purchase-intent'}
                  {activeTab === 'auth' && '/api/v1/protocol/authorization/{purchase_intent_id}'}
                  {activeTab === 'pay' && '/api/v1/protocol/payment-request'}
                </span>
              </div>
              <button
                onClick={() => copyToClipboard(requestPayload)}
                className="text-[11px] font-mono text-slate-400 hover:text-slate-200"
              >
                {copied ? '✓ Copied' : 'Copy JSON'}
              </button>
            </div>

            {/* Editable JSON Payload Textarea */}
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">
                Structured Request Body (Pydantic validated):
              </label>
              <textarea
                value={requestPayload}
                onChange={(e) => setRequestPayload(e.target.value)}
                rows={10}
                className="w-full p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-indigo-300 focus:outline-none focus:border-indigo-500 leading-relaxed"
              />
            </div>

            {/* Execute Button */}
            <div className="flex items-center justify-between pt-1">
              <span className="text-[10px] font-mono text-slate-400">
                Active Trace: <span className="text-indigo-400 font-bold">{lastTraceId}</span>
              </span>
              <button
                onClick={executeProtocolRequest}
                disabled={loading}
                className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-lg shadow-indigo-600/30 transition-all font-mono"
              >
                {loading ? 'Executing Protocol...' : 'Send Protocol Request →'}
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Live Response & Trace Correlation (6 Cols) */}
        <div className="lg:col-span-6 space-y-4">
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3 min-h-[440px] flex flex-col">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center space-x-2">
                <span className="text-xs font-mono font-bold text-white uppercase">Protocol Response</span>
                {responseStatus && (
                  <span
                    className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                      responseStatus >= 200 && responseStatus < 300
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : 'bg-rose-950 text-rose-300 border border-rose-800'
                    }`}
                  >
                    HTTP {responseStatus}
                  </span>
                )}
              </div>

              {responseData && (
                <button
                  onClick={() => copyToClipboard(JSON.stringify(responseData, null, 2))}
                  className="text-[11px] font-mono text-slate-400 hover:text-slate-200"
                >
                  Copy Response
                </button>
              )}
            </div>

            {/* Response Viewer */}
            <div className="flex-1">
              {responseData ? (
                <pre className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-emerald-300 overflow-x-auto max-h-[380px] leading-relaxed">
                  {JSON.stringify(responseData, null, 2)}
                </pre>
              ) : (
                <div className="h-full flex items-center justify-center text-center p-8 text-xs font-mono text-slate-400">
                  Select an operation and click &quot;Send Protocol Request&quot; to test the machine-to-machine interface.
                </div>
              )}
            </div>

            {/* Trace Deep Link */}
            {lastTraceId && (
              <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs font-mono">
                <span className="text-slate-400">Audit Correlated Trace:</span>
                <Link
                  href={`/dashboard/observability`}
                  className="text-indigo-400 hover:text-indigo-300 font-semibold underline"
                >
                  Inspect in Audit Explorer →
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
      </main>
      <footer className="border-t border-slate-900 bg-slate-950 text-slate-500 text-xs py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <span>Agentic Commerce OS — Machine-to-Machine AI Protocol</span>
          <span className="text-[11px] text-slate-600">Schema v1.0.0</span>
        </div>
      </footer>
    </div>
  );
}
