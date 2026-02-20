'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { getCredits, CreditsResponse } from '@/lib/api';
import { isAuthenticated, logout } from '@/lib/auth';

interface NavGroup {
  label: string;
  items: { href: string; label: string }[];
}

const primaryNav = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/products', label: 'Products' },
  { href: '/seo', label: 'SEO' },
];

const navGroups: NavGroup[] = [
  {
    label: 'Create',
    items: [
      { href: '/', label: 'Generate' },
      { href: '/batch', label: 'Batch' },
      { href: '/batch?tab=presets', label: 'Presets' },
      { href: '/strategy', label: 'Strategy' },
      { href: '/history', label: 'History' },
    ],
  },
  {
    label: 'Publish',
    items: [
      { href: '/shop', label: 'Shop' },
      { href: '/mockups', label: 'Mockups' },
      { href: '/mockups/generate', label: 'Mockup Gen' },
      { href: '/mockups/workflow', label: 'Workflow' },
      { href: '/schedule', label: 'Schedule' },
      { href: '/calendar', label: 'Calendar' },
      { href: '/dovshop', label: 'DovShop' },
      { href: '/sync-etsy', label: 'Sync Etsy' },
    ],
  },
  {
    label: 'Stats',
    items: [
      { href: '/analytics', label: 'Analytics' },
      { href: '/providers', label: 'Providers' },
      { href: '/competitors', label: 'Competitors' },
    ],
  },
];

// All hrefs for checking if a group is active
const allGroupHrefs = navGroups.flatMap((g) => g.items.map((i) => i.href));

function DropdownMenu({ group, pathname }: { group: NavGroup; pathname: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const isGroupActive = group.items.some((item) => item.href === pathname);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1 ${
          isGroupActive
            ? 'bg-accent/15 text-accent'
            : 'text-gray-400 hover:text-gray-200 hover:bg-dark-hover'
        }`}
      >
        {group.label}
        <svg
          className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 bg-dark-card border border-dark-border rounded-lg shadow-xl py-1 min-w-[140px] z-50">
          {group.items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={`block px-4 py-2 text-sm transition-colors ${
                pathname === item.href
                  ? 'bg-accent/15 text-accent'
                  : 'text-gray-300 hover:text-gray-100 hover:bg-dark-hover'
              }`}
            >
              {item.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Header() {
  const pathname = usePathname();
  const [credits, setCredits] = useState<CreditsResponse | null>(null);

  useEffect(() => {
    getCredits().then(setCredits).catch(console.error);
  }, [pathname]);

  useEffect(() => {
    const handler = () => {
      getCredits().then(setCredits).catch(console.error);
    };
    window.addEventListener('credits-refresh', handler);
    return () => window.removeEventListener('credits-refresh', handler);
  }, []);

  return (
    <header className="border-b border-dark-border bg-dark-card/80 backdrop-blur-sm sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <div className="flex items-center gap-5">
          <Link href="/dashboard" className="text-lg font-bold text-gray-100 flex-shrink-0">
            DovShop
          </Link>

          <nav className="flex items-center gap-0.5">
            {/* Primary links — always visible */}
            {primaryNav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  pathname === item.href
                    ? 'bg-accent/15 text-accent'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-dark-hover'
                }`}
              >
                {item.label}
              </Link>
            ))}

            {/* Separator */}
            <div className="w-px h-5 bg-dark-border mx-1" />

            {/* Grouped dropdowns */}
            {navGroups.map((group) => (
              <DropdownMenu key={group.label} group={group} pathname={pathname} />
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0">
        {credits?.balance && (
          <div className="flex items-center gap-3 text-sm flex-shrink-0">
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-green-400" />
              <span className="font-medium text-gray-100">
                {credits.balance.api_total_tokens.toLocaleString()}
              </span>
              <span className="text-gray-500">tokens</span>
            </div>
            {credits.balance.api_token_renewal_date && (
              <span className="text-xs text-gray-600">
                renews{' '}
                {new Date(
                  credits.balance.api_token_renewal_date
                ).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                })}
              </span>
            )}
          </div>
        )}
        {isAuthenticated() && (
          <button
            onClick={logout}
            className="px-3 py-1.5 rounded-md text-sm text-gray-400 hover:text-gray-200 hover:bg-dark-hover transition-colors"
          >
            Logout
          </button>
        )}
        </div>
      </div>
    </header>
  );
}
