import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart3,
  Calendar,
  Download,
  PhoneCall,
  CheckCircle2,
  Clock,
  CalendarCheck2,
  TrendingUp,
  RefreshCw,
  Sparkles,
  ArrowUpRight,
  ShieldCheck,
  Zap,
  Activity,
  Layers,
  Radio,
  BellRing,
  PieChart as PieChartIcon,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import StatCard from '../../components/common/StatCard';
import { reportsService } from '../../services/api';
import { useTheme } from '../../context/ThemeContext';
import confetti from 'canvas-confetti';

export default function Reports() {
  const { colors } = useTheme();
  const [rangeType, setRangeType] = useState('7d');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [csvType, setCsvType] = useState('calls');

  const chartColors = [colors.burnt, colors.amber, colors.lavender, '#10B981'];

  const fetchReports = async () => {
    setLoading(true);
    try {
      const rep = await reportsService.getSummary(rangeType);
      setData(rep);
    } catch (err) {
      console.error('Failed to load reports:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [rangeType]);

  const handleExportCSV = async () => {
    setExporting(true);
    confetti({
      particleCount: 50,
      spread: 60,
      origin: { y: 0.8 },
      colors: ['#E47745', '#F0AD57', '#A78BFA'],
    });

    try {
      await reportsService.exportCsv(csvType);
    } catch (err) {
      console.error('Failed to export CSV from server:', err);
    } finally {
      setExporting(false);
    }
  };

  if (loading || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-32 space-y-4">
        <div className="w-12 h-12 border-3 border-burnt border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-mutedgrey animate-pulse font-mono tracking-wider">
          COMPUTING TELEMETRY METRICS & CHARTS...
        </p>
      </div>
    );
  }

  const { metrics, timeline, duration_distribution, provider_breakdown, reminder_delivery } = data;

  const durationData = [
    { label: '< 1 min', count: duration_distribution?.under_1_min || 0 },
    { label: '1 - 3 mins', count: duration_distribution?.['1_to_3_mins'] || 0 },
    { label: '3 - 5 mins', count: duration_distribution?.['3_to_5_mins'] || 0 },
    { label: '5+ mins', count: duration_distribution?.over_5_mins || 0 },
  ];

  const providerData = [
    { name: 'Twilio Media Stream', value: provider_breakdown?.twilio || 0, color: colors.burnt },
    { name: 'Tata Smartflo SIP', value: provider_breakdown?.smartflo || 0, color: colors.amber },
    { name: 'Exotel Voice Gateway', value: provider_breakdown?.exotel || 0, color: colors.lavender },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-charcoal via-graphite to-warmblack border border-white/10 p-6 sm:p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-burnt/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
        <div className="absolute bottom-0 left-1/4 w-72 h-72 bg-amber/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="p-2.5 rounded-xl bg-burnt/15 border border-burnt/30 text-burnt">
                <BarChart3 className="w-5 h-5 animate-pulse" />
              </span>
              <span className="text-xs font-semibold tracking-wider uppercase text-burnt">
                Executive Telemetry & Intelligence
              </span>
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                <ShieldCheck className="w-3 h-3" /> Realtime Metrics
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-ivory tracking-tight">
              Reports & Performance Analytics
            </h1>
            <p className="text-xs sm:text-sm text-mutedgrey max-w-xl">
              High-fidelity operational analytics, automated call fulfillment ratios, handle-time
              distributions, telephony provider breakdowns, and CSV export capabilities.
            </p>
          </div>

          {/* Quick Actions & Date Filter */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Range Toggle */}
            <div className="flex items-center bg-warmblack/70 p-1 rounded-xl border border-graphite">
              {[
                { id: 'today', label: 'Today' },
                { id: '7d', label: '7 Days' },
                { id: '30d', label: '30 Days' },
                { id: '90d', label: '90 Days' },
                { id: 'year', label: 'Year' },
              ].map((r) => (
                <button
                  key={r.id}
                  onClick={() => setRangeType(r.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    rangeType === r.id
                      ? 'bg-burnt text-warmblack font-bold shadow-sm'
                      : 'text-mutedgrey hover:text-ivory'
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>

            {/* CSV Export Control */}
            <div className="flex items-center gap-1.5 bg-warmblack/70 p-1 rounded-xl border border-graphite">
              <select
                value={csvType}
                onChange={(e) => setCsvType(e.target.value)}
                className="bg-transparent text-xs text-ivory font-mono px-2 py-1 focus:outline-none"
              >
                <option value="calls" className="bg-charcoal text-ivory">Calls</option>
                <option value="appointments" className="bg-charcoal text-ivory">Appointments</option>
                <option value="reminders" className="bg-charcoal text-ivory">Reminders</option>
              </select>

              <button
                onClick={handleExportCSV}
                disabled={exporting}
                className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs flex items-center gap-1.5 shadow-sm hover:scale-[1.02] active:scale-[0.98] transition-all disabled:opacity-50"
              >
                <Download className="w-3.5 h-3.5" />
                {exporting ? 'Exporting...' : 'Export CSV'}
              </button>
            </div>

            <button
              onClick={fetchReports}
              className="p-2.5 rounded-xl bg-graphite/80 border border-white/10 text-ivory hover:text-burnt hover:border-burnt/30 transition-all"
              title="Refresh Analytics"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          title="Telephony Throughput"
          value={metrics.total_calls}
          subtext={`${metrics.incoming_calls} Inbound • ${metrics.outgoing_calls} Outbound`}
          icon={PhoneCall}
          color="burnt"
          trend="PSTN & SIP Trunks"
        />

        <StatCard
          title="Autonomous Success Rate"
          value={`${metrics.call_success_rate}%`}
          subtext={`${metrics.successful_calls} resolved / ${metrics.missed_calls} missed`}
          icon={Zap}
          color="amber"
          trend="Zero human intervention"
        />

        <StatCard
          title="Appointment Fulfillment"
          value={`${metrics.appointment_fulfillment_rate}%`}
          subtext={`${metrics.completed_appointments} completed of ${metrics.total_appointments}`}
          icon={CalendarCheck2}
          color="lavender"
          trend={`${metrics.appointment_conversion_rate}% call conversion`}
        />

        <StatCard
          title="Average Handle Time"
          value={`${metrics.avg_call_duration_seconds}s`}
          subtext={`~${Math.round(metrics.avg_call_duration_seconds / 60)} min per voice session`}
          icon={Clock}
          color="charcoal"
          trend="Real-time speech streaming"
        />
      </div>

      {/* Primary Chart: Telephony Timeline Volume Stream */}
      <div className="glass-panel p-6 sm:p-7 rounded-3xl border border-graphite space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="text-[10px] font-mono uppercase font-bold tracking-wider text-burnt">
              Temporal Trajectory
            </span>
            <h3 className="text-lg font-bold text-ivory">Daily Inbound vs Outbound Call Flow</h3>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="flex items-center gap-1.5 text-burnt">
              <span className="w-2.5 h-2.5 rounded-full bg-burnt" /> Incoming Calls
            </span>
            <span className="flex items-center gap-1.5 text-amber">
              <span className="w-2.5 h-2.5 rounded-full bg-amber" /> Outbound Reminders
            </span>
          </div>
        </div>

        <div className="h-80 w-full pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={timeline || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="callGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={colors.burnt} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={colors.burnt} stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="apptGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={colors.amber} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={colors.amber} stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.graphite} vertical={false} />
              <XAxis
                dataKey="date"
                stroke={colors.mutedgrey}
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />
              <YAxis stroke={colors.mutedgrey} fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: colors.warmblack,
                  borderColor: colors.graphite,
                  borderRadius: '12px',
                  color: colors.ivory,
                  fontSize: '12px',
                }}
              />
              <Area
                type="monotone"
                dataKey="incoming"
                stroke={colors.burnt}
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#callGrad)"
                name="Incoming Calls"
              />
              <Area
                type="monotone"
                dataKey="outgoing"
                stroke={colors.amber}
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#apptGrad)"
                name="Outgoing Calls"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Secondary Three-Column Grid: Duration Distribution, Provider Breakdown, and Reminder Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Card 1: Call Duration Distribution */}
        <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-4">
          <div>
            <span className="text-[10px] font-mono uppercase font-bold tracking-wider text-amber">
              Duration Histogram
            </span>
            <h3 className="text-base font-bold text-ivory">Call Length Distribution</h3>
          </div>

          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={durationData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={colors.graphite} vertical={false} />
                <XAxis dataKey="label" stroke={colors.mutedgrey} fontSize={10} tickLine={false} axisLine={false} />
                <YAxis stroke={colors.mutedgrey} fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: colors.warmblack,
                    borderColor: colors.graphite,
                    borderRadius: '12px',
                    color: colors.ivory,
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="count" fill={colors.burnt} radius={[6, 6, 0, 0]} name="Calls" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Card 2: Telephony Provider Breakdown */}
        <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-4 flex flex-col justify-between">
          <div>
            <span className="text-[10px] font-mono uppercase font-bold tracking-wider text-lavender">
              Carrier Telemetry
            </span>
            <h3 className="text-base font-bold text-ivory">Telephony Provider Ratio</h3>
          </div>

          <div className="h-44 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={providerData}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={68}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {providerData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} stroke={colors.warmblack} strokeWidth={2} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: colors.warmblack,
                    borderColor: colors.graphite,
                    borderRadius: '12px',
                    color: colors.ivory,
                    fontSize: '12px',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-1.5 pt-2 border-t border-white/5 text-xs">
            {providerData.map((item, idx) => (
              <div key={idx} className="flex items-center justify-between text-mutedgrey">
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                  {item.name}
                </span>
                <span className="font-mono font-bold text-ivory">{item.value} calls</span>
              </div>
            ))}
          </div>
        </div>

        {/* Card 3: Automated Reminder Delivery */}
        <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-4 flex flex-col justify-between">
          <div>
            <span className="text-[10px] font-mono uppercase font-bold tracking-wider text-emerald-400">
              Outbound Dispatch
            </span>
            <h3 className="text-base font-bold text-ivory">Reminder Delivery & Confirmations</h3>
          </div>

          <div className="space-y-3 pt-2">
            <div className="p-3 rounded-2xl bg-warmblack/60 border border-white/5 flex items-center justify-between">
              <span className="text-xs text-mutedgrey">Total Scheduled Reminders</span>
              <span className="text-base font-bold text-ivory font-mono">
                {reminder_delivery?.total || 0}
              </span>
            </div>

            <div className="p-3 rounded-2xl bg-warmblack/60 border border-white/5 flex items-center justify-between">
              <span className="text-xs text-mutedgrey">Successfully Dispatched</span>
              <span className="text-base font-bold text-emerald-400 font-mono">
                {reminder_delivery?.sent || 0}
              </span>
            </div>

            <div className="p-3 rounded-2xl bg-burnt/10 border border-burnt/30 flex items-center justify-between">
              <span className="text-xs text-burnt">Patient Confirmations</span>
              <span className="text-base font-bold text-burnt font-mono">
                {reminder_delivery?.confirmed || 0} ({reminder_delivery?.confirmation_rate || 0}%)
              </span>
            </div>

            <div className="p-3 rounded-2xl bg-warmblack/60 border border-white/5 flex items-center justify-between">
              <span className="text-xs text-mutedgrey">Pending / In-Queue</span>
              <span className="text-base font-bold text-amber font-mono">
                {reminder_delivery?.pending || 0}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
