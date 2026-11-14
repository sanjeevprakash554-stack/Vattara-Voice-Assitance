import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BellRing,
  Plus,
  Send,
  Clock,
  MessageSquare,
  PhoneCall,
  Calendar,
  CheckCircle2,
  Trash2,
  RefreshCw,
  Sparkles,
  Zap,
  Radio,
  SendHorizontal,
  Smartphone,
  ShieldCheck,
  AlertCircle,
  Sliders,
  Settings,
  RotateCcw,
  Check,
  Play,
  Volume2,
} from 'lucide-react';
import Modal from '../../components/common/Modal';
import Badge from '../../components/common/Badge';
import { remindersService, customersService } from '../../services/api';
import confetti from 'canvas-confetti';

export default function Reminders() {
  const [reminders, setReminders] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [channelFilter, setChannelFilter] = useState('all');
  const [sendingId, setSendingId] = useState(null);
  const [processingDue, setProcessingDue] = useState(false);
  const [processResult, setProcessResult] = useState(null);

  // Settings State & Modal
  const [settingsModal, setSettingsModal] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settings, setSettings] = useState({
    reminder_intervals_hours: '24,2',
    calling_start_time: '09:00',
    calling_end_time: '20:00',
    max_retries: 3,
    retry_delay_minutes: 15,
    is_enabled: true,
    default_channel: 'voice',
  });

  // New Reminder Modal
  const [createModal, setCreateModal] = useState(false);
  const [newRem, setNewRem] = useState({
    customer_id: '',
    reminder_type: 'call',
    scheduled_time: '',
    message: '',
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      const [rData, cData, sData] = await Promise.all([
        remindersService.getReminders(params),
        customersService.getCustomers(),
        remindersService.getSettings().catch(() => null),
      ]);
      setReminders(rData || []);
      setCustomers(cData || []);
      if (sData) setSettings(sData);
    } catch (err) {
      console.error('Failed to load reminders:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter]);

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSavingSettings(true);
    try {
      const updated = await remindersService.updateSettings({
        ...settings,
        max_retries: Number(settings.max_retries),
        retry_delay_minutes: Number(settings.retry_delay_minutes),
      });
      setSettings(updated);
      setSettingsModal(false);
      confetti({
        particleCount: 40,
        spread: 50,
        origin: { y: 0.7 },
        colors: ['#E47745', '#10B981'],
      });
    } catch (err) {
      console.error('Failed to save reminder settings:', err);
      alert('Failed to save reminder configuration. Please verify settings.');
    } finally {
      setSavingSettings(false);
    }
  };

  const handleProcessDue = async () => {
    setProcessingDue(true);
    setProcessResult(null);
    try {
      const res = await remindersService.processDue({ force_calling_window: true });
      setProcessResult(res);
      confetti({
        particleCount: 50,
        spread: 60,
        origin: { y: 0.7 },
        colors: ['#E47745', '#F0AD57', '#10B981'],
      });
      await loadData();
    } catch (err) {
      console.error('Failed to process due reminders:', err);
      alert('Failed to trigger outbound queue processing.');
    } finally {
      setProcessingDue(false);
    }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await remindersService.createReminder({
        ...newRem,
        scheduled_time: new Date(newRem.scheduled_time).toISOString(),
      });
      confetti({
        particleCount: 50,
        spread: 60,
        origin: { y: 0.7 },
        colors: ['#E47745', '#F0AD57', '#A78BFA'],
      });
      setCreateModal(false);
      setNewRem({ customer_id: '', reminder_type: 'call', scheduled_time: '', message: '' });
      await loadData();
    } catch (err) {
      console.error(err);
      alert('Failed to schedule reminder. Please verify fields.');
    }
  };

  const handleSendNow = async (id) => {
    setSendingId(id);
    try {
      await remindersService.sendReminder(id);
      confetti({
        particleCount: 40,
        spread: 50,
        origin: { y: 0.8 },
        colors: ['#F0AD57', '#E47745'],
      });
      await loadData();
    } catch (err) {
      console.error(err);
    } finally {
      setSendingId(null);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this scheduled notification from queue?')) return;
    try {
      await remindersService.deleteReminder(id);
      await loadData();
    } catch (err) {
      console.error(err);
    }
  };

  // Filtered list
  const filteredReminders = reminders.filter((rem) => {
    if (channelFilter !== 'all') {
      const type = rem.reminder_type === 'voice' ? 'call' : rem.reminder_type;
      if (type !== channelFilter) return false;
    }
    return true;
  });

  // KPIs
  const totalQueue = reminders.length;
  const pendingCount = reminders.filter((r) => ['scheduled', 'pending'].includes(r.status)).length;
  const sentCount = reminders.filter((r) => ['sent', 'completed'].includes(r.status)).length;
  const failedCount = reminders.filter((r) => r.status === 'failed').length;
  const callingCount = reminders.filter((r) => r.status === 'calling').length;
  const confirmedCount = reminders.filter((r) => (r.customer_response || '').toLowerCase().includes('confirm')).length;
  const deliveryRate = totalQueue > 0 ? Math.round((sentCount / totalQueue) * 100) : 100;

  const renderResponseBadge = (response) => {
    if (!response) return null;
    const resp = response.toLowerCase();
    let badgeColor = 'bg-graphite text-ivory/80 border-ivory/10';
    let label = response;

    if (resp.includes('confirm')) {
      badgeColor = 'bg-emerald-950/60 text-emerald-300 border-emerald-500/40';
      label = '✓ Confirmed by Customer';
    } else if (resp.includes('reschedule')) {
      badgeColor = 'bg-amber/20 text-amber-light border-amber/40';
      label = '⟳ Reschedule Requested';
    } else if (resp.includes('cancel')) {
      badgeColor = 'bg-rose-950/60 text-rose-300 border-rose-500/40';
      label = '✕ Cancelled by Customer';
    } else if (resp.includes('callback')) {
      badgeColor = 'bg-cyan-950/60 text-cyan-300 border-cyan-500/40';
      label = '☎ Callback Requested';
    } else if (resp.includes('wrong')) {
      badgeColor = 'bg-neutral-800 text-neutral-400 border-neutral-600';
      label = 'Wrong Number';
    } else if (resp.includes('no_response')) {
      badgeColor = 'bg-orange-950/50 text-orange-300 border-orange-500/30';
      label = 'No Answer';
    }

    return (
      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${badgeColor}`}>
        {label}
      </span>
    );
  };

  return (
    <div className="space-y-8 pb-12">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-charcoal via-graphite to-warmblack border border-white/10 p-6 sm:p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-amber/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
        <div className="absolute bottom-0 left-1/4 w-72 h-72 bg-burnt/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="p-2.5 rounded-xl bg-burnt/15 border border-burnt/30 text-burnt">
                <BellRing className="w-5 h-5 animate-pulse" />
              </span>
              <span className="text-xs font-semibold tracking-wider uppercase text-burnt">
                Automated AI Outbound Center
              </span>
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                <Zap className="w-3 h-3" /> Auto-Scheduler Active (24h & 2h)
              </span>
              <span className="hidden sm:flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-amber/15 border border-amber/30 text-amber">
                <Clock className="w-3 h-3" /> {settings.calling_start_time} - {settings.calling_end_time} Calling Window
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-ivory tracking-tight">
              Automated Reminders & Outbound AI Calling
            </h1>
            <p className="text-xs sm:text-sm text-mutedgrey max-w-xl">
              Proactive multi-lingual AI phone reminders with automatic confirmation, rescheduling, and cancellation
              intent classification in English, Tamil, and Tanglish.
            </p>
          </div>

          {/* Quick Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleProcessDue}
              disabled={processingDue}
              className="px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-emerald-900/30 hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50"
              title="Process all currently due reminders"
            >
              <Play className={`w-4 h-4 ${processingDue ? 'animate-spin' : ''}`} />
              {processingDue ? 'Processing Queue...' : 'Trigger Due Reminders'}
            </button>
            <button
              onClick={() => setSettingsModal(true)}
              className="px-4 py-2.5 rounded-xl bg-warmblack/80 hover:bg-graphite border border-white/10 hover:border-burnt/40 text-ivory font-bold text-xs flex items-center gap-2 transition-all"
            >
              <Sliders className="w-4 h-4 text-burnt" />
              Reminder Settings
            </button>
            <button
              onClick={() => setCreateModal(true)}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs flex items-center gap-2 shadow-lg shadow-burnt/20 hover:shadow-burnt/40 hover:scale-[1.02] active:scale-[0.98] transition-all"
            >
              <Plus className="w-4 h-4 stroke-[2.5]" />
              Queue Custom
            </button>
            <button
              onClick={loadData}
              className="p-2.5 rounded-xl bg-graphite/80 border border-white/10 text-ivory hover:text-burnt hover:border-burnt/30 transition-all"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Process Due Status Banner */}
        {processResult && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 p-3.5 rounded-2xl bg-emerald-950/60 border border-emerald-500/40 text-emerald-200 text-xs flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>
                Queue Run Complete: Processed <strong>{processResult.processed_count}</strong> reminders
                (Dispatched: <strong>{processResult.called_count}</strong>, Retried:{' '}
                <strong>{processResult.retried_count}</strong>, Deferred: <strong>{processResult.deferred_count}</strong>)
              </span>
            </div>
            <button
              onClick={() => setProcessResult(null)}
              className="text-emerald-400 hover:text-white font-mono text-xs px-2"
            >
              Dismiss
            </button>
          </motion.div>
        )}

        {/* Telemetry Metric Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-6 pt-6 border-t border-white/5">
          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <Clock className="w-3 h-3 text-burnt" /> Pending Queue
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-ivory mt-1">{pendingCount}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Dispatched
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-emerald-400 mt-1">{sentCount}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <ShieldCheck className="w-3 h-3 text-teal-400" /> Confirmed
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-teal-300 mt-1">{confirmedCount}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <AlertCircle className="w-3 h-3 text-rose-400" /> Failed
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-rose-400 mt-1">{failedCount}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <Zap className="w-3 h-3 text-lavender" /> Delivery Reliability
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-lavender mt-1">{deliveryRate}%</p>
          </div>
        </div>
      </div>

      {/* Control Ribbon (Status & Channel Filter) */}
      <div className="bg-charcoal/80 border border-graphite rounded-2xl p-4 backdrop-blur-md flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Status Filters */}
        <div className="flex flex-wrap items-center gap-1.5 w-full sm:w-auto">
          {[
            { id: 'all', label: 'All Reminders' },
            { id: 'scheduled', label: 'Scheduled' },
            { id: 'calling', label: 'Calling / In-Progress' },
            { id: 'sent', label: 'Completed' },
            { id: 'failed', label: 'Failed' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                statusFilter === tab.id
                  ? 'bg-burnt text-warmblack font-bold shadow-md shadow-burnt/20'
                  : 'bg-warmblack/60 text-mutedgrey hover:text-ivory border border-white/5'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Channel Selection */}
        <div className="flex items-center gap-2 self-end sm:self-auto">
          <span className="text-xs text-mutedgrey">Channel:</span>
          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            className="px-3 py-1.5 bg-warmblack/80 border border-graphite rounded-xl text-xs font-medium text-ivory focus:outline-none focus:border-burnt/50"
          >
            <option value="all">All Channels</option>
            <option value="call">AI Voice Call</option>
            <option value="sms">SMS Text</option>
            <option value="whatsapp">WhatsApp</option>
          </select>
        </div>
      </div>

      {/* Reminder Queue Timeline */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-24 space-y-4">
          <div className="w-10 h-10 border-3 border-burnt border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-mutedgrey animate-pulse font-mono tracking-wider">
            LOADING DISPATCH QUEUE...
          </p>
        </div>
      ) : filteredReminders.length === 0 ? (
        <div className="glass-panel p-12 text-center rounded-3xl border border-graphite space-y-4">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-burnt/10 border border-burnt/20 flex items-center justify-center text-burnt">
            <BellRing className="w-8 h-8" />
          </div>
          <h3 className="text-base font-bold text-ivory">No Reminders in Queue</h3>
          <p className="text-xs text-mutedgrey max-w-md mx-auto">
            All reminder broadcasts have been delivered or there are none scheduled. Auto-reminders
            are generated automatically when appointments are booked (24 hours and 2 hours prior).
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={() => setCreateModal(true)}
              className="px-5 py-2.5 rounded-xl bg-burnt hover:bg-burnt/90 text-warmblack font-bold text-xs transition-colors inline-flex items-center gap-2"
            >
              <Plus className="w-3.5 h-3.5" /> Queue Reminder
            </button>
            <button
              onClick={() => setSettingsModal(true)}
              className="px-5 py-2.5 rounded-xl bg-warmblack border border-graphite hover:border-white/20 text-ivory font-bold text-xs transition-colors inline-flex items-center gap-2"
            >
              <Sliders className="w-3.5 h-3.5 text-burnt" /> Configure Intervals
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredReminders.map((rem, idx) => {
            const timeObj = new Date(rem.scheduled_time);
            const timeStr = timeObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const dateStr = timeObj.toLocaleDateString(undefined, {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
            });
            const isCall = rem.reminder_type === 'call' || rem.reminder_type === 'voice';
            const isWhatsapp = rem.reminder_type === 'whatsapp';
            const isPending = ['scheduled', 'pending'].includes(rem.status);

            return (
              <motion.div
                key={rem.id || idx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.03 }}
                className="group glass-panel rounded-2xl border border-graphite hover:border-burnt/50 p-5 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                {/* Left: Channel Icon & Details */}
                <div className="flex items-start gap-4">
                  <div
                    className={`p-3 rounded-2xl border flex items-center justify-center shrink-0 ${
                      isCall
                        ? 'bg-burnt/15 border-burnt/30 text-burnt'
                        : isWhatsapp
                        ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
                        : 'bg-amber/15 border-amber/30 text-amber'
                    }`}
                  >
                    {isCall ? (
                      <PhoneCall className="w-5 h-5" />
                    ) : isWhatsapp ? (
                      <MessageSquare className="w-5 h-5" />
                    ) : (
                      <Smartphone className="w-5 h-5" />
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-mono font-bold uppercase text-ivory">
                        {isCall ? 'AI Voice Call' : isWhatsapp ? 'WhatsApp' : 'SMS Text'}
                      </span>
                      <span className="text-xs text-mutedgrey">•</span>
                      <span className="text-xs font-bold text-ivory">
                        {rem.customer?.name || rem.customer_name || 'Customer'}
                      </span>
                      {(rem.customer?.phone || rem.customer_phone) && (
                        <span className="text-xs font-mono text-mutedgrey">
                          ({rem.customer?.phone || rem.customer_phone})
                        </span>
                      )}
                      <Badge status={rem.status} />

                      {/* Interval Tag */}
                      {rem.interval_tag && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-burnt/15 border border-burnt/30 text-burnt">
                          {rem.interval_tag.toUpperCase()}
                        </span>
                      )}

                      {/* Response Classification */}
                      {renderResponseBadge(rem.customer_response)}

                      {/* Retry Badge */}
                      {rem.retry_count > 0 && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-amber/15 border border-amber/30 text-amber flex items-center gap-1">
                          <RotateCcw className="w-2.5 h-2.5" />
                          Retry {rem.retry_count}/{rem.max_retries || 3}
                        </span>
                      )}
                    </div>

                    {/* Message Content */}
                    <div className="p-3 rounded-xl bg-warmblack/70 border border-white/5 max-w-2xl">
                      <p className="text-xs text-ivory/90 leading-relaxed font-sans">
                        "{rem.message || 'Friendly reminder for your upcoming appointment.'}"
                      </p>
                      {rem.error_message && (
                        <div className="mt-2 text-[11px] text-rose-300 bg-rose-950/40 p-1.5 rounded-lg border border-rose-500/20 flex items-center gap-1.5">
                          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                          <span>{rem.error_message}</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-4 text-[11px] font-mono text-mutedgrey pt-1">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-burnt" />
                        Scheduled: {dateStr} at {timeStr}
                      </span>
                      {rem.sent_at && (
                        <span className="flex items-center gap-1 text-emerald-400">
                          <Check className="w-3 h-3" />
                          Dispatched: {new Date(rem.sent_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      )}
                      {rem.next_retry_at && rem.status === 'retrying' && (
                        <span className="flex items-center gap-1 text-amber">
                          <RotateCcw className="w-3 h-3" />
                          Next retry: {new Date(rem.next_retry_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-2.5 self-end md:self-auto shrink-0">
                  {isPending && (
                    <button
                      onClick={() => handleSendNow(rem.id)}
                      disabled={sendingId === rem.id}
                      className="px-4 py-2 rounded-xl bg-burnt hover:bg-burnt/90 text-warmblack font-bold text-xs flex items-center gap-1.5 shadow-md shadow-burnt/20 hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50"
                    >
                      <Send className={`w-3.5 h-3.5 ${sendingId === rem.id ? 'animate-spin' : ''}`} />
                      {sendingId === rem.id ? 'Dispatching...' : 'Dispatch Call Now'}
                    </button>
                  )}

                  <button
                    onClick={() => handleDelete(rem.id)}
                    className="p-2 rounded-xl bg-warmblack hover:bg-rose-500/15 border border-graphite hover:border-rose-500/30 text-mutedgrey hover:text-rose-400 transition-colors"
                    title="Remove Reminder"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Reminder Engine Settings Modal */}
      <Modal
        isOpen={settingsModal}
        onClose={() => setSettingsModal(false)}
        title="Automated Reminder Engine Configuration"
      >
        <form onSubmit={handleSaveSettings} className="space-y-4">
          <div className="p-3 bg-warmblack/70 rounded-xl border border-white/5 space-y-1">
            <p className="text-xs text-ivory font-bold flex items-center gap-2">
              <Zap className="w-4 h-4 text-burnt" /> Auto-Reminder Policy
            </p>
            <p className="text-[11px] text-mutedgrey leading-relaxed">
              When enabled, Vattara automatically creates reminder calls for newly booked appointments based
              on your configured hourly intervals, and reschedules or cancels them when the appointment changes.
            </p>
          </div>

          <div className="flex items-center justify-between p-3 rounded-xl bg-warmblack border border-graphite">
            <span className="text-xs font-semibold text-ivory">Enable Automated Reminders</span>
            <input
              type="checkbox"
              checked={settings.is_enabled}
              onChange={(e) => setSettings({ ...settings, is_enabled: e.target.checked })}
              className="w-4 h-4 text-burnt bg-charcoal rounded border-graphite focus:ring-burnt"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Reminder Intervals (Hours before appointment)
            </label>
            <input
              type="text"
              required
              placeholder="24,2"
              value={settings.reminder_intervals_hours}
              onChange={(e) => setSettings({ ...settings, reminder_intervals_hours: e.target.value })}
              className="glass-input w-full font-mono text-xs"
            />
            <p className="text-[10px] text-mutedgrey mt-1">
              Comma-separated hours (e.g. <code>24,2</code> generates a call 24 hours prior and 2 hours prior).
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                Calling Window Start
              </label>
              <input
                type="time"
                required
                value={settings.calling_start_time}
                onChange={(e) => setSettings({ ...settings, calling_start_time: e.target.value })}
                className="glass-input w-full font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                Calling Window End
              </label>
              <input
                type="time"
                required
                value={settings.calling_end_time}
                onChange={(e) => setSettings({ ...settings, calling_end_time: e.target.value })}
                className="glass-input w-full font-mono text-xs"
              />
            </div>
          </div>
          <p className="text-[10px] text-mutedgrey">
            Reminders outside this window are safely deferred to respect customer peace hours in your business timezone.
          </p>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                Max Retries
              </label>
              <input
                type="number"
                min="0"
                max="10"
                required
                value={settings.max_retries}
                onChange={(e) => setSettings({ ...settings, max_retries: e.target.value })}
                className="glass-input w-full font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                Retry Delay (Minutes)
              </label>
              <input
                type="number"
                min="1"
                max="180"
                required
                value={settings.retry_delay_minutes}
                onChange={(e) => setSettings({ ...settings, retry_delay_minutes: e.target.value })}
                className="glass-input w-full font-mono text-xs"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Default Dispatch Channel
            </label>
            <select
              value={settings.default_channel}
              onChange={(e) => setSettings({ ...settings, default_channel: e.target.value })}
              className="glass-input w-full text-xs"
            >
              <option value="voice">AI Voice Call (Conversational)</option>
              <option value="sms">SMS Text</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
          </div>

          <div className="pt-3 flex items-center justify-end gap-3 border-t border-graphite">
            <button
              type="button"
              onClick={() => setSettingsModal(false)}
              className="px-4 py-2 rounded-xl bg-warmblack border border-graphite text-xs font-semibold text-ivory hover:bg-graphite transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={savingSettings}
              className="px-5 py-2 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs shadow-lg shadow-burnt/20 hover:scale-[1.02] transition-all disabled:opacity-50"
            >
              {savingSettings ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </form>
      </Modal>

      {/* New Custom Reminder Modal */}
      <Modal
        isOpen={createModal}
        onClose={() => setCreateModal(false)}
        title="Schedule Omnichannel Reminder"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Select Customer Recipient
            </label>
            <select
              required
              value={newRem.customer_id}
              onChange={(e) => setNewRem({ ...newRem, customer_id: e.target.value })}
              className="glass-input w-full"
            >
              <option value="">Select a registered contact</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.phone})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Broadcast Delivery Channel
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'call', label: 'AI Voice Call', icon: PhoneCall },
                { id: 'sms', label: 'SMS Text', icon: Smartphone },
                { id: 'whatsapp', label: 'WhatsApp', icon: MessageSquare },
              ].map((ch) => {
                const Icon = ch.icon;
                const isSelected = newRem.reminder_type === ch.id;

                return (
                  <button
                    key={ch.id}
                    type="button"
                    onClick={() => setNewRem({ ...newRem, reminder_type: ch.id })}
                    className={`p-3 rounded-xl border text-center flex flex-col items-center justify-center gap-1.5 transition-all ${
                      isSelected
                        ? 'bg-burnt/15 border-burnt text-burnt font-bold'
                        : 'bg-warmblack border-graphite text-mutedgrey hover:text-ivory'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="text-xs">{ch.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Dispatch Date & Time
            </label>
            <input
              type="datetime-local"
              required
              value={newRem.scheduled_time}
              onChange={(e) => setNewRem({ ...newRem, scheduled_time: e.target.value })}
              className="glass-input w-full font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Message / Script Content
            </label>
            <textarea
              rows={3}
              required
              placeholder="Hi {Name}, your appointment is scheduled for tomorrow at 2:00 PM. Please reply YES to confirm..."
              value={newRem.message}
              onChange={(e) => setNewRem({ ...newRem, message: e.target.value })}
              className="glass-input w-full text-xs resize-none"
            />
          </div>

          <div className="pt-3 flex items-center justify-end gap-3 border-t border-graphite">
            <button
              type="button"
              onClick={() => setCreateModal(false)}
              className="px-4 py-2 rounded-xl bg-warmblack border border-graphite text-xs font-semibold text-ivory hover:bg-graphite transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs shadow-lg shadow-burnt/20 hover:scale-[1.02] transition-all"
            >
              Queue Reminder
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
