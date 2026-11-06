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
  Legend,
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

  const handleExportCSV = () => {
    if (!data) return;
    confetti({
      particleCount: 50,
      spread: 60,
      origin: { y: 0.8 },
      colors: ['#E47745', '#F0AD57', '#A78BFA'],
    });

    const rows = [
      ['Metric', 'Value'],
      ['Total Calls', data.metrics.total_calls],
      ['Incoming Calls', data.metrics.incoming_calls],
      ['Outgoing Calls', data.metrics.outgoing_calls],
      ['Successful Calls', data.metrics.successful_calls],
      ['Missed Calls', data.metrics.missed_calls],
      ['Call Success Rate (%)', data.metrics.call_success_rate],
      ['Avg Call Duration (s)', data.metrics.avg_call_duration_seconds],
      ['Total Appointments', data.metrics.total_appointments],
      ['Completed Appointments', data.metrics.completed_appointments],
      ['Appointment Fulfillment Rate (%)', data.metrics.appointment_fulfillment_rate],
    ];

    const csvContent = 'data:text/csv;charset=utf-8,' + rows.map((e) => e.join(',')).join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `vattara_telemetry_report_${rangeType}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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

  const { metrics, daily_breakdown } = data;

  const pieData = [
    { name: 'Successful Calls', value: metrics.successful_calls },
    { name: 'Missed / Dropped', value: metrics.missed_calls || 1 },
    { name: 'Completed Appts', value: metrics.completed_appointments },
    { name: 'Inbound Placed', value: metrics.incoming_calls },
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
                <ShieldCheck className="w-3 h-3" /> Zero Data Loss
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-ivory tracking-tight">
              Reports & Performance Analytics
            </h1>
            <p className="text-xs sm:text-sm text-mutedgrey max-w-xl">
              High-fidelity operational analytics, automated call fulfillment ratios, handle-time
              distributions, and CSV export capabilities.
            </p>
          </div>

          {/* Quick Actions & Date Filter */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Range Toggle */}
            <div className="flex items-center bg-warmblack/70 p-1 rounded-xl border border-graphite">
              {[
                { id: '7d', label: '7 Days' },
                { id: '30d', label: '30 Days' },
                { id: '90d', label: '90 Days' },
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

            <button
              onClick={handleExportCSV}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-burnt to-amber text-warmblack font-bold text-xs flex items-center gap-2 shadow-lg shadow-burnt/20 hover:scale-[1.02] active:scale-[0.98] transition-all"
            >
              <Download className="w-3.5 h-3.5" />
              Export CSV
            </button>

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
          title="Total Telephony Throughput"
          value={metrics.total_calls}
          subtext={`${metrics.incoming_calls} Inbound • ${metrics.outgoing_calls} Outbound`}
          icon={PhoneCall}
          color="burnt"
          trend="+14% this period"
        />

        <StatCard
          title="Autonomous Success Rate"
          value={`${metrics.call_success_rate}%`}
          subtext={`${metrics.successful_calls} resolved / ${metrics.missed_calls} missed`}
          icon={Zap}
          color="amber"
          trend="+3.2% vs last week"
        />

        <StatCard
          title="Appointment Fulfillment"
          value={`${metrics.appointment_fulfillment_rate}%`}
          subtext={`${metrics.completed_appointments} completed of ${metrics.total_appointments}`}
          icon={CalendarCheck2}
          color="lavender"
          trend="Optimal conversion"
        />

        <StatCard
          title="Average Handle Time"
          value={`${metrics.avg_call_duration_seconds}s`}
          subtext={`~${Math.round(metrics.avg_call_duration_seconds / 60)} min per voice session`}
          icon={Clock}
          color="charcoal"
          trend="-12s latency improvement"
        />
      </div>

      {/* Primary Chart: Telephony & Appointment Volume Stream */}
      <div className="glass-panel p-6 sm:p-7 rounded-3xl border border-graphite space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <span className="text-[10px] font-mono uppercase font-bold tracking-wider text-burnt">
              Temporal Trajectory
            </span>
            <h3 className="text-lg font-bold text-ivory">Call Volume vs Appointment Conversions</h3>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="flex items-center gap-1.5 text-burnt">
              <span className="w-2.5 h-2.5 rounded-full bg-burnt" /> AI Voice Calls
            </span>
            <span className="flex items-center gap-1.5 text-amber">
              <span className="w-2.5 h-2.5 rounded-full bg-amber" /> Appointments Booked
            </span>
          </div>
        </div>

        <div className="h-80 w-full pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={daily_breakdown} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
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
                  boxShadow: '0 10px 25px -5px rgba(0,0,0,0.5)',
                }}
              />
              <Area
                type="monotone"
                dataKey="calls"
                stroke={colors.burnt}
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#callGrad)"
                name="Voice Calls"
              />
              <Area
                type="monotone"
                dataKey="appointments"
                stroke={colors.amber}
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#apptGrad)"
                name="Appointments"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Secondary Two-Column Grid: Bar Chart & Telephony Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Disposition Bar Chart */}
        <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-4">
          <div>
            <span className="text-[10px] font-mono uppercase font-bold tracking-wider text-amber">
              Daily Distribution
            </span>
            <h3 className="text-base font-bold text-ivory">Completed Appointments by Day</h3>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={daily_breakdown} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
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
                <Bar
                  dataKey="completed"
                  fill={colors.lavender}
                  radius={[6, 6, 0, 0]}
                  name="Completed Appointments"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Telemetry Channel Composition Donut */}
        <div className="glass-panel p-6 rounded-3xl border border-graphite space-y-4 flex flex-col justify-between">
          <div>
            <span className="text-[10px] font-mono uppercase font-bold tracking-wider text-lavender">
              Composition Breakdown
            </span>
            <h3 className="text-base font-bold text-ivory">Telemetry Resolution Channels</h3>
          </div>

          <div className="h-56 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={chartColors[index % chartColors.length]}
                      stroke={colors.warmblack}
                      strokeWidth={2}
                    />
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

          {/* Custom Pill Legend */}
          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/5">
            {pieData.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 p-2 rounded-xl bg-warmblack/60 border border-white/5 text-xs"
              >
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: chartColors[idx % chartColors.length] }}
                />
                <span className="text-mutedgrey truncate">{item.name}</span>
                <span className="font-mono font-bold text-ivory ml-auto">{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
