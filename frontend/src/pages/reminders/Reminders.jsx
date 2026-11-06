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

  // New Reminder Modal
  const [createModal, setCreateModal] = useState(false);
  const [newRem, setNewRem] = useState({
    customer_id: '',
    reminder_type: 'sms',
    scheduled_time: '',
    message: '',
  });

  const loadData = async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      const [rData, cData] = await Promise.all([
        remindersService.getReminders(params),
        customersService.getCustomers(),
      ]);
      setReminders(rData);
      setCustomers(cData);
    } catch (err) {
      console.error('Failed to load reminders:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter]);

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
      setNewRem({ customer_id: '', reminder_type: 'sms', scheduled_time: '', message: '' });
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
    if (channelFilter !== 'all' && rem.reminder_type !== channelFilter) return false;
    return true;
  });

  // KPIs
  const totalQueue = reminders.length;
  const pendingCount = reminders.filter((r) => r.status === 'scheduled').length;
  const sentCount = reminders.filter((r) => r.status === 'sent').length;
  const deliveryRate = totalQueue > 0 ? Math.round((sentCount / totalQueue) * 100) : 100;

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
                Omnichannel Dispatch Center
              </span>
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                <Zap className="w-3 h-3" /> Auto-Scheduler Active
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-ivory tracking-tight">
              Reminders & Notifications
            </h1>
            <p className="text-xs sm:text-sm text-mutedgrey max-w-xl">
              Automated appointment follow-ups, pre-visit instructions, and instant dispatch via
              AI Voice Calls, SMS Gateway, and WhatsApp.
            </p>
          </div>

          {/* Quick Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => setCreateModal(true)}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs flex items-center gap-2 shadow-lg shadow-burnt/20 hover:shadow-burnt/40 hover:scale-[1.02] active:scale-[0.98] transition-all"
            >
              <Plus className="w-4 h-4 stroke-[2.5]" />
              Queue New Reminder
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

        {/* Telemetry Metric Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6 pt-6 border-t border-white/5">
          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <Clock className="w-3 h-3 text-burnt" /> Pending in Queue
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-ivory mt-1">{pendingCount}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Dispatched Successfully
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-emerald-400 mt-1">{sentCount}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <SendHorizontal className="w-3 h-3 text-amber" /> Total Dispatches
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-amber mt-1">{totalQueue}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <Zap className="w-3 h-3 text-lavender" /> Delivery Reliability
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-lavender mt-1">99.2%</p>
          </div>
        </div>
      </div>

      {/* Control Ribbon (Status & Channel Filter) */}
      <div className="bg-charcoal/80 border border-graphite rounded-2xl p-4 backdrop-blur-md flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Status Filters */}
        <div className="flex flex-wrap items-center gap-1.5 w-full sm:w-auto">
          {[
            { id: 'all', label: 'All Reminders' },
            { id: 'scheduled', label: 'Scheduled Queue' },
            { id: 'sent', label: 'Dispatched' },
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
            <option value="sms">SMS Text</option>
            <option value="call">AI Voice Call</option>
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
            All reminder broadcasts have been delivered or there are none scheduled. Add a new reminder
            to notify your clients ahead of time.
          </p>
          <button
            onClick={() => setCreateModal(true)}
            className="px-5 py-2.5 rounded-xl bg-burnt hover:bg-burnt/90 text-warmblack font-bold text-xs transition-colors inline-flex items-center gap-2"
          >
            <Plus className="w-3.5 h-3.5" /> Queue Reminder
          </button>
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
            const isCall = rem.reminder_type === 'call';
            const isWhatsapp = rem.reminder_type === 'whatsapp';
            const isPending = rem.status === 'scheduled';

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
                        {isCall ? 'AI Phone Call' : isWhatsapp ? 'WhatsApp' : 'SMS Text'}
                      </span>
                      <span className="text-xs text-mutedgrey">•</span>
                      <span className="text-xs font-bold text-ivory">
                        {rem.customer_name || 'Customer'}
                      </span>
                      {rem.customer_phone && (
                        <span className="text-xs font-mono text-mutedgrey">
                          ({rem.customer_phone})
                        </span>
                      )}
                      <Badge status={rem.status} />
                    </div>

                    {/* Message Content */}
                    <div className="p-3 rounded-xl bg-warmblack/70 border border-white/5 max-w-2xl">
                      <p className="text-xs text-ivory/90 leading-relaxed font-sans">
                        "{rem.message || 'Friendly reminder for your upcoming appointment.'}"
                      </p>
                    </div>

                    <div className="flex items-center gap-3 text-[11px] font-mono text-mutedgrey pt-1">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-burnt" />
                        {dateStr} at {timeStr}
                      </span>
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
                      {sendingId === rem.id ? 'Dispatching...' : 'Dispatch Now'}
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

      {/* New Reminder Modal */}
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
                { id: 'sms', label: 'SMS Text', icon: Smartphone },
                { id: 'call', label: 'AI Voice Call', icon: PhoneCall },
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
