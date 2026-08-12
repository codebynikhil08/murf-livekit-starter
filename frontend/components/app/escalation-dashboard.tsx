'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  CheckCircle2, 
  Clock, 
  AlertTriangle, 
  ShieldAlert, 
  UserCheck, 
  Phone, 
  MapPin, 
  Globe, 
  Copy, 
  Check, 
  RefreshCw, 
  X,
  Filter
} from 'lucide-react';

export interface Escalation {
  id: string;
  reference_id: string;
  caller_name: string;
  issue_summary: string;
  urgency: 'low' | 'medium' | 'high' | 'emergency' | string;
  language_preference: string;
  contact_method: string;
  location: string;
  status: 'Open' | 'In Progress' | 'Resolved' | string;
  created_at: string;
  updated_at: string;
}

interface EscalationDashboardProps {
  isOpen: boolean;
  onClose: () => void;
}

export function EscalationDashboard({ isOpen, onClose }: EscalationDashboardProps) {
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'All' | 'Open' | 'In Progress' | 'Resolved'>('All');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const fetchEscalations = async () => {
    try {
      const res = await fetch('/api/escalations');
      const data = await res.json();
      if (data.success && Array.isArray(data.escalations)) {
        setEscalations(data.escalations);
      }
    } catch (err) {
      console.error('Failed to load escalations:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchEscalations();
      const interval = setInterval(fetchEscalations, 3000);
      return () => clearInterval(interval);
    }
  }, [isOpen]);

  const handleUpdateStatus = async (refId: string, newStatus: string) => {
    setUpdatingId(refId);
    try {
      const res = await fetch('/api/escalations', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reference_id: refId, status: newStatus }),
      });
      const data = await res.json();
      if (data.success) {
        setEscalations((prev) =>
          prev.map((item) =>
            item.reference_id === refId ? { ...item, status: newStatus } : item
          )
        );
      }
    } catch (err) {
      console.error('Failed to update status:', err);
    } finally {
      setUpdatingId(null);
    }
  };

  const copyRefId = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredEscalations = escalations.filter((item) => {
    if (filter === 'All') return true;
    return item.status.toLowerCase() === filter.toLowerCase();
  });

  const countOpen = escalations.filter((i) => i.status === 'Open').length;
  const countInProgress = escalations.filter((i) => i.status === 'In Progress').length;
  const countResolved = escalations.filter((i) => i.status === 'Resolved').length;

  const getUrgencyBadge = (urgency: string) => {
    switch (urgency.toLowerCase()) {
      case 'emergency':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-500/20 text-red-400 border border-red-500/40 animate-pulse">
            <ShieldAlert className="w-3 h-3 text-red-400" />
            EMERGENCY
          </span>
        );
      case 'high':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-orange-500/20 text-orange-400 border border-orange-500/40">
            <AlertTriangle className="w-3 h-3 text-orange-400" />
            HIGH
          </span>
        );
      case 'low':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
            LOW
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-400 border border-amber-500/40">
            MEDIUM
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'In Progress':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">
            <Clock className="w-3 h-3" />
            In Progress
          </span>
        );
      case 'Resolved':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3" />
            Resolved
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
            <AlertTriangle className="w-3 h-3" />
            Open
          </span>
        );
    }
  };

  const formatTimestamp = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ', ' + d.toLocaleDateString();
    } catch {
      return iso;
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/70 backdrop-blur-md">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 15 }}
          transition={{ duration: 0.25 }}
          className="relative w-full max-w-4xl max-h-[85vh] flex flex-col rounded-2xl border border-white/10 bg-slate-900/95 text-slate-100 shadow-2xl overflow-hidden"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-slate-900/80">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-amber-500 to-orange-500 text-white shadow-lg shadow-orange-500/20">
                <UserCheck className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold tracking-tight text-white">
                    Krishi Officer Human Escalation Portal
                  </h2>
                  <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-ping" title="Live Polling Active" />
                </div>
                <p className="text-xs text-slate-400">
                  Requests created by Kisan Mitra AI voice agent when human intervention is required
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={fetchEscalations}
                className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
                title="Refresh requests"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
              <button
                onClick={onClose}
                className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Stats Bar & Filter Tabs */}
          <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-3 border-b border-white/5 bg-slate-950/40">
            <div className="flex gap-2">
              {(['All', 'Open', 'In Progress', 'Resolved'] as const).map((tab) => {
                const count =
                  tab === 'All'
                    ? escalations.length
                    : tab === 'Open'
                    ? countOpen
                    : tab === 'In Progress'
                    ? countInProgress
                    : countResolved;

                return (
                  <button
                    key={tab}
                    onClick={() => setFilter(tab)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                      filter === tab
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm'
                        : 'text-slate-400 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    <span>{tab}</span>
                    <span className={`px-1.5 py-0.2 rounded-full text-[10px] ${
                      filter === tab ? 'bg-amber-500/30 text-amber-200' : 'bg-white/10 text-slate-400'
                    }`}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="text-xs text-slate-400 flex items-center gap-1">
              <Filter className="w-3 h-3 text-slate-500" />
              Showing <span className="font-semibold text-slate-200">{filteredEscalations.length}</span> of{' '}
              <span className="font-semibold text-slate-200">{escalations.length}</span> tickets
            </div>
          </div>

          {/* Ticket List */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                <RefreshCw className="w-8 h-8 animate-spin text-amber-500 mb-3" />
                <p className="text-sm">Loading human help requests...</p>
              </div>
            ) : filteredEscalations.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center text-slate-500">
                <CheckCircle2 className="w-12 h-12 text-slate-600 mb-3 stroke-1" />
                <p className="text-base font-medium text-slate-300">No {filter !== 'All' ? filter.toLowerCase() : ''} requests found</p>
                <p className="text-xs max-w-sm mt-1 text-slate-400">
                  When Kisan Mitra voice agent encounters a complex issue or crop emergency, human escalation requests will appear here automatically.
                </p>
              </div>
            ) : (
              filteredEscalations.map((ticket) => (
                <motion.div
                  key={ticket.id}
                  layout
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`rounded-xl border p-5 transition-all ${
                    ticket.urgency.toLowerCase() === 'emergency'
                      ? 'border-red-500/40 bg-red-950/10 shadow-lg shadow-red-950/20'
                      : ticket.status === 'Open'
                      ? 'border-amber-500/30 bg-slate-800/60 hover:border-amber-500/50'
                      : 'border-white/10 bg-slate-800/30'
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-3">
                      <span className="text-base font-bold text-white">
                        {ticket.caller_name}
                      </span>
                      <button
                        onClick={() => copyRefId(ticket.reference_id)}
                        className="inline-flex items-center gap-1 font-mono text-xs text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded border border-amber-400/20 hover:bg-amber-400/20 transition-colors"
                        title="Click to copy Reference ID"
                      >
                        {copiedId === ticket.reference_id ? (
                          <Check className="w-3 h-3 text-emerald-400" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                        {ticket.reference_id}
                      </button>
                    </div>

                    <div className="flex items-center gap-2">
                      {getUrgencyBadge(ticket.urgency)}
                      {getStatusBadge(ticket.status)}
                    </div>
                  </div>

                  {/* Summary Box */}
                  <div className="rounded-lg bg-slate-950/60 p-3.5 text-sm text-slate-300 leading-relaxed border border-white/5 mb-4">
                    <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                      Issue & Diagnostic Summary
                    </p>
                    {ticket.issue_summary}
                  </div>

                  {/* Meta details & Actions */}
                  <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400 pt-2 border-t border-white/5">
                    <div className="flex flex-wrap items-center gap-4">
                      {ticket.location && (
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3.5 h-3.5 text-slate-500" />
                          {ticket.location}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Globe className="w-3.5 h-3.5 text-slate-500" />
                        {ticket.language_preference}
                      </span>
                      <span className="flex items-center gap-1">
                        <Phone className="w-3.5 h-3.5 text-slate-500" />
                        {ticket.contact_method}
                      </span>
                      <span className="flex items-center gap-1 text-slate-500">
                        <Clock className="w-3.5 h-3.5" />
                        {formatTimestamp(ticket.created_at)}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {ticket.status === 'Open' && (
                        <button
                          disabled={updatingId === ticket.reference_id}
                          onClick={() => handleUpdateStatus(ticket.reference_id, 'In Progress')}
                          className="px-3 py-1 rounded-md bg-blue-600/30 hover:bg-blue-600/50 text-blue-300 border border-blue-500/40 text-xs font-semibold transition-colors disabled:opacity-50"
                        >
                          Mark In Progress
                        </button>
                      )}

                      {ticket.status !== 'Resolved' ? (
                        <button
                          disabled={updatingId === ticket.reference_id}
                          onClick={() => handleUpdateStatus(ticket.reference_id, 'Resolved')}
                          className="px-3 py-1 rounded-md bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-300 border border-emerald-500/40 text-xs font-semibold transition-colors disabled:opacity-50"
                        >
                          Resolve Ticket
                        </button>
                      ) : (
                        <button
                          disabled={updatingId === ticket.reference_id}
                          onClick={() => handleUpdateStatus(ticket.reference_id, 'Open')}
                          className="px-3 py-1 rounded-md bg-slate-700/50 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors disabled:opacity-50"
                        >
                          Reopen
                        </button>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-3 border-t border-white/10 bg-slate-950/60 text-xs text-slate-400 flex items-center justify-between">
            <span>Murf AI Voice Agent Challenge · Day 7 Human Escalation System</span>
            <span className="text-slate-500">Kisan Mitra Krishi Support</span>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
