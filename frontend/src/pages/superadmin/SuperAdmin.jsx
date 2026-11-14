import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ShieldAlert,
  Building2,
  Users,
  PhoneCall,
  CalendarCheck2,
  Sliders,
  CheckCircle2,
  XCircle,
  ToggleLeft,
  ToggleRight,
  TrendingUp,
  CreditCard,
  RefreshCw,
  Search,
  AlertTriangle,
  ArrowUpRight,
  Check,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { superAdminService } from '../../services/api';
import StatCard from '../../components/common/StatCard';
import Modal from '../../components/common/Modal';
import Badge from '../../components/common/Badge';

export default function SuperAdmin() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [businesses, setBusinesses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [toast, setToast] = useState('');
  const [selectedBiz, setSelectedBiz] = useState(null);
  const [planModal, setPlanModal] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState('professional');
  const [updating, setUpdating] = useState(false);

  const isSuperAdmin = user?.role === 'super_admin';

  const loadData = async () => {
    setLoading(true);
    try {
      const [sData, bData] = await Promise.all([
        superAdminService.getStats(),
        superAdminService.getBusinesses(),
      ]);
      setStats(sData);
      setBusinesses(bData);
    } catch (err) {
      console.error('Failed to load super admin data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 4000);
  };

  const handleToggleStatus = async (biz) => {
    try {
      await superAdminService.toggleStatus(biz.id);
      showToast(`Business "${biz.name}" status successfully toggled.`);
      await loadData();
    } catch (err) {
      console.error(err);
      showToast('Failed to toggle business status.');
    }
  };

  const handleOpenPlanModal = (biz) => {
    setSelectedBiz(biz);
    setSelectedPlan(biz.plan || 'professional');
    setPlanModal(true);
  };

  const handleSavePlan = async (e) => {
    e.preventDefault();
    if (!selectedBiz) return;
    setUpdating(true);
    try {
      await superAdminService.updateSubscription(selectedBiz.id, {
        plan: selectedPlan,
        billing_cycle: 'monthly',
      });
      showToast(`Subscription updated for "${selectedBiz.name}" to ${selectedPlan}.`);
      setPlanModal(false);
      await loadData();
    } catch (err) {
      console.error(err);
      showToast('Failed to update tenant subscription.');
    } finally {
      setUpdating(false);
    }
  };

  if (!isSuperAdmin) {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-4">
        <div className="w-16 h-16 rounded-3xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
          <ShieldAlert className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-ivory">Super Admin Clearance Required</h2>
        <p className="text-xs text-mutedgrey max-w-md text-center">
          You are currently signed in as <span className="text-ivory font-mono">{user?.email}</span> with role{' '}
          <span className="text-burnt font-mono font-bold">{user?.role}</span>. This command surface is strictly restricted to platform administrators.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 space-y-4">
        <div className="w-12 h-12 border-3 border-burnt border-t-transparent rounded-full animate-spin" />
        <p className="text-xs text-mutedgrey animate-pulse font-mono tracking-wider">
          SYNCHRONIZING CROSS-TENANT PLATFORM MATRIX...
        </p>
      </div>
    );
  }

  const filteredBusinesses = businesses.filter(
    (b) =>
      b.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (b.email && b.email.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (b.phone && b.phone.includes(searchTerm))
  );

  return (
    <div className="space-y-8 pb-12 max-w-7xl">
      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 bg-charcoal border border-burnt/40 text-ivory text-xs font-semibold px-5 py-3 rounded-2xl shadow-2xl flex items-center gap-2.5 backdrop-blur-md">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toast}</span>
        </div>
      )}

      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-charcoal via-graphite to-warmblack border border-white/10 p-6 sm:p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-burnt/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
        <div className="absolute bottom-0 left-1/4 w-72 h-72 bg-amber/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="p-2.5 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-400">
                <ShieldAlert className="w-5 h-5 animate-pulse" />
              </span>
              <span className="text-xs font-semibold tracking-wider uppercase text-rose-400">
                Super Admin Matrix • Root Clearance
              </span>
              <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
                Multi-Tenant Isolation
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-ivory tracking-tight">
              Platform Administration & SaaS Control
            </h1>
            <p className="text-xs sm:text-sm text-mutedgrey max-w-2xl">
              Inspect multi-tenant health, cross-organization traffic volume, provision subscription quotas,
              and enforce real-time tenant activation states.
            </p>
          </div>

          <button
            onClick={loadData}
            className="self-start lg:self-center px-4 py-2.5 rounded-xl bg-graphite/80 border border-white/10 text-ivory hover:text-burnt hover:border-burnt/30 text-xs font-semibold flex items-center gap-2 transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh Telemetry
          </button>
        </div>
      </div>

      {/* Platform KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          title="Total Businesses"
          value={stats?.total_businesses || 0}
          subtext={`${stats?.active_businesses || 0} currently active`}
          icon={Building2}
          color="burnt"
          trend="Multi-tenant cloud"
        />

        <StatCard
          title="Platform Users"
          value={stats?.total_users || 0}
          subtext="Admins, Doctors, Staff"
          icon={Users}
          color="amber"
          trend="RBAC protected"
        />

        <StatCard
          title="Total Calls Handled"
          value={stats?.total_calls || 0}
          subtext="Aggregated telephony minutes"
          icon={PhoneCall}
          color="lavender"
          trend="Real-time WebSocket & SIP"
        />

        <StatCard
          title="Total Appointments"
          value={stats?.total_appointments || 0}
          subtext="Autonomous reservations"
          icon={CalendarCheck2}
          color="charcoal"
          trend="Full conversion"
        />
      </div>

      {/* Subscription Tier Distribution */}
      <div className="glass-panel p-6 rounded-3xl border border-graphite">
        <div className="flex items-center justify-between mb-4">
          <div>
            <span className="text-[10px] font-mono uppercase font-bold tracking-wider text-burnt">
              Subscription Composition
            </span>
            <h3 className="text-base font-bold text-ivory">Tenant Tier Allocations</h3>
          </div>
          <span className="text-xs text-mutedgrey font-mono">
            Active Accounts: {stats?.active_businesses || 0}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-4 rounded-2xl bg-warmblack/60 border border-white/5 space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wider text-mutedgrey">Starter Tier</span>
            <div className="text-2xl font-extrabold text-ivory font-mono">
              {stats?.plan_distribution?.starter || 0} <span className="text-xs text-mutedgrey font-sans">tenants</span>
            </div>
            <p className="text-[11px] text-mutedgrey">Up to 2 staff • 500 mins</p>
          </div>

          <div className="p-4 rounded-2xl bg-burnt/10 border border-burnt/30 space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wider text-burnt">Professional Tier</span>
            <div className="text-2xl font-extrabold text-burnt font-mono">
              {stats?.plan_distribution?.professional || 0} <span className="text-xs text-mutedgrey font-sans">tenants</span>
            </div>
            <p className="text-[11px] text-mutedgrey">Up to 10 staff • 2,000 mins</p>
          </div>

          <div className="p-4 rounded-2xl bg-amber/10 border border-amber/30 space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wider text-amber">Enterprise Tier</span>
            <div className="text-2xl font-extrabold text-amber font-mono">
              {stats?.plan_distribution?.enterprise || 0} <span className="text-xs text-mutedgrey font-sans">tenants</span>
            </div>
            <p className="text-[11px] text-mutedgrey">Up to 50 staff • 10,000 mins</p>
          </div>
        </div>
      </div>

      {/* Tenant Directory Table */}
      <div className="glass-panel p-6 sm:p-7 rounded-3xl border border-graphite space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-ivory">Tenant Directory & Management</h3>
            <p className="text-xs text-mutedgrey">
              Configure tenant subscriptions, inspect voice volume, and toggle active states.
            </p>
          </div>

          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 text-mutedgrey absolute left-3.5 top-3" />
            <input
              type="text"
              placeholder="Search by business, email, phone..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="glass-input w-full pl-10 pr-4 py-2 text-xs font-medium"
            />
          </div>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-white/5">
          <table className="w-full text-left text-xs">
            <thead className="bg-warmblack text-mutedgrey uppercase tracking-wider text-[10px] font-mono border-b border-white/5">
              <tr>
                <th className="py-3 px-4">Business Tenant</th>
                <th className="py-3 px-4">Vertical</th>
                <th className="py-3 px-4">Subscription Plan</th>
                <th className="py-3 px-4">Staff Count</th>
                <th className="py-3 px-4">Calls / Appts</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 bg-charcoal/50">
              {filteredBusinesses.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-mutedgrey text-xs">
                    No business tenants match the current query.
                  </td>
                </tr>
              ) : (
                filteredBusinesses.map((biz) => (
                  <tr key={biz.id} className="hover:bg-warmblack/40 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-ivory">{biz.name}</div>
                      <div className="text-[11px] text-mutedgrey font-mono">{biz.email || biz.phone}</div>
                    </td>
                    <td className="py-3.5 px-4 capitalize text-mutedgrey">
                      {biz.vertical || 'Clinic'}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase ${
                        biz.plan === 'enterprise'
                          ? 'bg-amber/15 text-amber border border-amber/30'
                          : biz.plan === 'professional'
                          ? 'bg-burnt/15 text-burnt border border-burnt/30'
                          : 'bg-graphite text-ivory border border-white/10'
                      }`}>
                        {biz.plan || 'Starter'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-ivory">
                      {biz.total_staff || 1}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-mutedgrey">
                      <span className="text-ivory font-bold">{biz.total_calls || 0}</span> calls •{' '}
                      <span className="text-amber font-bold">{biz.total_appointments || 0}</span> appts
                    </td>
                    <td className="py-3.5 px-4">
                      <button
                        onClick={() => handleToggleStatus(biz)}
                        className="flex items-center gap-1.5 focus:outline-none"
                        title={biz.is_active ? 'Click to Suspend' : 'Click to Activate'}
                      >
                        {biz.is_active ? (
                          <span className="text-emerald-400 flex items-center gap-1 text-[11px] font-bold">
                            <ToggleRight className="w-6 h-6 text-emerald-400" />
                            Active
                          </span>
                        ) : (
                          <span className="text-rose-400 flex items-center gap-1 text-[11px] font-bold">
                            <ToggleLeft className="w-6 h-6 text-rose-400" />
                            Suspended
                          </span>
                        )}
                      </button>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => handleOpenPlanModal(biz)}
                        className="px-3 py-1.5 rounded-xl bg-graphite hover:bg-burnt/20 hover:text-burnt text-ivory border border-white/10 text-xs font-semibold transition-colors"
                      >
                        Manage Tier
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal: Update Tenant Subscription Plan */}
      <Modal
        isOpen={planModal}
        onClose={() => setPlanModal(false)}
        title={`Manage Subscription: ${selectedBiz?.name || ''}`}
      >
        <form onSubmit={handleSavePlan} className="space-y-4">
          <p className="text-xs text-mutedgrey">
            Adjust the platform tier for this business tenant. This updates available staff quotas,
            monthly voice minutes, and telephony integrations instantly.
          </p>

          <div className="space-y-3 pt-2">
            {[
              {
                id: 'starter',
                name: 'Starter Plan',
                price: '₹2,499 / mo',
                details: '2 Staff • 500 Monthly Voice Minutes • Basic OpenAI Voice',
              },
              {
                id: 'professional',
                name: 'Professional Plan',
                price: '₹6,999 / mo',
                details: '10 Staff • 2,000 Monthly Voice Minutes • Deepgram & ElevenLabs',
              },
              {
                id: 'enterprise',
                name: 'Enterprise Plan',
                price: '₹18,999 / mo',
                details: '50 Staff • 10,000 Monthly Voice Minutes • Dedicated Smartflo SIP',
              },
            ].map((p) => {
              const isSelected = selectedPlan === p.id;
              return (
                <div
                  key={p.id}
                  onClick={() => setSelectedPlan(p.id)}
                  className={`p-4 rounded-2xl border cursor-pointer transition-all flex items-start justify-between ${
                    isSelected
                      ? 'bg-burnt/15 border-burnt ring-1 ring-burnt text-ivory'
                      : 'glass-card border-white/10 text-mutedgrey hover:border-white/20'
                  }`}
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h4 className="text-xs font-bold text-ivory">{p.name}</h4>
                      <span className="text-[10px] font-mono text-amber font-bold">{p.price}</span>
                    </div>
                    <p className="text-[11px] text-mutedgrey">{p.details}</p>
                  </div>
                  {isSelected && <Check className="w-4 h-4 text-burnt mt-1 shrink-0" />}
                </div>
              );
            })}
          </div>

          <div className="pt-4 flex items-center justify-end gap-2 border-t border-white/5">
            <button
              type="button"
              onClick={() => setPlanModal(false)}
              className="px-4 py-2 text-xs font-semibold text-mutedgrey hover:text-ivory"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={updating}
              className="px-5 py-2.5 bg-gradient-to-r from-burnt to-amber text-warmblack font-extrabold rounded-xl text-xs uppercase tracking-wider disabled:opacity-50"
            >
              {updating ? 'Updating...' : 'Save Plan Allocation'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
