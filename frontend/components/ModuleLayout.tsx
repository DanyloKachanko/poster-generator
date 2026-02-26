'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export interface ModuleTab {
  href: string;
  label: string;
}

interface ModuleLayoutProps {
  tabs: ModuleTab[];
  children: React.ReactNode;
}

export default function ModuleLayout({ tabs, children }: ModuleLayoutProps) {
  const pathname = usePathname();

  if (tabs.length <= 1) return <>{children}</>;

  return (
    <div>
      <div className="border-b border-dark-border bg-dark-card/50">
        <div className="max-w-7xl mx-auto px-4">
          <nav className="flex gap-0.5 -mb-px">
            {tabs.map((tab) => {
              const isActive = pathname === tab.href;
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                    isActive
                      ? 'border-accent text-accent'
                      : 'border-transparent text-gray-400 hover:text-gray-200 hover:border-gray-600'
                  }`}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
      {children}
    </div>
  );
}
