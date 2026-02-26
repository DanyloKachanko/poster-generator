'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { getCredits, CreditsResponse } from '@/lib/api';
import { isAuthenticated, logout } from '@/lib/auth';

const pipelineNav = [
  { href: '/strategy', label: 'Strategy' },
  { href: '/create', label: 'Create' },
  { href: '/products', label: 'Products' },
  { href: '/mockups', label: 'Mockups' },
  { href: '/publish', label: 'Publish' },
  { href: '/monitor', label: 'Monitor' },
];

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
          <Link href="/monitor" className="text-lg font-bold text-gray-100 flex-shrink-0">
            DovShop
          </Link>

          <nav className="flex items-center gap-0.5">
            {pipelineNav.map((item) => {
              const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-accent/15 text-accent'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-dark-hover'
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
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
