import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { PhoneCall, Sparkles } from 'lucide-react';
import Sidebar from './Sidebar';
import Header from './Header';

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [notification, setNotification] = useState(null);

  const handleCallSimulated = (call) => {
    setNotification({
      title: 'AI Call Simulated Successfully',
      caller: call.caller_name || call.caller_phone,
      duration: `${call.duration_seconds}s`,
    });
    setTimeout(() => setNotification(null), 6000);
  };

  return (
    <div className="min-h-screen bg-warmblack text-ivory flex relative overflow-hidden bg-mesh-pattern">
      {/* Background atmospheric energy glow gradients */}
      <div className="fixed top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full bg-burnt/[0.04] blur-[140px] pointer-events-none" />
      <div className="fixed bottom-[-20%] right-[-10%] w-[600px] h-[600px] rounded-full bg-amber/[0.04] blur-[140px] pointer-events-none" />
      <div className="fixed top-[40%] right-[30%] w-[450px] h-[450px] rounded-full bg-lavender/[0.03] blur-[160px] pointer-events-none" />

      {/* Persistent Left Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-64 z-10">
        <Header
          onMenuClick={() => setSidebarOpen(true)}
          onCallSimulated={handleCallSimulated}
        />

        {/* Global Toast for real-time telephony actions */}
        <AnimatePresence>
          {notification && (
            <motion.div
              initial={{ opacity: 0, y: 30, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              className="fixed bottom-6 right-6 z-50 glass-panel-glow text-ivory px-5 py-4 rounded-2xl shadow-2xl flex items-center gap-4 border border-burnt/40"
            >
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-burnt to-amber flex items-center justify-center text-warmblack shadow-md shadow-burnt/30">
                <PhoneCall className="w-5 h-5 animate-bounce" />
              </div>

              <div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  <p className="text-xs font-bold text-ivory">{notification.title}</p>
                </div>
                <p className="text-[11px] text-mutedgrey mt-0.5">
                  Caller: <span className="text-amber font-mono font-bold">{notification.caller}</span> • Duration: {notification.duration}
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
