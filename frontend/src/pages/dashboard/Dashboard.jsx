import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  PhoneIncoming,
  PhoneOutgoing,
  CalendarCheck2,
  Users,
  CheckCircle2,
  PhoneMissed,
  Bot,
  ArrowUpRight,
  Clock,
  Calendar,
  Sparkles,
  PhoneCall,
  Radio,
  Flame,
  Volume2,
  Zap,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import confetti from 'canvas-confetti';
import StatCard from '../../components/common/StatCard';
import Badge from '../../components/common/Badge';
import VoiceOrb from '../../components/common/VoiceOrb';
import WaveformVisualizer from '../../components/common/WaveformVisualizer';
import { dashboardService, callsService } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';

export default function Dashboard() {
  const { business } = useAuth();
  const { colors } = useTheme();
  const [stats, setStats] = useState(null);
  const [activities, setActivities] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [orbSpeaking, setOrbSpeaking] = useState(true);

  const pieColors = [colors.burnt, colors.amber, colors.lavender, colors.graphite];

  const loadData = async () => {
    try {
      const [sData, aData, anData] = await Promise.all([
        dashboardService.getStats(),
        dashboardService.getActivities(),
        dashboardService.getAnalytics(7),
      ]);
      setStats(sData);
      setActivities(aData);
      setAnalytics(anData);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSimulateCall = async () => {
    setSimulating(true);
    setOrbSpeaking(true);
    try {
      await callsService.simulateCall({
        caller_name: 'Patient Caller',
        caller_phone: '+91 94441 99221',
        call_type: 'incoming',
        scenario: 'Doctor Consultation Booking',
        duration_seconds: 140,
      });

      confetti({
        particleCount: 40,
        spread: 70,
        origin: { y: 0.3, x: 0.5 },
        colors: ['#E47745', '#F0AD57', '#A78BFA'],
      });

      await loadData();
    } catch (err) {
      console.error(err);
    } finally {
      setSimulating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-2 border-burnt border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-xs font-mono uppercase tracking-widest text-mutedgrey">
            Synchronizing live telephony telemetry...
          </p>
        </div>
      </div>
    );
  }

  const successRate = stats?.successful_calls && (stats?.successful_calls + stats?.missed_calls) > 0
    ? Math.round((stats.successful_calls / (stats.successful_calls + stats.missed_calls)) * 100)
    : 92;

  return (
    <div className="space-y-8">
      {/* 1. HERO COMPOSITION: Asymmetric AI Engine Showcase */}
      <div className="relative rounded-3xl glass-panel-glow border border-ivory/10 p-6 sm:p-8 lg:p-10 overflow-hidden">
        {/* Subtle background glow circle */}
        <div className="absolute -right-20 -top-20 w-96 h-96 bg-burnt/15 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Left Column: Organization context & call simulator */}
          <div className="lg:col-span-7 space-y-4">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-mono uppercase font-bold tracking-widest text-amber bg-amber/15 border border-amber/30">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                Vattara Engine 3.8 Online
              </span>
              <span className="text-[11px] font-mono text-mutedgrey">
                Latency: <span className="text-ivory font-bold">~420ms</span>
              </span>
              <span className="text-mutedgrey">•</span>
              <span className="text-[11px] font-mono text-mutedgrey">
                PSTN Trunk: <span className="text-emerald-400 font-bold">Bound</span>
              </span>
            </div>

            <h1 className="text-3xl sm:text-4xl font-extrabold text-ivory tracking-tight">
              {business?.name || 'Vattara City Clinic & Diagnostics'}
            </h1>

            <p className="text-xs sm:text-sm text-mutedgrey max-w-xl leading-relaxed">
              Autonomous conversational reception. Patient inquiries, clinic timings, pricing, and appointment schedules handled seamlessly around the clock.
            </p>

            {/* Quick action buttons & waveform preview */}
            <div className="pt-2 flex flex-wrap items-center gap-3">
              <button
                onClick={handleSimulateCall}
                disabled={simulating}
                className="flex items-center gap-2.5 px-5 py-3 rounded-xl bg-gradient-to-r from-burnt via-burnt to-amber text-warmblack font-extrabold text-xs uppercase tracking-wider shadow-xl shadow-burnt/30 hover:shadow-burnt/50 transition-all duration-200 disabled:opacity-50"
              >
                <PhoneCall className={`w-4 h-4 ${simulating ? 'animate-bounce' : ''}`} />
                <span>{simulating ? 'Synthesizing Audio...' : 'Test AI Phone Call'}</span>
              </button>

              <Link
                to="/assistant"
                className="flex items-center gap-2 px-4 py-3 rounded-xl glass-card text-ivory hover:text-amber font-semibold text-xs border border-ivory/10 transition-colors"
              >
                <Bot className="w-4 h-4 text-amber" />
                <span>Voice Agent Setup</span>
              </Link>
            </div>
          </div>

          {/* Right Column: 3D Animated Voice Orb & Soundwaves */}
          <div className="lg:col-span-5 flex flex-col items-center justify-center border-t lg:border-t-0 lg:border-l border-ivory/10 pt-6 lg:pt-0">
            <VoiceOrb isSpeaking={orbSpeaking} size="md" />

            <div className="mt-3 flex items-center gap-3">
              <button
                onClick={() => setOrbSpeaking(!orbSpeaking)}
                className="text-[11px] font-mono px-3 py-1 rounded-full glass-card border border-ivory/10 text-mutedgrey hover:text-ivory"
              >
                Speech Pulse: <span className={orbSpeaking ? 'text-amber font-bold' : 'text-mutedgrey'}>{orbSpeaking ? 'ACTIVE' : 'IDLE'}</span>
              </button>
            </div>
            <div className="mt-2">
              <WaveformVisualizer barCount={24} height={28} isPlaying={orbSpeaking} color="amber" />
            </div>
          </div>
        </div>
      </div>

      {/* 2. ASYMMETRIC KPI MATRIX */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Dual Calls (Span 2 on large screens) */}
        <div className="lg:col-span-2 glass-card rounded-2xl p-6 border border-burnt/30 shadow-lg shadow-burnt/5 flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-burnt/40 to-transparent" />

          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-mutedgrey">
                Telephony Throughput
              </span>
              <span className="inline-flex items-center gap-1 text-[11px] font-mono text-emerald-400 font-bold bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-500/30">
                <Radio className="w-3 h-3 text-emerald-400 animate-pulse" /> Live Feed
              </span>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-6">
              <div>
                <div className="flex items-center gap-2 text-mutedgrey text-xs">
                  <PhoneIncoming className="w-4 h-4 text-burnt-light" />
                  <span>Incoming Calls</span>
                </div>
                <p className="text-3xl font-extrabold text-ivory mt-1">
                  {stats?.total_incoming_calls || 0}
                </p>
                <p className="text-[11px] text-mutedgrey mt-0.5">Caller queries resolved</p>
              </div>

              <div>
                <div className="flex items-center gap-2 text-mutedgrey text-xs">
                  <PhoneOutgoing className="w-4 h-4 text-amber" />
                  <span>Outgoing Calls</span>
                </div>
                <p className="text-3xl font-extrabold text-ivory mt-1">
                  {stats?.total_outgoing_calls || 0}
                </p>
                <p className="text-[11px] text-mutedgrey mt-0.5">Automated reminders</p>
              </div>
            </div>
          </div>

          {/* Visual comparative bar */}
          <div className="mt-6 pt-4 border-t border-ivory/10 space-y-2">
            <div className="flex justify-between text-[11px] font-mono text-mutedgrey">
              <span>Resolution Ratio</span>
              <span className="text-amber font-bold">{successRate}% Successful</span>
            </div>
            <div className="w-full h-2 rounded-full bg-graphite overflow-hidden flex">
              <div
                className="h-full bg-gradient-to-r from-burnt to-amber"
                style={{ width: `${successRate}%` }}
              />
              <div
                className="h-full bg-rose-500/50"
                style={{ width: `${100 - successRate}%` }}
              />
            </div>
          </div>
        </div>

        {/* Card 2: Total Appointments */}
        <StatCard
          title="Total Bookings"
          value={stats?.total_appointments || 0}
          subtitle={`${stats?.upcoming_appointments_count || 0} visits upcoming this week`}
          icon={CalendarCheck2}
          color="amber"
          trend={18}
        />

        {/* Card 3: Total Customers */}
        <StatCard
          title="Customer Base"
          value={stats?.total_customers || 0}
          subtitle="Registered callers in CRM"
          icon={Users}
          color="lavender"
          trend={12}
        />
      </div>

      {/* 3. VISUAL TELEMETRY: 7-Day Area Chart + Donut Fulfillment */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Recharts Volume Curve (Span 8) */}
        <div className="lg:col-span-8 glass-panel rounded-3xl p-6 border border-ivory/10">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-burnt animate-pulse" />
                <h3 className="text-base font-bold text-ivory tracking-wide">
                  Call Volume & Telephony Trajectory
                </h3>
              </div>
              <p className="text-xs text-mutedgrey mt-0.5">
                Daily inbound customer traffic vs. outbound reminder dispatch volume
              </p>
            </div>

            <Link
              to="/reports"
              className="inline-flex items-center gap-1 text-xs font-mono font-bold text-burnt-light hover:text-burnt transition-colors"
            >
              Full Analytics <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analytics?.call_trends || []}>
                <defs>
                  <linearGradient id="colorBurnt" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={colors.burnt} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={colors.burnt} stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="colorAmber" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={colors.amber} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={colors.amber} stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={colors.graphite} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: colors.mutedgrey }} stroke={colors.graphite} />
                <YAxis tick={{ fontSize: 11, fill: colors.mutedgrey }} stroke={colors.graphite} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: colors.charcoal,
                    borderColor: colors.graphite,
                    borderRadius: '12px',
                    color: colors.ivory,
                    fontSize: '11px',
                    fontFamily: 'monospace',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="incoming"
                  stroke={colors.burnt}
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#colorBurnt)"
                  name="Inbound Calls"
                />
                <Area
                  type="monotone"
                  dataKey="outgoing"
                  stroke={colors.amber}
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#colorAmber)"
                  name="Outbound Calls"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right: Appointment Breakdown Donut (Span 4) */}
        <div className="lg:col-span-4 glass-panel rounded-3xl p-6 border border-ivory/10 flex flex-col justify-between">
          <div>
            <h3 className="text-base font-bold text-ivory tracking-wide">
              Appointment Status
            </h3>
            <p className="text-xs text-mutedgrey mt-0.5">Fulfillment across schedule</p>
          </div>

          <div className="h-56 w-full flex items-center justify-center relative">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={analytics?.appointment_breakdown || []}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={84}
                  paddingAngle={5}
                  dataKey="count"
                  nameKey="status"
                >
                  {(analytics?.appointment_breakdown || []).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={pieColors[index % pieColors.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: colors.charcoal,
                    borderColor: colors.graphite,
                    borderRadius: '12px',
                    color: colors.ivory,
                    fontSize: '11px',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>

            {/* Glowing Donut Center Indicator */}
            <div className="absolute text-center pointer-events-none">
              <span className="text-2xl font-extrabold text-ivory block font-mono">
                {stats?.total_appointments || 0}
              </span>
              <span className="text-[10px] uppercase font-mono tracking-widest text-mutedgrey">
                Total Visits
              </span>
            </div>
          </div>

          <div className="pt-4 border-t border-ivory/10 flex items-center justify-between text-xs">
            <span className="text-mutedgrey">Autonomous Bookings</span>
            <span className="font-mono font-bold text-amber">84% via Voice</span>
          </div>
        </div>
      </div>

      {/* 4. RECENT ACTIVITIES & LAUNCHPAD */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Activity Feed (Span 8) */}
        <div className="lg:col-span-8 glass-panel rounded-3xl p-6 border border-ivory/10">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-base font-bold text-ivory">Real-Time Event Stream</h3>
              <p className="text-xs text-mutedgrey">Chronological voice calls and appointment entries</p>
            </div>
            <Link
              to="/calls"
              className="text-xs font-mono font-bold text-amber hover:text-amber-light"
            >
              Inspect Logs
            </Link>
          </div>

          <div className="divide-y divide-ivory/5">
            {activities.length === 0 ? (
              <p className="py-8 text-center text-xs text-mutedgrey">No live events captured yet.</p>
            ) : (
              activities.slice(0, 5).map((item) => (
                <div key={item.id} className="py-3.5 flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-xl bg-graphite border border-ivory/10 text-burnt-light mt-0.5">
                      {item.type === 'call' ? (
                        <PhoneCall className="w-4 h-4" />
                      ) : (
                        <CalendarCheck2 className="w-4 h-4 text-amber" />
                      )}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-ivory">{item.title}</p>
                      <p className="text-xs text-mutedgrey line-clamp-1 mt-0.5">{item.description}</p>
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-1 flex-shrink-0">
                    <Badge status={item.status || 'completed'} />
                    <span className="text-[10px] font-mono text-mutedgrey/70">
                      {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Quick Launchpad (Span 4) */}
        <div className="lg:col-span-4 glass-panel rounded-3xl p-6 border border-ivory/10 flex flex-col justify-between">
          <div>
            <h3 className="text-base font-bold text-ivory mb-1">Direct Operations</h3>
            <p className="text-xs text-mutedgrey mb-4">Fast-track administrative commands</p>

            <div className="space-y-2.5">
              <Link
                to="/appointments"
                className="flex items-center justify-between p-3.5 rounded-2xl glass-card border border-ivory/5 hover:border-burnt/30 transition-all group"
              >
                <div className="flex items-center gap-3">
                  <CalendarCheck2 className="w-4 h-4 text-burnt-light" />
                  <span className="text-xs font-semibold text-ivory">Book New Appointment</span>
                </div>
                <ArrowUpRight className="w-4 h-4 text-mutedgrey group-hover:text-amber transition-colors" />
              </Link>

              <Link
                to="/customers"
                className="flex items-center justify-between p-3.5 rounded-2xl glass-card border border-ivory/5 hover:border-burnt/30 transition-all group"
              >
                <div className="flex items-center gap-3">
                  <Users className="w-4 h-4 text-amber" />
                  <span className="text-xs font-semibold text-ivory">Register Customer</span>
                </div>
                <ArrowUpRight className="w-4 h-4 text-mutedgrey group-hover:text-amber transition-colors" />
              </Link>

              <Link
                to="/reminders"
                className="flex items-center justify-between p-3.5 rounded-2xl glass-card border border-ivory/5 hover:border-burnt/30 transition-all group"
              >
                <div className="flex items-center gap-3">
                  <Clock className="w-4 h-4 text-lavender" />
                  <span className="text-xs font-semibold text-ivory">Dispatch SMS Reminder</span>
                </div>
                <ArrowUpRight className="w-4 h-4 text-mutedgrey group-hover:text-amber transition-colors" />
              </Link>
            </div>
          </div>

          <div className="mt-6 p-4 rounded-2xl bg-gradient-to-br from-graphite to-charcoal border border-burnt/20">
            <div className="flex items-center gap-2 mb-1">
              <Flame className="w-4 h-4 text-burnt animate-pulse" />
              <span className="text-xs font-bold text-ivory">Twilio Media Stream</span>
            </div>
            <p className="text-[11px] text-mutedgrey leading-relaxed">
              Inbound calls to your Twilio number are automatically transcribed and processed through OpenAI Realtime.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
