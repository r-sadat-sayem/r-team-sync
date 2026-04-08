// components/layout/Sidebar.tsx

import { NavLink } from 'react-router-dom';
import { MessageSquare, FileText, Mail, Ticket, LayoutDashboard, History, Folders, X } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { api } from '../../services/api';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

const navItems = [
  { to: '/',          icon: MessageSquare,  label: 'Chat' },
  { to: '/history',   icon: History,        label: 'History' },
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/prd',       icon: FileText,       label: 'PRD Viewer' },
  { to: '/email',     icon: Mail,           label: 'Email' },
  { to: '/jira',      icon: Ticket,         label: 'JIRA' },
  { to: '/projects',  icon: Folders,        label: 'Projects' },
];

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  return (
    <aside
      className={cn(
        'fixed left-0 top-0 h-full z-40 flex flex-col',
        'bg-background-secondary border-r border-white/8',
        'transition-all duration-300 ease-in-out w-64',
        isOpen ? 'translate-x-0' : '-translate-x-full',
        'md:translate-x-0 md:w-16 lg:w-64'
      )}
    >
      {/* Logo */}
      <div className="p-4 lg:p-6 border-b border-white/8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 lg:w-10 lg:h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center text-white font-bold text-base lg:text-lg flex-shrink-0">
            T
          </div>
          <div className="hidden lg:block overflow-hidden">
            <h1 className="font-bold text-text-primary whitespace-nowrap">TeamSync AI</h1>
            <p className="text-xs text-text-muted whitespace-nowrap">PRD Automation</p>
          </div>
        </div>
        {/* Close button — mobile only */}
        <button
          onClick={onClose}
          className="lg:hidden p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-white/8 transition-colors"
          aria-label="Close sidebar"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 lg:p-4 space-y-1">
        {navItems.map((item) => {
          const historyCount = item.to === '/history' ? api.getPRDHistory().length : 0;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              data-label={item.label}
              className={({ isActive }) =>
                cn(
                  'sidebar-nav-item flex items-center gap-3 px-3 py-3 lg:px-4 rounded-lg transition-all duration-200 relative',
                  'md:justify-center lg:justify-start',
                  isActive
                    ? 'bg-primary/20 text-primary-light border border-primary/30'
                    : 'text-text-secondary hover:bg-white/5 hover:text-text-primary'
                )
              }
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              <span className="font-medium flex-1 hidden lg:block">{item.label}</span>
              {/* Full badge — desktop */}
              {historyCount > 0 && (
                <span className="hidden lg:inline-flex px-1.5 py-0.5 text-xs font-bold rounded-full bg-primary/30 text-primary-light min-w-[20px] text-center">
                  {historyCount}
                </span>
              )}
              {/* Dot badge — tablet icon-only */}
              {historyCount > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-primary lg:hidden" aria-hidden="true" />
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-3 lg:p-4 border-t border-white/8">
        <div className="flex items-center justify-center lg:justify-start gap-2 text-xs text-text-muted">
          <div className="w-2 h-2 rounded-full bg-status-success animate-pulse flex-shrink-0" />
          <span className="hidden lg:block">System Online</span>
        </div>
        <p className="text-xs text-text-muted mt-2 hidden lg:block">v2.1</p>
      </div>
    </aside>
  );
}
