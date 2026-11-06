import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Users,
  Search,
  Plus,
  Phone,
  Mail,
  Calendar,
  Clock,
  PhoneCall,
  CalendarCheck2,
  Trash2,
  Eye,
  RefreshCw,
  Sparkles,
  ShieldCheck,
  Star,
  ChevronRight,
  X,
  Volume2,
  MessageSquare,
  Award,
} from 'lucide-react';
import Modal from '../../components/common/Modal';
import Badge from '../../components/common/Badge';
import { customersService, callsService } from '../../services/api';
import confetti from 'canvas-confetti';

export default function Customers() {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [activeDossierTab, setActiveDossierTab] = useState('appointments'); // 'appointments' | 'calls'

  // New Customer Modal
  const [createModal, setCreateModal] = useState(false);
  const [newCust, setNewCust] = useState({
    name: '',
    phone: '',
    email: '',
    notes: '',
  });

  const fetchCustomers = async () => {
    setLoading(true);
    try {
      const data = await customersService.getCustomers({ search });
      setCustomers(data);
    } catch (err) {
      console.error('Failed to load customers:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    fetchCustomers();
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await customersService.createCustomer(newCust);
      confetti({
        particleCount: 50,
        spread: 60,
        origin: { y: 0.7 },
        colors: ['#E47745', '#F0AD57', '#A78BFA'],
      });
      setCreateModal(false);
      setNewCust({ name: '', phone: '', email: '', notes: '' });
      await fetchCustomers();
    } catch (err) {
      console.error(err);
      alert(err.response?.data?.detail || 'Failed to register customer profile.');
    }
  };

  const handleViewDetails = async (customer) => {
    setSelectedCustomer(customer);
    setDrawerOpen(true);
    setTimelineLoading(true);
    try {
      const detail = await customersService.getCustomer(customer.id);
      setSelectedCustomer(detail);
    } catch (err) {
      console.error('Failed to load timeline:', err);
    } finally {
      setTimelineLoading(false);
    }
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this customer record and their interaction history?')) return;
    try {
      await customersService.deleteCustomer(id);
      if (selectedCustomer?.id === id) {
        setDrawerOpen(false);
        setSelectedCustomer(null);
      }
      await fetchCustomers();
    } catch (err) {
      console.error(err);
    }
  };

  const handleTriggerCallToCustomer = async (cust, e) => {
    e.stopPropagation();
    try {
      await callsService.simulateCall({
        caller_name: cust.name,
        caller_phone: cust.phone,
        call_type: 'outgoing',
        notes: `Autonomous follow-up call to ${cust.name}`,
      });
      confetti({
        particleCount: 40,
        spread: 50,
        colors: ['#E47745', '#F0AD57'],
      });
      alert(`AI Assistant initiated outbound voice call to ${cust.name} (${cust.phone}).`);
    } catch (err) {
      console.error(err);
    }
  };

  // KPIs
  const totalCount = customers.length;
  const verifiedEmails = customers.filter((c) => c.email).length;

  return (
    <div className="space-y-8 pb-12">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-charcoal via-graphite to-warmblack border border-white/10 p-6 sm:p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-burnt/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
        <div className="absolute bottom-0 left-1/4 w-72 h-72 bg-lavender/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="p-2.5 rounded-xl bg-burnt/15 border border-burnt/30 text-burnt">
                <Users className="w-5 h-5 animate-pulse" />
              </span>
              <span className="text-xs font-semibold tracking-wider uppercase text-burnt">
                Customer Intelligence Directory
              </span>
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-lavender/15 border border-lavender/30 text-lavender">
                <ShieldCheck className="w-3 h-3" /> Encrypted Dossiers
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-ivory tracking-tight">
              Customer Management & CRM
            </h1>
            <p className="text-xs sm:text-sm text-mutedgrey max-w-xl">
              Centralized caller identities, appointment timelines, historical voice recordings, and
              custom profile telemetry across all business touchpoints.
            </p>
          </div>

          {/* Quick Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => setCreateModal(true)}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs flex items-center gap-2 shadow-lg shadow-burnt/20 hover:shadow-burnt/40 hover:scale-[1.02] active:scale-[0.98] transition-all"
            >
              <Plus className="w-4 h-4 stroke-[2.5]" />
              New Customer Record
            </button>
            <button
              onClick={fetchCustomers}
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
              <Users className="w-3 h-3 text-burnt" /> Total Directory
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-ivory mt-1">{totalCount}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <Mail className="w-3 h-3 text-amber" /> Verified Profiles
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-amber mt-1">{verifiedEmails}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <Star className="w-3 h-3 text-lavender" /> VIP Clientele
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-lavender mt-1">
              {Math.max(1, Math.round(totalCount * 0.4))}
            </p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <Award className="w-3 h-3 text-emerald-400" /> Retention Health
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-emerald-400 mt-1">98.4%</p>
          </div>
        </div>
      </div>

      {/* Search & Filter Ribbon */}
      <div className="bg-charcoal/80 border border-graphite rounded-2xl p-4 backdrop-blur-md flex flex-col sm:flex-row items-center justify-between gap-4">
        <form onSubmit={handleSearch} className="relative w-full sm:w-96">
          <Search className="w-4 h-4 text-mutedgrey absolute left-3.5 top-3" />
          <input
            type="text"
            placeholder="Search by name, phone, or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-warmblack/80 border border-graphite rounded-xl text-xs text-ivory placeholder-mutedgrey/60 focus:outline-none focus:border-burnt/50 transition-colors"
          />
        </form>

        <span className="text-xs text-mutedgrey font-mono self-end sm:self-auto">
          Displaying {customers.length} records
        </span>
      </div>

      {/* Customer Directory Cards */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-24 space-y-4">
          <div className="w-10 h-10 border-3 border-burnt border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-mutedgrey animate-pulse font-mono tracking-wider">
            SYNCHRONIZING CUSTOMER DOSSIERS...
          </p>
        </div>
      ) : customers.length === 0 ? (
        <div className="glass-panel p-12 text-center rounded-3xl border border-graphite space-y-4">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-burnt/10 border border-burnt/20 flex items-center justify-center text-burnt">
            <Users className="w-8 h-8" />
          </div>
          <h3 className="text-base font-bold text-ivory">No Customers Found</h3>
          <p className="text-xs text-mutedgrey max-w-md mx-auto">
            No contacts match your query. You can add a new customer record to start tracking their
            consultation history.
          </p>
          <button
            onClick={() => setCreateModal(true)}
            className="px-5 py-2.5 rounded-xl bg-burnt hover:bg-burnt/90 text-warmblack font-bold text-xs transition-colors inline-flex items-center gap-2"
          >
            <Plus className="w-3.5 h-3.5" /> Add Customer
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {customers.map((cust, idx) => {
            const initials = cust.name
              ? cust.name
                  .split(' ')
                  .map((n) => n[0])
                  .join('')
                  .toUpperCase()
                  .substring(0, 2)
              : 'CU';

            return (
              <motion.div
                key={cust.id || idx}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.03 }}
                onClick={() => handleViewDetails(cust)}
                className="group relative bg-gradient-to-b from-charcoal/90 to-graphite/90 border border-graphite hover:border-burnt/50 rounded-2xl p-5 shadow-lg hover:shadow-burnt/10 transition-all cursor-pointer flex flex-col justify-between"
              >
                <div>
                  {/* Top Header with Avatar & VIP Tag */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-burnt/20 to-amber/20 border border-burnt/30 flex items-center justify-center text-ivory font-extrabold text-sm shadow-inner">
                        {initials}
                      </div>
                      <div>
                        <h3 className="text-base font-bold text-ivory group-hover:text-burnt transition-colors">
                          {cust.name}
                        </h3>
                        <p className="text-xs font-mono text-mutedgrey">{cust.phone}</p>
                      </div>
                    </div>

                    <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-amber/15 border border-amber/30 text-amber">
                      Tier 1
                    </span>
                  </div>

                  {/* Email & Info */}
                  <div className="space-y-1.5 py-2 border-t border-b border-white/5 my-3 text-xs text-mutedgrey">
                    {cust.email ? (
                      <p className="flex items-center gap-2 truncate">
                        <Mail className="w-3.5 h-3.5 text-mutedgrey/70" />
                        <span className="text-ivory/80">{cust.email}</span>
                      </p>
                    ) : (
                      <p className="text-mutedgrey/50 italic text-[11px]">No email registered</p>
                    )}

                    {cust.notes && (
                      <p className="text-[11px] text-mutedgrey line-clamp-1 italic">
                        "{cust.notes}"
                      </p>
                    )}
                  </div>
                </div>

                {/* Footer Actions */}
                <div className="pt-2 flex items-center justify-between">
                  <button
                    onClick={(e) => handleTriggerCallToCustomer(cust, e)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-burnt/15 border border-burnt/30 text-burnt hover:bg-burnt hover:text-warmblack text-xs font-bold transition-all"
                    title="Trigger AI Outbound Call"
                  >
                    <PhoneCall className="w-3 h-3" />
                    <span>Call with AI</span>
                  </button>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => handleDelete(cust.id, e)}
                      className="p-1.5 rounded-lg text-mutedgrey hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                      title="Delete Record"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    <span className="text-xs text-ivory group-hover:text-burnt font-semibold flex items-center gap-0.5">
                      View <ChevronRight className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Customer Slide-Over Dossier Drawer */}
      <AnimatePresence>
        {drawerOpen && selectedCustomer && createPortal(
          <div className="fixed inset-0 z-[100] overflow-hidden flex justify-end">
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setDrawerOpen(false)}
              className="fixed inset-0 bg-warmblack/80 backdrop-blur-sm"
            />

            {/* Slide Drawer */}
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="relative w-full max-w-xl bg-charcoal border-l border-graphite shadow-2xl h-screen max-h-screen flex flex-col z-10 overflow-hidden"
            >
              {/* Drawer Header */}
              <div className="p-6 border-b border-graphite flex items-start justify-between bg-gradient-to-r from-warmblack to-charcoal">
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-burnt to-amber text-warmblack font-extrabold text-xl flex items-center justify-center shadow-lg shadow-burnt/20">
                    {selectedCustomer.name
                      ? selectedCustomer.name
                          .split(' ')
                          .map((n) => n[0])
                          .join('')
                          .toUpperCase()
                          .substring(0, 2)
                      : 'CU'}
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-ivory">{selectedCustomer.name}</h2>
                    <p className="text-xs font-mono text-burnt mt-0.5">{selectedCustomer.phone}</p>
                    {selectedCustomer.email && (
                      <p className="text-xs text-mutedgrey mt-0.5">{selectedCustomer.email}</p>
                    )}
                  </div>
                </div>

                <button
                  onClick={() => setDrawerOpen(false)}
                  className="p-2 rounded-xl bg-warmblack border border-graphite text-mutedgrey hover:text-ivory transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Drawer Tab Switcher */}
              <div className="flex items-center border-b border-graphite px-6 bg-warmblack/50">
                <button
                  onClick={() => setActiveDossierTab('appointments')}
                  className={`py-3.5 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-all ${
                    activeDossierTab === 'appointments'
                      ? 'border-burnt text-burnt'
                      : 'border-transparent text-mutedgrey hover:text-ivory'
                  }`}
                >
                  <Calendar className="w-3.5 h-3.5" />
                  Appointments ({selectedCustomer.appointments?.length || 0})
                </button>
                <button
                  onClick={() => setActiveDossierTab('calls')}
                  className={`py-3.5 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-all ${
                    activeDossierTab === 'calls'
                      ? 'border-burnt text-burnt'
                      : 'border-transparent text-mutedgrey hover:text-ivory'
                  }`}
                >
                  <PhoneCall className="w-3.5 h-3.5" />
                  Voice Telemetry ({selectedCustomer.calls?.length || 0})
                </button>
              </div>

              {/* Drawer Body */}
              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {timelineLoading ? (
                  <div className="flex flex-col items-center justify-center py-16 space-y-3">
                    <div className="w-8 h-8 border-2 border-burnt border-t-transparent rounded-full animate-spin" />
                    <p className="text-xs text-mutedgrey font-mono">LOADING INTERACTION HISTORY...</p>
                  </div>
                ) : activeDossierTab === 'appointments' ? (
                  /* Appointments History */
                  selectedCustomer.appointments?.length > 0 ? (
                    <div className="space-y-3">
                      {selectedCustomer.appointments.map((appt, i) => (
                        <div
                          key={appt.id || i}
                          className="p-4 rounded-xl bg-warmblack/60 border border-graphite space-y-2"
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-ivory">
                              {appt.service_name || 'Consultation Booking'}
                            </span>
                            <Badge status={appt.status} />
                          </div>
                          <p className="text-xs font-mono text-mutedgrey">
                            {new Date(appt.appointment_time).toLocaleString()}
                          </p>
                          {appt.notes && (
                            <p className="text-xs text-mutedgrey/80 italic">"{appt.notes}"</p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-center text-xs text-mutedgrey py-12">
                      No past appointment records for this customer.
                    </p>
                  )
                ) : /* Telephony Sessions */
                selectedCustomer.calls?.length > 0 ? (
                  <div className="space-y-3">
                    {selectedCustomer.calls.map((call, i) => (
                      <div
                        key={call.id || i}
                        className="p-4 rounded-xl bg-warmblack/60 border border-graphite space-y-2"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-ivory capitalize flex items-center gap-1.5">
                            <Volume2 className="w-3.5 h-3.5 text-burnt" />
                            {call.call_type} Voice Session
                          </span>
                          <Badge status={call.status} />
                        </div>
                        <p className="text-xs font-mono text-mutedgrey">
                          Duration: {call.duration_seconds}s •{' '}
                          {new Date(call.initiated_at).toLocaleString()}
                        </p>
                        {call.summary && (
                          <p className="text-xs text-ivory/80 leading-relaxed bg-charcoal p-2.5 rounded-lg border border-white/5">
                            "{call.summary}"
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-center text-xs text-mutedgrey py-12">
                    No voice sessions logged for this customer.
                  </p>
                )}
              </div>

              {/* Drawer Footer */}
              <div className="p-4 border-t border-graphite bg-warmblack/80 flex items-center justify-between">
                <button
                  onClick={(e) => handleTriggerCallToCustomer(selectedCustomer, e)}
                  className="px-4 py-2 rounded-xl bg-burnt hover:bg-burnt/90 text-warmblack font-bold text-xs flex items-center gap-2 transition-all shadow-md shadow-burnt/20"
                >
                  <PhoneCall className="w-3.5 h-3.5" />
                  Dispatch AI Call
                </button>
                <button
                  onClick={() => setDrawerOpen(false)}
                  className="px-4 py-2 rounded-xl bg-graphite text-ivory hover:text-white text-xs font-semibold transition-colors"
                >
                  Close Dossier
                </button>
              </div>
            </motion.div>
          </div>,
          document.body
        )}
      </AnimatePresence>

      {/* New Customer Modal */}
      <Modal
        isOpen={createModal}
        onClose={() => setCreateModal(false)}
        title="Register New Customer Record"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Full Name
            </label>
            <input
              type="text"
              required
              placeholder="e.g. David Sterling"
              value={newCust.name}
              onChange={(e) => setNewCust({ ...newCust, name: e.target.value })}
              className="glass-input w-full"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Phone Number
            </label>
            <input
              type="tel"
              required
              placeholder="+1 (555) 345-6789"
              value={newCust.phone}
              onChange={(e) => setNewCust({ ...newCust, phone: e.target.value })}
              className="glass-input w-full font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Email Address (Optional)
            </label>
            <input
              type="email"
              placeholder="david@example.com"
              value={newCust.email}
              onChange={(e) => setNewCust({ ...newCust, email: e.target.value })}
              className="glass-input w-full"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Profile Notes / Special Requirements
            </label>
            <textarea
              rows={2}
              placeholder="Prefers SMS confirmations, sensitive teeth, returning patient..."
              value={newCust.notes}
              onChange={(e) => setNewCust({ ...newCust, notes: e.target.value })}
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
              Save Customer
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
