import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CalendarDays,
  Plus,
  Clock,
  User,
  Phone,
  CheckCircle2,
  XCircle,
  Calendar,
  Sparkles,
  RefreshCw,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
  Filter,
  Check,
  RotateCcw,
  Tag,
  Stethoscope,
  Scissors,
  Sparkle,
  Layers,
  ListOrdered,
} from 'lucide-react';
import Badge from '../../components/common/Badge';
import Modal from '../../components/common/Modal';
import { appointmentsService, customersService, assistantService } from '../../services/api';
import { useDashboardWebSocket } from '../../context/DashboardWebSocketContext';
import confetti from 'canvas-confetti';

export default function Appointments() {
  const { subscribe, isConnected } = useDashboardWebSocket();
  const [appointments, setAppointments] = useState([]);
  const [services, setServices] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [viewMode, setViewMode] = useState('agenda'); // 'agenda' or 'grid'
  const [selectedDate, setSelectedDate] = useState(new Date());

  const tomorrowStr = new Date(Date.now() + 86400000).toISOString().split('T')[0];
  const [staffList, setStaffList] = useState([]);

  // New Appointment Modal & Slot Availability
  const [createModal, setCreateModal] = useState(false);
  const [bookingDate, setBookingDate] = useState(tomorrowStr);
  const [slotsData, setSlotsData] = useState({ is_open: true, slots: [], available_slots_count: 0 });
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [bookingError, setBookingError] = useState(null);
  const [newAppt, setNewAppt] = useState({
    customer_name: '',
    customer_phone: '',
    service_id: '',
    staff_id: '',
    appointment_time: '',
    notes: '',
    source: 'dashboard',
  });

  // Reschedule Modal & Slot Availability
  const [rescheduleModal, setRescheduleModal] = useState(false);
  const [selectedAppt, setSelectedAppt] = useState(null);
  const [rescheduleDate, setRescheduleDate] = useState(tomorrowStr);
  const [rescheduleSlots, setRescheduleSlots] = useState({ is_open: true, slots: [] });
  const [rescheduleLoading, setRescheduleLoading] = useState(false);
  const [rescheduleReason, setRescheduleReason] = useState('');
  const [rescheduleError, setRescheduleError] = useState(null);
  const [newTime, setNewTime] = useState('');

  const loadSlots = async (dateStr, serviceId, staffId) => {
    if (!dateStr) return;
    setSlotsLoading(true);
    setBookingError(null);
    try {
      const res = await appointmentsService.getAvailableSlots(dateStr, serviceId || null, staffId || null);
      setSlotsData(res || { is_open: false, slots: [] });
    } catch (err) {
      console.error('Failed to load slots:', err);
      setSlotsData({ is_open: false, slots: [] });
    } finally {
      setSlotsLoading(false);
    }
  };

  const loadRescheduleSlots = async (dateStr, serviceId, staffId) => {
    if (!dateStr) return;
    setRescheduleLoading(true);
    setRescheduleError(null);
    try {
      const res = await appointmentsService.getAvailableSlots(dateStr, serviceId || null, staffId || null);
      setRescheduleSlots(res || { is_open: false, slots: [] });
    } catch (err) {
      console.error('Failed to load reschedule slots:', err);
      setRescheduleSlots({ is_open: false, slots: [] });
    } finally {
      setRescheduleLoading(false);
    }
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      const [apptsData, srvData, custData, staffData] = await Promise.all([
        appointmentsService.getAppointments(params),
        assistantService.getServices(),
        customersService.getCustomers(),
        appointmentsService.getStaff(),
      ]);
      setAppointments(apptsData);
      setServices(srvData);
      setCustomers(custData);
      setStaffList(staffData || []);
    } catch (err) {
      console.error('Failed to load appointments:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter]);

  // Real-time WebSocket event listeners
  useEffect(() => {
    const unsubCreated = subscribe('APPOINTMENT_CREATED', () => {
      loadData();
    });
    const unsubUpdated = subscribe('APPOINTMENT_UPDATED', () => {
      loadData();
    });
    return () => {
      unsubCreated();
      unsubUpdated();
    };
  }, [subscribe]);

  const handleOpenCreateModal = () => {
    setBookingError(null);
    setSelectedSlot(null);
    setCreateModal(true);
    loadSlots(bookingDate, newAppt.service_id, newAppt.staff_id);
  };

  const handleOpenRescheduleModal = (appt) => {
    setSelectedAppt(appt);
    setNewTime('');
    setRescheduleError(null);
    setRescheduleReason('');
    setRescheduleModal(true);
    loadRescheduleSlots(rescheduleDate, appt.service_id, appt.staff_id);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setBookingError(null);
    if (!newAppt.appointment_time) {
      setBookingError('Please select an available time slot from the schedule.');
      return;
    }
    try {
      await appointmentsService.createAppointment({
        ...newAppt,
        customer_id: 'new',
        appointment_time: new Date(newAppt.appointment_time).toISOString(),
      });
      confetti({
        particleCount: 60,
        spread: 70,
        origin: { y: 0.7 },
        colors: ['#E47745', '#F0AD57', '#A78BFA'],
      });
      setCreateModal(false);
      setNewAppt({
        customer_name: '',
        customer_phone: '',
        service_id: '',
        staff_id: '',
        appointment_time: '',
        notes: '',
        source: 'dashboard',
      });
      setSelectedSlot(null);
      await loadData();
    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.detail || 'Failed to book appointment. Please verify details.';
      setBookingError(msg);
    }
  };

  const handleReschedule = async (e) => {
    e.preventDefault();
    if (!selectedAppt || !newTime) {
      setRescheduleError('Please choose an available time slot.');
      return;
    }
    setRescheduleError(null);
    try {
      await appointmentsService.rescheduleAppointment(selectedAppt.id, {
        new_appointment_time: new Date(newTime).toISOString(),
        reason: rescheduleReason || 'Customer requested reschedule',
      });
      confetti({
        particleCount: 40,
        spread: 50,
        colors: ['#F0AD57', '#A78BFA'],
      });
      setRescheduleModal(false);
      setSelectedAppt(null);
      setNewTime('');
      setRescheduleReason('');
      await loadData();
    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.detail || 'Failed to reschedule appointment.';
      setRescheduleError(msg);
    }
  };

  const handleCancel = async (id) => {
    if (!window.confirm('Cancel this scheduled appointment?')) return;
    try {
      await appointmentsService.cancelAppointment(id);
      await loadData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleComplete = async (id) => {
    try {
      await appointmentsService.updateAppointment(id, { status: 'completed' });
      await loadData();
    } catch (err) {
      console.error(err);
    }
  };

  // Generate 7-day strip centered around selected date
  const getWeekDays = () => {
    const days = [];
    const base = new Date(selectedDate);
    base.setDate(base.getDate() - 3);
    for (let i = 0; i < 7; i++) {
      const d = new Date(base);
      d.setDate(base.getDate() + i);
      days.push(d);
    }
    return days;
  };

  const weekDays = getWeekDays();

  // Metrics
  const totalAppts = appointments.length;
  const upcomingCount = appointments.filter((a) =>
    ['scheduled', 'confirmed', 'rescheduled'].includes(a.status)
  ).length;
  const completedCount = appointments.filter((a) => a.status === 'completed').length;
  const cancelledCount = appointments.filter((a) => a.status === 'cancelled').length;
  const fulfillmentRate =
    totalAppts > 0 ? Math.round((completedCount / (totalAppts - cancelledCount || 1)) * 100) : 100;

  return (
    <div className="space-y-8 pb-12">
      {/* Top Header / Control Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-charcoal via-graphite to-warmblack border border-white/10 p-6 sm:p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-burnt/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
        <div className="absolute bottom-0 left-1/4 w-72 h-72 bg-amber/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="p-2.5 rounded-xl bg-burnt/15 border border-burnt/30 text-burnt">
                <CalendarDays className="w-5 h-5 animate-pulse" />
              </span>
              <span className="text-xs font-semibold tracking-wider uppercase text-burnt">
                Calendar & Dispatch Agenda
              </span>
              <span className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono ${
                isConnected
                  ? 'bg-amber/15 border border-amber/30 text-amber'
                  : 'bg-mutedgrey/10 border border-mutedgrey/20 text-mutedgrey'
              }`}>
                <Clock className="w-3 h-3" />
                {isConnected ? 'Realtime Slot Sync' : 'Sync Paused'}
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-ivory tracking-tight">
              Appointment Management
            </h1>
            <p className="text-xs sm:text-sm text-mutedgrey max-w-xl">
              Unified schedule coordinator with autonomous AI call bookings, manual walk-in slots,
              practitioner assignments, and instant rescheduling workflows.
            </p>
          </div>

          {/* Quick Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={handleOpenCreateModal}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs flex items-center gap-2 shadow-lg shadow-burnt/20 hover:shadow-burnt/40 hover:scale-[1.02] active:scale-[0.98] transition-all"
            >
              <Plus className="w-4 h-4 stroke-[2.5]" />
              Schedule Appointment
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
              <Clock className="w-3 h-3 text-burnt" /> Active / Upcoming
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-ivory mt-1">{upcomingCount}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Completed
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-emerald-400 mt-1">{completedCount}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <XCircle className="w-3 h-3 text-rose-400" /> Cancelled
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-rose-400 mt-1">{cancelledCount}</p>
          </div>

          <div className="bg-warmblack/50 border border-white/5 rounded-2xl p-3.5 backdrop-blur-sm">
            <p className="text-[10px] uppercase font-bold text-mutedgrey flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-lavender" /> Fulfillment Rate
            </p>
            <p className="text-lg sm:text-xl font-extrabold text-lavender mt-1">{fulfillmentRate}%</p>
          </div>
        </div>
      </div>

      {/* Interactive Week Strip */}
      <div className="glass-panel rounded-2xl border border-graphite p-4">
        <div className="flex items-center justify-between mb-3 text-xs text-mutedgrey font-semibold">
          <div className="flex items-center gap-2 text-ivory">
            <Calendar className="w-4 h-4 text-burnt" />
            <span>
              {selectedDate.toLocaleDateString(undefined, {
                month: 'long',
                year: 'numeric',
              })}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                const prev = new Date(selectedDate);
                prev.setDate(prev.getDate() - 7);
                setSelectedDate(prev);
              }}
              className="p-1 rounded-lg bg-warmblack hover:bg-graphite text-ivory transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setSelectedDate(new Date())}
              className="px-2.5 py-1 rounded-lg bg-warmblack hover:bg-graphite text-[10px] font-mono text-ivory transition-colors"
            >
              Today
            </button>
            <button
              onClick={() => {
                const next = new Date(selectedDate);
                next.setDate(next.getDate() + 7);
                setSelectedDate(next);
              }}
              className="p-1 rounded-lg bg-warmblack hover:bg-graphite text-ivory transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 7-Day Day Pills */}
        <div className="grid grid-cols-7 gap-2 sm:gap-3">
          {weekDays.map((d, idx) => {
            const isSelected = d.toDateString() === selectedDate.toDateString();
            const isToday = d.toDateString() === new Date().toDateString();

            return (
              <button
                key={idx}
                onClick={() => setSelectedDate(d)}
                className={`flex flex-col items-center justify-center p-2.5 sm:p-3 rounded-2xl border transition-all ${
                  isSelected
                    ? 'bg-gradient-to-b from-burnt to-burnt/80 border-burnt text-warmblack font-bold shadow-lg shadow-burnt/20 scale-[1.03]'
                    : isToday
                    ? 'bg-graphite/70 border-burnt/40 text-burnt hover:border-burnt'
                    : 'bg-warmblack/50 border-white/5 text-mutedgrey hover:text-ivory hover:border-graphite'
                }`}
              >
                <span className="text-[10px] uppercase font-bold tracking-wider">
                  {d.toLocaleDateString(undefined, { weekday: 'short' })}
                </span>
                <span
                  className={`text-base sm:text-lg font-extrabold mt-0.5 ${
                    isSelected ? 'text-warmblack' : isToday ? 'text-burnt' : 'text-ivory'
                  }`}
                >
                  {d.getDate()}
                </span>
                {isToday && !isSelected && (
                  <span className="w-1.5 h-1.5 rounded-full bg-burnt mt-1" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Filter and View Ribbon */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-charcoal/80 border border-graphite rounded-2xl p-4 backdrop-blur-md">
        {/* Status Tab Pills */}
        <div className="flex flex-wrap items-center gap-1.5 w-full sm:w-auto">
          {[
            { id: 'all', label: 'All Slots' },
            { id: 'scheduled', label: 'Scheduled' },
            { id: 'confirmed', label: 'Confirmed' },
            { id: 'completed', label: 'Completed' },
            { id: 'cancelled', label: 'Cancelled' },
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

        {/* View Mode Toggle */}
        <div className="flex items-center gap-1 bg-warmblack/60 p-1 rounded-xl border border-graphite self-end sm:self-auto">
          <button
            onClick={() => setViewMode('agenda')}
            className={`p-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              viewMode === 'agenda'
                ? 'bg-burnt text-warmblack shadow-sm font-bold'
                : 'text-mutedgrey hover:text-ivory'
            }`}
          >
            <ListOrdered className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Agenda</span>
          </button>
          <button
            onClick={() => setViewMode('grid')}
            className={`p-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              viewMode === 'grid'
                ? 'bg-burnt text-warmblack shadow-sm font-bold'
                : 'text-mutedgrey hover:text-ivory'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Cards</span>
          </button>
        </div>
      </div>

      {/* Appointment List / Agenda Timeline */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-24 space-y-4">
          <div className="w-10 h-10 border-3 border-burnt border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-mutedgrey animate-pulse font-mono tracking-wider">
            LOADING CALENDAR SCHEDULE...
          </p>
        </div>
      ) : appointments.length === 0 ? (
        <div className="glass-panel p-12 text-center rounded-3xl border border-graphite space-y-4">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-burnt/10 border border-burnt/20 flex items-center justify-center text-burnt">
            <CalendarDays className="w-8 h-8" />
          </div>
          <h3 className="text-base font-bold text-ivory">No Appointments in this View</h3>
          <p className="text-xs text-mutedgrey max-w-md mx-auto">
            There are no appointment records matching the current filter. Book a new appointment or
            switch filters to view other slots.
          </p>
          <button
            onClick={handleOpenCreateModal}
            className="px-5 py-2.5 rounded-xl bg-burnt hover:bg-burnt/90 text-warmblack font-bold text-xs transition-colors inline-flex items-center gap-2"
          >
            <Plus className="w-3.5 h-3.5" /> Schedule New
          </button>
        </div>
      ) : viewMode === 'agenda' ? (
        /* Agenda Timeline Flow */
        <div className="space-y-4">
          {appointments.map((appt, idx) => {
            const timeObj = new Date(appt.appointment_time);
            const timeStr = timeObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const dateStr = timeObj.toLocaleDateString(undefined, {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
            });

            return (
              <motion.div
                key={appt.id || idx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.03 }}
                className="group glass-panel rounded-2xl border border-graphite hover:border-burnt/50 p-4 sm:p-5 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                {/* Time Indicator & Customer */}
                <div className="flex items-start sm:items-center gap-4">
                  <div className="flex flex-col items-center justify-center p-3 rounded-xl bg-warmblack/80 border border-white/5 min-w-[85px] text-center">
                    <span className="text-[11px] font-bold text-burnt uppercase tracking-wider">
                      {dateStr}
                    </span>
                    <span className="text-sm font-extrabold text-ivory font-mono mt-0.5">
                      {timeStr}
                    </span>
                  </div>

                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-bold text-ivory group-hover:text-burnt transition-colors">
                        {appt.customer_name || 'Walk-in Customer'}
                      </h3>
                      <Badge status={appt.status} />
                      {appt.source === 'ai_call' && (
                        <span className="px-2 py-0.5 rounded-md text-[9px] font-mono bg-burnt/15 border border-burnt/30 text-burnt font-bold">
                          AI Booked
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-3 text-xs text-mutedgrey">
                      <span className="flex items-center gap-1 font-mono">
                        <Phone className="w-3 h-3 text-mutedgrey" />
                        {appt.customer_phone || '+1 (555) 000-0000'}
                      </span>
                      {appt.service_name && (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-graphite text-ivory text-[11px]">
                          <Tag className="w-3 h-3 text-amber" />
                          {appt.service_name}
                        </span>
                      )}
                    </div>

                    {appt.notes && (
                      <p className="text-xs text-mutedgrey/80 line-clamp-1 italic">
                        "{appt.notes}"
                      </p>
                    )}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center gap-2 self-end md:self-auto">
                  {appt.status !== 'completed' && appt.status !== 'cancelled' && (
                    <>
                      <button
                        onClick={() => handleComplete(appt.id)}
                        className="px-3 py-1.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 text-xs font-semibold flex items-center gap-1 transition-all"
                        title="Mark Completed"
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">Complete</span>
                      </button>

                      <button
                        onClick={() => handleOpenRescheduleModal(appt)}
                        className="px-3 py-1.5 rounded-xl bg-warmblack hover:bg-graphite border border-graphite text-ivory text-xs font-semibold flex items-center gap-1 transition-all"
                        title="Reschedule"
                      >
                        <RotateCcw className="w-3.5 h-3.5 text-amber" />
                        <span className="hidden sm:inline">Reschedule</span>
                      </button>

                      <button
                        onClick={() => handleCancel(appt.id)}
                        className="p-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-400 text-xs transition-all"
                        title="Cancel Appointment"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      ) : (
        /* Card Grid View */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {appointments.map((appt, idx) => {
            const timeObj = new Date(appt.appointment_time);
            const timeStr = timeObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const dateStr = timeObj.toLocaleDateString(undefined, {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
            });

            return (
              <div
                key={appt.id || idx}
                className="group relative bg-gradient-to-b from-charcoal/90 to-graphite/90 border border-graphite hover:border-burnt/50 rounded-2xl p-5 shadow-lg transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[10px] font-mono text-burnt font-bold uppercase tracking-wider">
                      {dateStr} • {timeStr}
                    </span>
                    <Badge status={appt.status} />
                  </div>

                  <h3 className="text-base font-bold text-ivory group-hover:text-burnt transition-colors">
                    {appt.customer_name || 'Walk-in Customer'}
                  </h3>

                  <p className="text-xs font-mono text-mutedgrey mt-1">{appt.customer_phone}</p>

                  <div className="mt-3 py-2 px-3 rounded-xl bg-warmblack/60 border border-white/5 flex items-center justify-between">
                    <span className="text-xs font-semibold text-ivory flex items-center gap-1.5">
                      <Tag className="w-3.5 h-3.5 text-amber" />
                      {appt.service_name || 'General Appointment'}
                    </span>
                    {appt.source === 'ai_call' && (
                      <span className="text-[9px] font-mono font-bold text-burnt bg-burnt/10 px-1.5 py-0.5 rounded">
                        AI Agent
                      </span>
                    )}
                  </div>

                  {appt.notes && (
                    <p className="text-xs text-mutedgrey/70 mt-3 italic line-clamp-2">
                      "{appt.notes}"
                    </p>
                  )}
                </div>

                <div className="mt-5 pt-3 border-t border-white/5 flex items-center justify-between gap-2">
                  {appt.status !== 'completed' && appt.status !== 'cancelled' ? (
                    <>
                      <button
                        onClick={() => handleOpenRescheduleModal(appt)}
                        className="text-xs text-amber hover:text-amber/80 font-semibold flex items-center gap-1"
                      >
                        <RotateCcw className="w-3 h-3" /> Reschedule
                      </button>

                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleComplete(appt.id)}
                          className="p-1.5 rounded-lg bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 transition-colors"
                          title="Complete"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleCancel(appt.id)}
                          className="p-1.5 rounded-lg bg-rose-500/15 text-rose-400 hover:bg-rose-500/25 transition-colors"
                          title="Cancel"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </>
                  ) : (
                    <span className="text-[11px] text-mutedgrey font-mono capitalize">
                      Status: {appt.status}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* New Appointment Modal with Live Slot Availability */}
      <Modal
        isOpen={createModal}
        onClose={() => setCreateModal(false)}
        title="Schedule New Appointment"
      >
        <form onSubmit={handleCreate} className="space-y-4">
          {bookingError && (
            <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs font-medium">
              {bookingError}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                Customer Name
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Rachel Adams"
                value={newAppt.customer_name}
                onChange={(e) => setNewAppt({ ...newAppt, customer_name: e.target.value })}
                className="glass-input w-full"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                Customer Phone
              </label>
              <input
                type="tel"
                required
                placeholder="+91 98401 23456"
                value={newAppt.customer_phone}
                onChange={(e) => setNewAppt({ ...newAppt, customer_phone: e.target.value })}
                className="glass-input w-full font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                Service / Procedure
              </label>
              <select
                value={newAppt.service_id}
                onChange={(e) => {
                  const sId = e.target.value;
                  setNewAppt({ ...newAppt, service_id: sId, appointment_time: '' });
                  setSelectedSlot(null);
                  loadSlots(bookingDate, sId, newAppt.staff_id);
                }}
                className="glass-input w-full"
              >
                <option value="">General Consultation (30 mins)</option>
                {services.map((srv) => (
                  <option key={srv.id} value={srv.id}>
                    {srv.name} ({srv.duration_minutes || 30} mins)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
                Provider / Doctor
              </label>
              <select
                value={newAppt.staff_id || ''}
                onChange={(e) => {
                  const stId = e.target.value || '';
                  setNewAppt({ ...newAppt, staff_id: stId, appointment_time: '' });
                  setSelectedSlot(null);
                  loadSlots(bookingDate, newAppt.service_id, stId);
                }}
                className="glass-input w-full"
              >
                <option value="">Any Available Staff</option>
                {staffList.map((st) => (
                  <option key={st.id} value={st.id}>
                    {st.name} ({st.role})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Appointment Date
            </label>
            <input
              type="date"
              required
              value={bookingDate}
              onChange={(e) => {
                setBookingDate(e.target.value);
                setNewAppt({ ...newAppt, appointment_time: '' });
                setSelectedSlot(null);
                loadSlots(e.target.value, newAppt.service_id, newAppt.staff_id);
              }}
              className="glass-input w-full font-mono text-xs"
            />
          </div>

          {/* Slot Picker Component */}
          <div className="space-y-1.5 pt-1">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider">
                Select Time Slot {slotsData.is_open && slotsData.available_slots_count ? `(${slotsData.available_slots_count} available)` : ''}
              </label>
              {slotsData.timezone && (
                <span className="text-[10px] text-mutedgrey font-mono">
                  {slotsData.timezone}
                </span>
              )}
            </div>

            {slotsLoading ? (
              <div className="p-4 rounded-xl bg-graphite/40 border border-white/5 text-center text-xs text-mutedgrey animate-pulse">
                Calculating available slots...
              </div>
            ) : !slotsData.is_open ? (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs text-center font-medium">
                Business / Provider is closed on this day. Please select another date.
              </div>
            ) : slotsData.slots && slotsData.slots.length > 0 ? (
              <div className="grid grid-cols-4 sm:grid-cols-6 gap-2 max-h-44 overflow-y-auto p-1.5 rounded-xl bg-graphite/30 border border-white/5">
                {slotsData.slots.map((slot) => {
                  const isSelected = newAppt.appointment_time === slot.start_time;
                  return (
                    <button
                      key={slot.time}
                      type="button"
                      disabled={!slot.available}
                      onClick={() => {
                        setNewAppt({ ...newAppt, appointment_time: slot.start_time });
                        setSelectedSlot(slot);
                        setBookingError(null);
                      }}
                      title={slot.reason || 'Click to select slot'}
                      className={`py-2 px-1 rounded-lg text-xs font-mono font-medium transition-all text-center border ${
                        isSelected
                          ? 'bg-amber text-warmblack font-bold border-amber shadow-md shadow-amber/30 scale-105'
                          : slot.available
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
                          : 'bg-white/5 border-white/5 text-mutedgrey/30 cursor-not-allowed line-through'
                      }`}
                    >
                      {slot.time}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="p-3 rounded-xl bg-graphite/30 text-center text-xs text-mutedgrey">
                No slots configured for this day.
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Special Notes / Instructions
            </label>
            <textarea
              rows={2}
              placeholder="First-time visitor, requested routine checkup..."
              value={newAppt.notes}
              onChange={(e) => setNewAppt({ ...newAppt, notes: e.target.value })}
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
              disabled={!newAppt.appointment_time}
              className="px-5 py-2 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs shadow-lg shadow-burnt/20 hover:scale-[1.02] disabled:opacity-40 disabled:hover:scale-100 transition-all"
            >
              Confirm Booking
            </button>
          </div>
        </form>
      </Modal>

      {/* Reschedule Modal with Live Slot Calculation */}
      <Modal
        isOpen={rescheduleModal}
        onClose={() => setRescheduleModal(false)}
        title="Reschedule Appointment"
      >
        <form onSubmit={handleReschedule} className="space-y-4">
          {rescheduleError && (
            <div className="p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs font-medium">
              {rescheduleError}
            </div>
          )}

          <p className="text-xs text-mutedgrey">
            Rescheduling booking for{' '}
            <strong className="text-ivory">{selectedAppt?.customer?.name || selectedAppt?.customer_name || 'Customer'}</strong>.
            The client will receive an automated notification.
          </p>

          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Select New Date
            </label>
            <input
              type="date"
              required
              value={rescheduleDate}
              onChange={(e) => {
                setRescheduleDate(e.target.value);
                setNewTime('');
                loadRescheduleSlots(e.target.value, selectedAppt?.service_id, selectedAppt?.staff_id);
              }}
              className="glass-input w-full font-mono text-xs"
            />
          </div>

          {/* Reschedule Slot Picker */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider">
                Select Available Slot
              </label>
              {rescheduleSlots.timezone && (
                <span className="text-[10px] text-mutedgrey font-mono">
                  {rescheduleSlots.timezone}
                </span>
              )}
            </div>

            {rescheduleLoading ? (
              <div className="p-3 rounded-xl bg-graphite/40 border border-white/5 text-center text-xs text-mutedgrey animate-pulse">
                Fetching open slots...
              </div>
            ) : !rescheduleSlots.is_open ? (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs text-center font-medium">
                Clinic is closed on this date.
              </div>
            ) : rescheduleSlots.slots && rescheduleSlots.slots.length > 0 ? (
              <div className="grid grid-cols-4 sm:grid-cols-6 gap-2 max-h-40 overflow-y-auto p-1.5 rounded-xl bg-graphite/30 border border-white/5">
                {rescheduleSlots.slots.map((slot) => {
                  const isSelected = newTime === slot.start_time;
                  return (
                    <button
                      key={slot.time}
                      type="button"
                      disabled={!slot.available}
                      onClick={() => {
                        setNewTime(slot.start_time);
                        setRescheduleError(null);
                      }}
                      title={slot.reason || 'Available slot'}
                      className={`py-2 px-1 rounded-lg text-xs font-mono font-medium transition-all text-center border ${
                        isSelected
                          ? 'bg-amber text-warmblack font-bold border-amber shadow-md shadow-amber/30 scale-105'
                          : slot.available
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
                          : 'bg-white/5 border-white/5 text-mutedgrey/30 cursor-not-allowed line-through'
                      }`}
                    >
                      {slot.time}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="p-3 rounded-xl bg-graphite/30 text-center text-xs text-mutedgrey">
                No slots found for this day.
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-mutedgrey uppercase tracking-wider mb-1.5">
              Reason for Reschedule
            </label>
            <input
              type="text"
              placeholder="e.g. Patient travel conflict, Doctor requested change"
              value={rescheduleReason}
              onChange={(e) => setRescheduleReason(e.target.value)}
              className="glass-input w-full text-xs"
            />
          </div>

          <div className="pt-3 flex items-center justify-end gap-3 border-t border-graphite">
            <button
              type="button"
              onClick={() => setRescheduleModal(false)}
              className="px-4 py-2 rounded-xl bg-warmblack border border-graphite text-xs font-semibold text-ivory hover:bg-graphite transition-colors"
            >
              Keep Current
            </button>
            <button
              type="submit"
              disabled={!newTime}
              className="px-5 py-2 rounded-xl bg-burnt text-warmblack font-bold text-xs shadow-lg shadow-burnt/20 hover:scale-[1.02] disabled:opacity-40 disabled:hover:scale-100 transition-all"
            >
              Update Schedule
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
