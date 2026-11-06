import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  PhoneCall,
  PhoneIncoming,
  PhoneOutgoing,
  PhoneMissed,
  Search,
  Filter,
  Clock,
  Eye,
  RefreshCw,
  Play,
  Volume2,
  Calendar,
  Sparkles,
  Zap,
  Activity,
  Layers,
  List,
  Smile,
  Meh,
  AlertCircle,
  Radio,
} from 'lucide-react';
import Badge from '../../components/common/Badge';
import CallDetailModal from './CallDetailModal';
import { callsService } from '../../services/api';
import confetti from 'canvas-confetti';

export default function Calls() {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCall, setSelectedCall] = useState(null);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [viewMode, setViewMode] = useState('matrix'); // 'matrix' (cards) or 'timeline'
  const [simulatingCall, setSimulatingCall] = useState(false);

  const fetchCalls = async () => {
    setLoading(true);
    try {
      const params = {};
      if (typeFilter) params.call_type = typeFilter;
      if (statusFilter) params.status = statusFilter;
      if (search) params.search = search;
      const data = await callsService.getCalls(params);
      setCalls(data);
    } catch (err) {
      console.error('Failed to fetch call logs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCalls();
  }, [typeFilter, statusFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchCalls();
  };

  const handleSimulateCall = async () => {
    setSimulatingCall(true);
    try {
      await callsService.simulateCall({
        caller_name: 'Dr. Sarah Mitchell',
        caller_phone: '+1 (555) 789-0123',
        call_type: 'incoming',
        notes: 'Simulated live inbound consultation booking inquiry',
      });
      confetti({
        particleCount: 50,
        spread: 60,
        origin: { y: 0.8 },
        colors: ['#E47745', '#F0AD57', '#A78BFA'],
      });
      await fetchCalls();
    } catch (e) {
      console.error(e);
    } finally {
      setTimeout(() => setSimulatingCall(false), 800);
    }
  };

  // Telemetry KPIs
  const totalCalls = calls.length;
  const inboundCount = calls.filter((c) => c.call_type === 'incoming').length;
  const outboundCount = calls.filter((c) => c.call_type === 'outgoing').length;
  const completedCount = calls.filter((c) => c.status === 'completed').length;
  const successRate = totalCalls > 0 ? Math.round((completedCount / totalCalls) * 100) : 100;
  const avgDuration =
    totalCalls > 0
      ? Math.round(calls.reduce((acc, c) => acc + (c.duration_seconds || 0), 0) / totalCalls)
      : 0;

  return (
    <div className="space-y-8 pb-12">
      {/* Hero Telephony Header */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-charcoal via-graphite to-warmblack border border-white/10 p-6 sm:p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-burnt/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
        <div className="absolute bottom-0 left-1/3 w-64 h-64 bg-lavender/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="p-2.5 rounded-xl bg-burnt/15 border border-burnt/30 text-burnt">
                <Radio className="w-5 h-5 animate-pulse" />
              </span>
              <span className="text-xs font-semibold tracking-wider uppercase text-burnt">
                Real-Time Telephony Console
              </span>
              <span className="flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-medium bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                Live Dispatch Ready
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-ivory tracking-tight">
              Call Management & Telemetry
            </h1>
            <p className="text-xs sm:text-sm text-mutedgrey max-w-xl">
              Inspect neural voice speech sessions, caller sentiment signals, AI dialog transcripts,
              and bidirectional audio telemetry with zero packet drop.
            </p>
          </div>

          {/* Quick Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleSimulateCall}
              disabled={simulatingCall}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs flex items-center gap-2 shadow-lg shadow-burnt/20 hover:shadow-burnt/40 hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {simulatingCall ? 'Simulating...' : 'Simulate Inbound Call'}
            </button>
            <button
              onClick={fetchCalls}
              className="p-2.5 rounded-xl bg-graphite/80 border border-white/10 text-ivory hover:text-burnt hover:border-burnt/30 transition-all"
              title="Refresh Calls"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Telemetry Quick Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-6 border-t border-white/5">
          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <PhoneIncoming className="w-3 h-3 text-burnt" /> Inbound Received
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-ivory mt-1">{inboundCount}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <PhoneOutgoing className="w-3 h-3 text-amber" /> Outbound Placed
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-ivory mt-1">{outboundCount}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <Zap className="w-3 h-3 text-emerald-400" /> Success Rate
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-emerald-400 mt-1">{successRate}%</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <Clock className="w-3 h-3 text-lavender" /> Mean Handle Time
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-lavender mt-1">{avgDuration}s</p>
          </div>
        </div>
      </div>

      {/* Control Ribbon (Filters, Search, View Switcher) */}
      <div className="bg-charcoal/80 border border-graphite rounded-2xl p-4 backdrop-blur-md flex flex-col lg:flex-row items-center justify-between gap-4">
        {/* Search */}
        <form onSubmit={handleSearchSubmit} className="relative w-full lg:w-96">
          <Search className="w-4 h-4 text-mutedgrey absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search by caller, phone number, or topic..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-warmblack/80 border border-graphite rounded-xl text-xs text-ivory placeholder-mutedgrey/60 focus:outline-none focus:border-burnt/50 transition-colors"
          />
        </form>

        {/* Filters and View Toggle */}
        <div className="flex flex-wrap items-center gap-3 w-full lg:w-auto justify-between lg:justify-end">
          <div className="flex items-center gap-2">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3 py-2 bg-warmblack/80 border border-graphite rounded-xl text-xs font-medium text-ivory focus:outline-none focus:border-burnt/50"
            >
              <option value="">All Direction Types</option>
              <option value="incoming">Inbound Only</option>
              <option value="outgoing">Outbound Only</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 bg-warmblack/80 border border-graphite rounded-xl text-xs font-medium text-ivory focus:outline-none focus:border-burnt/50"
            >
              <option value="">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="missed">Missed / Dropped</option>
            </select>
          </div>

          {/* View switcher */}
          <div className="flex items-center bg-warmblack/60 p-1 rounded-xl border border-graphite">
            <button
              onClick={() => setViewMode('matrix')}
              className={`p-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                viewMode === 'matrix'
                  ? 'bg-burnt text-warmblack shadow-sm font-bold'
                  : 'text-mutedgrey hover:text-ivory'
              }`}
              title="Matrix Card View"
            >
              <Layers className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Matrix</span>
            </button>
            <button
              onClick={() => setViewMode('timeline')}
              className={`p-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                viewMode === 'timeline'
                  ? 'bg-burnt text-warmblack shadow-sm font-bold'
                  : 'text-mutedgrey hover:text-ivory'
              }`}
              title="Timeline Activity Stream"
            >
              <List className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Stream</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Area: Matrix vs Stream */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-24 space-y-4">
          <div className="w-10 h-10 border-3 border-burnt border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-mutedgrey animate-pulse font-mono tracking-wider">
            SYNCHRONIZING TELEPHONY LOGS...
          </p>
        </div>
      ) : calls.length === 0 ? (
        <div className="glass-panel p-12 text-center rounded-3xl border border-graphite space-y-4">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-burnt/10 border border-burnt/20 flex items-center justify-center text-burnt">
            <PhoneMissed className="w-8 h-8" />
          </div>
          <h3 className="text-base font-bold text-ivory">No Telephony Sessions Found</h3>
          <p className="text-xs text-mutedgrey max-w-md mx-auto">
            No voice logs match your current filter criteria. You can test your AI assistant by
            triggering a simulated inbound consultation call.
          </p>
          <button
            onClick={handleSimulateCall}
            className="px-5 py-2.5 rounded-xl bg-burnt hover:bg-burnt/90 text-warmblack font-bold text-xs transition-colors inline-flex items-center gap-2"
          >
            <Sparkles className="w-3.5 h-3.5" /> Trigger Demo Call
          </button>
        </div>
      ) : viewMode === 'matrix' ? (
        /* Matrix Grid View */
        <motion.div
          layout
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"
        >
          <AnimatePresence>
            {calls.map((call, idx) => {
              const minutes = Math.floor((call.duration_seconds || 0) / 60);
              const seconds = (call.duration_seconds || 0) % 60;
              const isInbound = call.call_type === 'incoming';

              return (
                <motion.div
                  key={call.id || idx}
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ delay: idx * 0.04 }}
                  onClick={() => setSelectedCall(call)}
                  className="group relative bg-gradient-to-b from-charcoal/90 to-graphite/90 border border-graphite hover:border-burnt/50 rounded-2xl p-5 shadow-lg hover:shadow-burnt/10 transition-all cursor-pointer flex flex-col justify-between"
                >
                  {/* Subtle top indicator bar */}
                  <div
                    className={`absolute top-0 left-6 right-6 h-0.5 rounded-full ${
                      isInbound ? 'bg-burnt/60' : 'bg-amber/60'
                    }`}
                  />

                  <div>
                    {/* Direction and Status */}
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <span
                          className={`p-2 rounded-xl text-xs flex items-center justify-center ${
                            isInbound
                              ? 'bg-burnt/15 border border-burnt/30 text-burnt'
                              : 'bg-amber/15 border border-amber/30 text-amber'
                          }`}
                        >
                          {isInbound ? (
                            <PhoneIncoming className="w-4 h-4" />
                          ) : (
                            <PhoneOutgoing className="w-4 h-4" />
                          )}
                        </span>
                        <div>
                          <p className="text-[10px] font-bold tracking-wider uppercase text-mutedgrey">
                            {isInbound ? 'Inbound Voice' : 'Outbound AI'}
                          </p>
                          <p className="text-xs font-mono text-ivory/80">{call.caller_phone}</p>
                        </div>
                      </div>

                      <Badge status={call.status} />
                    </div>

                    {/* Caller Name and Summary */}
                    <div className="space-y-1 mb-4">
                      <h3 className="text-base font-bold text-ivory group-hover:text-burnt transition-colors">
                        {call.caller_name || 'Customer'}
                      </h3>
                      <p className="text-xs text-mutedgrey line-clamp-2 leading-relaxed">
                        {call.summary || 'General customer inquiry and appointment scheduling.'}
                      </p>
                    </div>

                    {/* Synthetic Mini-Waveform visualization representation */}
                    <div className="py-2 px-3 rounded-xl bg-warmblack/60 border border-white/5 flex items-center justify-between gap-3 mb-4">
                      <div className="flex items-center gap-1.5 text-burnt">
                        <Volume2 className="w-3.5 h-3.5" />
                        <span className="text-[10px] font-mono text-mutedgrey">
                          {call.duration_seconds > 0 ? `${minutes}m ${seconds}s` : '0s'}
                        </span>
                      </div>

                      {/* Mini audio bars */}
                      <div className="flex items-center gap-1 h-4">
                        {[40, 70, 95, 30, 85, 60, 45, 90, 50, 75].map((height, i) => (
                          <div
                            key={i}
                            className={`w-0.5 rounded-full transition-all duration-300 ${
                              call.status === 'completed'
                                ? 'bg-burnt/70 group-hover:bg-burnt'
                                : 'bg-mutedgrey/30'
                            }`}
                            style={{ height: `${height}%` }}
                          />
                        ))}
                      </div>

                      <div className="flex items-center gap-1 text-[10px] text-mutedgrey font-mono">
                        <Smile className="w-3 h-3 text-emerald-400" />
                        <span>Positive</span>
                      </div>
                    </div>
                  </div>

                  {/* Card Footer: Timestamp and Inspect Button */}
                  <div className="pt-3 border-t border-white/5 flex items-center justify-between text-xs text-mutedgrey">
                    <span className="text-[11px] font-mono flex items-center gap-1">
                      <Clock className="w-3 h-3 text-mutedgrey" />
                      {new Date(call.initiated_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>

                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-ivory group-hover:text-burnt transition-colors">
                      <Eye className="w-3.5 h-3.5" /> Inspect Session
                    </span>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </motion.div>
      ) : (
        /* Stream Timeline View */
        <div className="glass-panel rounded-2xl border border-graphite overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-mutedgrey">
              <thead className="bg-warmblack/90 text-ivory/70 uppercase tracking-wider font-semibold border-b border-graphite">
                <tr>
                  <th className="py-3.5 px-5">Flow</th>
                  <th className="py-3.5 px-4">Caller Identity</th>
                  <th className="py-3.5 px-4">Phone Number</th>
                  <th className="py-3.5 px-4">Session Duration</th>
                  <th className="py-3.5 px-4">Delivery Status</th>
                  <th className="py-3.5 px-4">AI Telemetry Summary</th>
                  <th className="py-3.5 px-4">Timestamp</th>
                  <th className="py-3.5 px-5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-graphite/40 bg-charcoal/50">
                {calls.map((call) => {
                  const minutes = Math.floor((call.duration_seconds || 0) / 60);
                  const seconds = (call.duration_seconds || 0) % 60;
                  const durText = `${minutes}m ${seconds}s`;
                  const isInbound = call.call_type === 'incoming';

                  return (
                    <tr
                      key={call.id}
                      onClick={() => setSelectedCall(call)}
                      className="hover:bg-graphite/40 transition-colors cursor-pointer group"
                    >
                      <td className="py-3.5 px-5">
                        <div className="flex items-center gap-2">
                          <span
                            className={`p-1.5 rounded-lg ${
                              isInbound
                                ? 'bg-burnt/15 text-burnt border border-burnt/30'
                                : 'bg-amber/15 text-amber border border-amber/30'
                            }`}
                          >
                            {isInbound ? (
                              <PhoneIncoming className="w-3.5 h-3.5" />
                            ) : (
                              <PhoneOutgoing className="w-3.5 h-3.5" />
                            )}
                          </span>
                          <span className="font-semibold text-ivory capitalize text-xs">
                            {call.call_type}
                          </span>
                        </div>
                      </td>

                      <td className="py-3.5 px-4 font-bold text-ivory group-hover:text-burnt transition-colors">
                        {call.caller_name || 'Caller'}
                      </td>

                      <td className="py-3.5 px-4 font-mono text-mutedgrey">{call.caller_phone}</td>

                      <td className="py-3.5 px-4 font-medium text-ivory">
                        {call.duration_seconds > 0 ? durText : '—'}
                      </td>

                      <td className="py-3.5 px-4">
                        <Badge status={call.status} />
                      </td>

                      <td className="py-3.5 px-4 max-w-xs truncate text-mutedgrey">
                        {call.summary || 'Customer consultation inquiry'}
                      </td>

                      <td className="py-3.5 px-4 font-mono text-[11px] text-mutedgrey">
                        {new Date(call.initiated_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>

                      <td className="py-3.5 px-5 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedCall(call);
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-warmblack border border-graphite text-xs font-semibold text-ivory hover:text-burnt hover:border-burnt/40 transition-colors"
                        >
                          <Eye className="w-3 h-3" /> View
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Telemetry Detail Modal with waveform audio player and sentiment */}
      {selectedCall && (
        <CallDetailModal
          isOpen={!!selectedCall}
          onClose={() => setSelectedCall(null)}
          call={selectedCall}
        />
      )}
    </div>
  );
}
