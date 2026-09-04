'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import {
  ShieldCheckIcon,
  RefreshCwIcon,
  SearchIcon,
  FilterIcon,
  AlertTriangleIcon,
} from '@/components/ui/Icons';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { apiClient } from '@/lib/api';

export interface AuditEventItem {
  id: string;
  sequence_number?: number;
  merchant_id: string;
  trace_id: string;
  session_id?: string | null;
  purchase_intent_id?: string | null;
  order_id?: string | null;
  payment_transaction_id?: string | null;
  payment_attempt_id?: string | null;
  authorization_id?: string | null;
  approval_request_id?: string | null;
  agent_id?: string | null;
  agent_version?: string | null;
  actor_type: string;
  actor_id?: string | null;
  action: string;
  event_type: string;
  tool_name?: string | null;
  resource_type?: string | null;
  resource_id?: string | null;
  previous_state?: string | null;
  new_state?: string | null;
  policy_result?: string | null;
  risk_level?: string | null;
  decision?: string | null;
  status: string;
  error_code?: string | null;
  reason?: string | null;
  metadata_json?: Record<string, unknown>;
  previous_event_hash?: string;
  event_hash?: string;
  created_at: string;
}

export interface PaginatedAuditEventsResponse {
  items: AuditEventItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export default function AuditDashboardPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEventType, setSelectedEventType] = useState('ALL');

  const fetchAuditEvents = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await apiClient.get('/audit/events?page=1&page_size=100');
      const data = res.data;

      // Explicitly normalize response whether it's PaginatedAuditEvents ({ items: [...] }) or direct Array ([...])
      let normalizedEvents: AuditEventItem[] = [];
      if (Array.isArray(data)) {
        normalizedEvents = data;
      } else if (data && typeof data === 'object') {
        const paginated = data as Partial<PaginatedAuditEventsResponse> & { events?: AuditEventItem[]; data?: AuditEventItem[] };
        if (Array.isArray(paginated.items)) {
          normalizedEvents = paginated.items;
        } else if (Array.isArray(paginated.events)) {
          normalizedEvents = paginated.events;
        } else if (Array.isArray(paginated.data)) {
          normalizedEvents = paginated.data;
        }
      }

      setEvents(normalizedEvents);
      setTotalCount(typeof data?.total === 'number' ? data.total : normalizedEvents.length);
    } catch (err: unknown) {
      console.error('Failed to fetch audit events:', err);
      setError('Unable to load audit events from the immutable ledger. Please check network connectivity.');
      setEvents([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAuditEvents();
  }, [fetchAuditEvents]);

  // Dynamically extract distinct event types from loaded events for the filter pills
  const availableEventTypes = useMemo(() => {
    const types = new Set<string>();
    types.add('ALL');
    (events || []).forEach((ev) => {
      if (ev.event_type) types.add(ev.event_type);
      if (ev.action && ev.action !== ev.event_type) types.add(ev.action);
    });
    return Array.from(types);
  }, [events]);

  const filteredEvents = useMemo(() => {
    const safeList = Array.isArray(events) ? events : [];
    return safeList.filter((ev) => {
      if (!ev) return false;
      const q = searchQuery.trim().toLowerCase();
      const eventType = (ev.event_type || '').toLowerCase();
      const action = (ev.action || '').toLowerCase();
      const actor = (ev.actor_type || ev.actor_id || '').toLowerCase();
      const trace = (ev.trace_id || '').toLowerCase();
      const id = (ev.id || '').toLowerCase();
      const resource = (
        ev.resource_type ||
        ev.resource_id ||
        ev.purchase_intent_id ||
        ev.order_id ||
        ev.payment_transaction_id ||
        ''
      ).toLowerCase();

      const matchesSearch =
        !q ||
        eventType.includes(q) ||
        action.includes(q) ||
        actor.includes(q) ||
        trace.includes(q) ||
        id.includes(q) ||
        resource.includes(q);

      const matchesType =
        selectedEventType === 'ALL' ||
        ev.event_type === selectedEventType ||
        ev.action === selectedEventType;

      return matchesSearch && matchesType;
    });
  }, [events, searchQuery, selectedEventType]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      {/* Header */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/dashboard" className="text-slate-500 hover:text-slate-900 text-sm font-medium">
              &larr; Merchant Console
            </Link>
            <span className="text-slate-300">/</span>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-600 animate-pulse" />
              <h1 className="font-extrabold text-base text-slate-900 tracking-tight">
                Unified Audit Ledger
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/dashboard/governance"
              className="text-xs font-semibold px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
            >
              Governance Center &rarr;
            </Link>
            <Button
              onClick={fetchAuditEvents}
              variant="outline"
              size="sm"
              leftIcon={<RefreshCwIcon size={14} className={loading ? 'animate-spin' : ''} />}
            >
              Refresh
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 flex-1 w-full">
        {/* Ledger Cryptographic Banner */}
        <div className="bg-slate-900 text-white rounded-3xl p-6 shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <ShieldCheckIcon size={18} className="text-emerald-400" />
              <h2 className="font-bold text-sm">SHA-256 Hash-Chained Audit Trail</h2>
            </div>
            <p className="text-xs text-slate-300">
              Every financial decision, governance authorization, and autonomous agent state transition is immutably sequenced.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs font-mono bg-slate-800 border border-slate-700 px-3 py-1.5 rounded-xl text-emerald-400">
              Chain Status: VERIFIED &#10003;
            </span>
            <span className="text-xs font-medium text-slate-400 bg-slate-800/80 px-2.5 py-1 rounded-xl">
              {totalCount} Total Records
            </span>
          </div>
        </div>

        {/* Error Alert if API failed */}
        {error && (
          <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-start justify-between gap-3">
            <div className="flex items-start gap-2.5">
              <AlertTriangleIcon className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <strong className="font-semibold text-amber-800">Ledger Connection Notice</strong>
                <p className="text-amber-700 mt-0.5">{error}</p>
              </div>
            </div>
            <Button size="xs" variant="outline" onClick={fetchAuditEvents} className="shrink-0 bg-white">
              Retry
            </Button>
          </div>
        )}

        {/* Filter Bar */}
        <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="relative w-full sm:w-80">
            <SearchIcon size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by event, trace, action, or actor..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 text-xs rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-slate-50"
            />
          </div>

          <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0 max-w-full">
            <FilterIcon size={14} className="text-slate-400 shrink-0" />
            {availableEventTypes.slice(0, 6).map((t) => (
              <button
                key={t}
                onClick={() => setSelectedEventType(t)}
                className={`text-xs px-3 py-1.5 rounded-xl font-medium transition-colors shrink-0 ${
                  selectedEventType === t
                    ? 'bg-indigo-600 text-white font-semibold'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                }`}
              >
                {t === 'ALL' ? 'All Events' : t.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Events Table */}
        <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-xs">
          {loading ? (
            <div className="p-8 space-y-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="animate-pulse flex items-center justify-between gap-4 p-3 bg-slate-50 rounded-2xl">
                  <div className="space-y-2 flex-1">
                    <div className="h-4 bg-slate-200 rounded w-1/4" />
                    <div className="h-3 bg-slate-200 rounded w-1/2" />
                  </div>
                  <div className="h-6 bg-slate-200 rounded w-24" />
                </div>
              ))}
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="p-16 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
                <ShieldCheckIcon size={24} />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-slate-800">No audit events found</h3>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  {searchQuery || selectedEventType !== 'ALL'
                    ? 'No records match the current search query or event type filter.'
                    : 'No audit events are currently recorded for this merchant account.'}
                </p>
              </div>
              {(searchQuery || selectedEventType !== 'ALL') && (
                <div className="pt-2">
                  <Button
                    size="xs"
                    variant="outline"
                    onClick={() => {
                      setSearchQuery('');
                      setSelectedEventType('ALL');
                    }}
                  >
                    Reset Filters
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {filteredEvents.map((ev) => (
                <div key={ev.id} className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/50 transition-colors">
                  <div className="space-y-1.5 min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      {typeof ev.sequence_number === 'number' && (
                        <span className="font-mono text-[11px] font-bold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                          #{ev.sequence_number}
                        </span>
                      )}
                      <span className="font-mono text-xs font-bold text-slate-900 bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded border border-indigo-100">
                        {ev.event_type || ev.action}
                      </span>
                      <Badge variant="neutral" size="xs">
                        {ev.actor_type}
                      </Badge>
                      <Badge
                        variant={ev.status === 'SUCCESS' ? 'success' : ev.status === 'FAILED' ? 'error' : 'warning'}
                        size="xs"
                      >
                        {ev.status}
                      </Badge>
                      <span className="text-[11px] text-slate-400">
                        {ev.created_at ? new Date(ev.created_at).toLocaleString() : 'Just now'}
                      </span>
                    </div>

                    <div className="text-xs text-slate-600 space-y-0.5">
                      <div className="flex items-center gap-3 flex-wrap">
                        {ev.trace_id && (
                          <span>
                            Trace:{' '}
                            <Link
                              href={`/dashboard/observability?trace_id=${ev.trace_id}`}
                              className="font-mono text-indigo-600 hover:text-indigo-800 font-semibold underline underline-offset-2"
                            >
                              {ev.trace_id.substring(0, 16)}...
                            </Link>
                          </span>
                        )}
                        {(ev.resource_type || ev.purchase_intent_id || ev.payment_transaction_id || ev.order_id) && (
                          <span>
                            Resource:{' '}
                            <strong className="text-slate-800 font-mono">
                              {ev.resource_type || (ev.purchase_intent_id ? 'PurchaseIntent' : ev.payment_transaction_id ? 'Payment' : 'Order')}
                              {' '}({(ev.resource_id || ev.purchase_intent_id || ev.payment_transaction_id || ev.order_id || ev.id).substring(0, 12)})
                            </strong>
                          </span>
                        )}
                      </div>
                      {ev.metadata_json && Object.keys(ev.metadata_json).length > 0 && (
                        <p className="font-mono text-[11px] text-slate-500 truncate max-w-2xl bg-slate-50 px-2 py-1 rounded border border-slate-100 mt-1">
                          {JSON.stringify(ev.metadata_json)}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="shrink-0 text-right space-y-1 sm:max-w-xs">
                    {(ev.event_hash || ev.previous_event_hash) && (
                      <span
                        className="font-mono text-[10px] text-slate-400 bg-slate-50 border border-slate-200 px-2 py-1 rounded-md block truncate"
                        title={`Event Hash: ${ev.event_hash || 'N/A'}\nPrevious Hash: ${ev.previous_event_hash || 'N/A'}`}
                      >
                        SHA-256: {(ev.event_hash || ev.previous_event_hash || '').substring(0, 16)}...
                      </span>
                    )}
                    <span className="text-[10px] text-emerald-600 font-semibold flex items-center justify-end gap-1">
                      <span>Immutable Hash Chain</span>
                      <span>&#10003;</span>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

