'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Phone, 
  CheckCircle2, 
  XCircle, 
  BarChart2, 
  Clock, 
  User, 
  X, 
  RefreshCw 
} from 'lucide-react';

export interface CallLog {
  session_id: string;
  caller_name: string;
  status: string;
  outcome: 'success' | 'failed' | string;
  reason: string;
  created_at: string;
  updated_at: string;
}

export interface Stats {
  total: number;
  successful: number;
  failed: number;
}

interface AnalyticsDashboardProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AnalyticsDashboard({ isOpen, onClose }: AnalyticsDashboardProps) {
  const [stats, setStats] = useState<Stats>({ total: 0, successful: 0, failed: 0 });
  const [calls, setCalls] = useState<CallLog[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAnalytics = async () => {
    try {
      const res = await fetch('/api/calls');
      const data = await res.json();
      if (data.success) {
        setStats(data.stats);
        setCalls(data.recent_calls || []);
      }
    } catch (err) {
      console.error('Failed to fetch call analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchAnalytics();
      const interval = setInterval(fetchAnalytics, 3000);
      return () => clearInterval(interval);
    }
  }, [isOpen]);

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
      <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-6 bg-black/70 backdrop-blur-md">
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
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-500 text-white shadow-lg shadow-indigo-500/20">
                <BarChart2 className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold tracking-tight text-white">
                    Call Analytics Dashboard
                  </h2>
                  <span className="flex h-2 w-2 rounded-full bg-indigo-400 animate-ping" title="Live Polling Active" />
                </div>
                <p className="text-xs text-slate-400">
                  Real-time call tracking and performance metrics for Kisan Mitra voice agent
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={fetchAnalytics}
                className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
                title="Refresh stats"
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

          {/* Stats Bar */}
          <div className="grid grid-cols-3 border-b border-white/10 bg-slate-950/40 p-6 gap-4">
            <div className="flex flex-col items-center justify-center p-4 rounded-xl bg-slate-800/40 border border-white/5 shadow-inner">
              <Phone className="w-6 h-6 text-slate-400 mb-1" />
              <span className="text-2xl font-black text-white">{stats.total}</span>
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Total Calls</span>
            </div>
            
            <div className="flex flex-col items-center justify-center p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/20 shadow-inner">
              <CheckCircle2 className="w-6 h-6 text-emerald-400 mb-1" />
              <span className="text-2xl font-black text-emerald-400">{stats.successful}</span>
              <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-400">Successful</span>
            </div>
            
            <div className="flex flex-col items-center justify-center p-4 rounded-xl bg-red-500/5 border border-red-500/20 shadow-inner">
              <XCircle className="w-6 h-6 text-red-400 mb-1" />
              <span className="text-2xl font-black text-red-400">{stats.failed}</span>
              <span className="text-[10px] uppercase font-bold tracking-wider text-red-400">Failed</span>
            </div>
          </div>

          {/* Call Logs */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-2">Recent Calls</h3>
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16 text-slate-400">
                <RefreshCw className="w-8 h-8 animate-spin text-indigo-500 mb-3" />
                <p className="text-sm">Loading call analytics logs...</p>
              </div>
            ) : calls.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center text-slate-500">
                <Phone className="w-12 h-12 text-slate-600 mb-3 stroke-1" />
                <p className="text-base font-medium text-slate-300">No calls recorded yet</p>
                <p className="text-xs max-w-sm mt-1 text-slate-400">
                  When callers dial in or place a call to the Kisan Mitra voice agent, call records will appear here in real-time.
                </p>
              </div>
            ) : (
              <div className="overflow-hidden rounded-xl border border-white/5 bg-slate-950/20">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-white/10 bg-slate-950/60 text-xs font-bold text-slate-400">
                      <th className="p-3">Session/Room</th>
                      <th className="p-3">Caller</th>
                      <th className="p-3">Status</th>
                      <th className="p-3">Outcome</th>
                      <th className="p-3">Reason / Details</th>
                      <th className="p-3 text-right">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 text-xs text-slate-300">
                    {calls.map((call) => (
                      <tr key={call.session_id} className="hover:bg-white/5 transition-colors">
                        <td className="p-3 font-mono text-[10px] text-slate-400 select-all max-w-[120px] truncate" title={call.session_id}>
                          {call.session_id}
                        </td>
                        <td className="p-3 font-semibold text-slate-200">
                          <span className="flex items-center gap-1">
                            <User className="w-3.5 h-3.5 text-slate-500" />
                            {call.caller_name || 'Unknown'}
                          </span>
                        </td>
                        <td className="p-3">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            call.status === 'active' 
                              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30 animate-pulse' 
                              : 'bg-slate-800 text-slate-400 border border-slate-700'
                          }`}>
                            {call.status}
                          </span>
                        </td>
                        <td className="p-3">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            call.outcome === 'success' 
                              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
                              : 'bg-red-500/20 text-red-400 border border-red-500/30'
                          }`}>
                            {call.outcome === 'success' ? 'SUCCESS' : 'FAILED'}
                          </span>
                        </td>
                        <td className="p-3 text-slate-400 max-w-[200px] truncate" title={call.reason}>
                          {call.reason}
                        </td>
                        <td className="p-3 text-right text-slate-500 font-mono">
                          {formatTimestamp(call.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-3 border-t border-white/10 bg-slate-950/60 text-xs text-slate-400 flex items-center justify-between">
            <span>Murf AI Voice Agent Challenge · Day 8 Analytics System</span>
            <span className="text-slate-500">Kisan Mitra Performance</span>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
