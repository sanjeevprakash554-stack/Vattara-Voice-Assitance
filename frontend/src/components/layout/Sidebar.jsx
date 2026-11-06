import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Bot,
  PhoneCall,
  CalendarDays,
  Users,
  BellRing,
  BarChart3,
  Settings,
  AudioWaveform,
  Activity,
  Radio,
} from 'lucide-react';
import { motion } from 'framer-motion';

const navigation = [
  { name: 'Console', href: '/', icon: LayoutDashboard },
  { name: 'AI Voice Agent', href: '/assistant', icon: Bot, badge: 'Live' },
  { name: 'Call Monitor', href: '/calls', icon: PhoneCall },
  { name: 'Appointments', href: '/appointments', icon: CalendarDays },
  { name: 'Customer Hub', href: '/customers', icon: Users },
  { name: 'Reminders', href: '/reminders', icon: BellRing },
  { name: 'Analytics', href: '/reports', icon: BarChart3 },
  { name: 'Organization', href: '/settings', icon: Settings },
];

export default function Sidebar({ isOpen, onClose }) {
  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-warmblack/80 backdrop-blur-md lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-40 w-64 glass-panel flex flex-col border-r border-ivory/10 transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-6 h-20 border-b border-ivory/10 bg-graphite/30">
          <div className="relative w-10 h-10 rounded-2xl bg-gradient-to-tr from-burnt to-amber flex items-center justify-center text-warmblack shadow-lg shadow-burnt/25">
            <AudioWaveform className="w-5 h-5 animate-pulse" />
            <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-charcoal animate-ping" />
          </div>

          <div>
            <span className="font-extrabold text-ivory text-base tracking-tight block">
              VATTARA
            </span>
            <span className="text-[10px] uppercase font-mono font-bold tracking-widest text-amber block -mt-0.5">
              Voice Intelligence
            </span>
          </div>
        </div>

        {/* Navigation list */}
        <div className="flex-1 px-3 py-6 space-y-1.5 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-mono uppercase font-bold tracking-widest text-mutedgrey/70">
            Platform Matrix
          </div>

          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              onClick={onClose}
              end={item.href === '/'}
              className={({ isActive }) =>
                `group relative flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold tracking-wide transition-all duration-200 ${
                  isActive
                    ? 'bg-gradient-to-r from-burnt/20 via-burnt/10 to-transparent text-ivory border-l-2 border-burnt'
                    : 'text-mutedgrey hover:text-ivory hover:bg-graphite/40'
                }`
              }
            >
              <div className="flex items-center gap-3">
                <item.icon className="w-4 h-4 transition-transform duration-200 group-hover:scale-110" />
                <span>{item.name}</span>
              </div>

              {item.badge && (
                <span className="text-[9px] font-mono font-bold px-2 py-0.5 rounded-full bg-burnt/15 text-burnt border border-burnt/30 uppercase tracking-wider">
                  {item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </div>

        {/* AI Agent Telemetry Footer Widget */}
        <div className="p-3 m-3 rounded-2xl glass-card border border-ivory/10 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[11px] font-bold text-ivory">Neural Core 3.8</span>
            </div>
            <span className="text-[9px] font-mono text-mutedgrey">~420ms</span>
          </div>

          <p className="text-[11px] text-mutedgrey leading-relaxed">
            Realtime speech-to-speech conversational engine connected.
          </p>

          <div className="pt-1 flex items-center justify-between text-[10px] text-amber font-mono font-semibold">
            <span className="flex items-center gap-1">
              <Radio className="w-3 h-3 text-burnt animate-pulse" /> Twilio Trunk
            </span>
            <span className="text-emerald-400">99.9% Up</span>
          </div>
        </div>
      </aside>
    </>
  );
}
