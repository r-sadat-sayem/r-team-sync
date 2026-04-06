// components/layout/Sidebar.tsx

import { NavLink } from 'react-router-dom';
import { MessageSquare, FileText, Mail, Ticket, LayoutDashboard } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const navItems = [
  { to: '/', icon: MessageSquare, label: 'Chat' },
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/prd', icon: FileText, label: 'PRD Viewer' },
  { to: '/email', icon: Mail, label: 'Email' },
  { to: '/jira', icon: Ticket, label: 'JIRA' },
];

export function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-full w-64 bg-background-secondary border-r border-white/8 flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-white/8">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-primary-light flex items-center justify-center text-white font-bold text-lg">
            T
          </div>
          <div>
            <h1 className="font-bold text-text-primary">TeamSync AI</h1>
            <p className="text-xs text-text-muted">PRD Automation</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200',
                isActive
                  ? 'bg-primary/20 text-primary-light border border-primary/30'
                  : 'text-text-secondary hover:bg-white/5 hover:text-text-primary'
              )
            }
          >
            <item.icon className="w-5 h-5" />
            <span className="font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-white/8">
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <div className="w-2 h-2 rounded-full bg-status-success animate-pulse" />
          <span>System Online</span>
        </div>
        <p className="text-xs text-text-muted mt-2">v2.1</p>
      </div>
    </aside>
  );
}
