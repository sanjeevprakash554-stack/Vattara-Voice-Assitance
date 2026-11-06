import React, { useState } from 'react';
import {
  Menu,
  PhoneCall,
  ChevronDown,
  LogOut,
  User,
  Building2,
  Sparkles,
  Radio,
  Palette,
  Bell,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { useAuth } from '../../context/AuthContext';
import { callsService } from '../../services/api';
import LiveCallSimulatorModal from '../common/LiveCallSimulatorModal';
import ThemeCustomizerModal from '../theme/ThemeCustomizerModal';

export default function Header({ onMenuClick, onCallSimulated }) {
  const { user, business, logout } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [callModalOpen, setCallModalOpen] = useState(false);
  const [themeModalOpen, setThemeModalOpen] = useState(false);

  const handleOpenSimulator = () => {
    setCallModalOpen(true);
  };

  return (
    <header className="sticky top-0 z-30 flex h-20 w-full items-center justify-between border-b border-ivory/10 bg-warmblack/70 backdrop-blur-xl px-4 sm:px-6 lg:px-8">
      {/* Left: Mobile Drawer Trigger & Business Context */}
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="rounded-xl p-2 text-mutedgrey hover:text-ivory hover:bg-graphite/60 lg:hidden"
        >
          <Menu className="w-6 h-6" />
        </button>

        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-2xl bg-charcoal border border-ivory/10 text-burnt hidden sm:flex items-center justify-center">
            <Building2 className="w-5 h-5" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold text-ivory tracking-wide">
                {business?.name || 'Vattara City Clinic & Diagnostics'}
              </h1>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider bg-burnt/15 text-burnt border border-burnt/30">
                <span className="w-1.5 h-1.5 rounded-full bg-burnt animate-ping" />
                {business?.vertical || 'Clinic'}
              </span>
            </div>

            <p className="text-[11px] font-mono text-mutedgrey mt-0.5 hidden sm:block">
              Connected Phone: <span className="text-ivory/80">{business?.phone || '+91 44 2828 9000'}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Right: Simulation Action & User Controls */}
      <div className="flex items-center gap-3">
        {/* Instant AI Phone Call Simulation Button */}
        <button
          onClick={handleOpenSimulator}
          className="relative group overflow-hidden flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-gradient-to-r from-burnt via-burnt to-amber text-warmblack font-bold text-xs shadow-lg shadow-burnt/25 hover:shadow-burnt/40 transition-all duration-200"
        >
          <PhoneCall className="w-4 h-4 animate-bounce" />
          <span className="tracking-wide hidden sm:inline">Test AI Phone Call</span>
          <span className="absolute inset-0 bg-ivory/20 opacity-0 group-hover:opacity-100 transition-opacity" />
        </button>

        {/* Theme Customizer Trigger */}
        <button
          onClick={() => setThemeModalOpen(true)}
          className="relative p-2.5 rounded-2xl glass-card border border-ivory/10 hover:border-burnt/50 text-ivory hover:text-burnt transition-all"
          title="Customize Theme & Palette"
        >
          <Palette className="w-4 h-4" />
          <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-burnt animate-pulse" />
        </button>

        {/* User Profile Dropdown */}
        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2.5 p-1.5 rounded-2xl glass-card border border-ivory/10 hover:border-ivory/20 transition-all"
          >
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-burnt to-lavender text-warmblack flex items-center justify-center font-bold text-xs uppercase shadow-sm">
              {user?.full_name?.charAt(0) || 'A'}
            </div>
            <div className="hidden md:block text-left text-xs">
              <span className="font-bold text-ivory block leading-tight">{user?.full_name || 'Administrator'}</span>
              <span className="text-[10px] font-mono text-mutedgrey block capitalize">{user?.role || 'Admin'}</span>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-mutedgrey" />
          </button>

          {dropdownOpen && (
            <div
              className="absolute right-0 mt-2 w-56 rounded-2xl glass-panel-glow border border-ivory/10 p-2 z-50 shadow-2xl"
              onClick={() => setDropdownOpen(false)}
            >
              <div className="px-3 py-2.5 border-b border-ivory/10 mb-1">
                <p className="text-xs font-bold text-ivory">{user?.full_name}</p>
                <p className="text-[11px] text-mutedgrey truncate font-mono">{user?.email}</p>
              </div>

              <a
                href="/settings"
                className="flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-ivory/80 hover:text-ivory hover:bg-graphite/60 rounded-xl transition-colors"
              >
                <User className="w-4 h-4 text-amber" />
                Profile & Settings
              </a>

              <button
                onClick={logout}
                className="flex items-center gap-2.5 w-full text-left px-3 py-2 text-xs font-semibold text-rose-400 hover:bg-rose-500/10 rounded-xl transition-colors mt-1"
              >
                <LogOut className="w-4 h-4" />
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Interactive Inbound Live Call Simulator Modal */}
      <LiveCallSimulatorModal
        isOpen={callModalOpen}
        onClose={() => setCallModalOpen(false)}
        onCallCompleted={(call) => {
          if (onCallSimulated) onCallSimulated(call);
        }}
      />

      {/* Theme Customization Slide-over Panel */}
      <ThemeCustomizerModal
        isOpen={themeModalOpen}
        onClose={() => setThemeModalOpen(false)}
      />
    </header>
  );
}
