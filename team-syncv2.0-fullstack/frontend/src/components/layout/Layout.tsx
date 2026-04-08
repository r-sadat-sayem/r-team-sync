// components/layout/Layout.tsx
import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

const ITERATION = 1;

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  // Close sidebar on route change (mobile UX)
  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  // Prevent body scroll when mobile sidebar is open
  useEffect(() => {
    if (sidebarOpen) {
      document.body.classList.add('sidebar-open');
    } else {
      document.body.classList.remove('sidebar-open');
    }
    return () => document.body.classList.remove('sidebar-open');
  }, [sidebarOpen]);

  return (
    <div className="h-screen overflow-hidden bg-background-primary flex relative">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Mobile backdrop overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      <div className="flex-1 flex flex-col md:ml-16 lg:ml-64 min-w-0 transition-[margin] duration-300">
        <Header
          onMenuToggle={() => setSidebarOpen(prev => !prev)}
          sidebarOpen={sidebarOpen}
        />
        <main className="flex-1 overflow-y-auto p-4 lg:p-6 min-h-0">
          {children}
        </main>
      </div>

      {/* Iteration badge — bottom-right corner */}
      <div className="fixed bottom-3 right-3 z-50 pointer-events-none">
        <span className="text-[10px] font-mono text-text-muted/50 bg-background-secondary/60 border border-white/5 rounded px-1.5 py-0.5 select-none">
          v2.0 · iter {ITERATION}
        </span>
      </div>
    </div>
  );
}
