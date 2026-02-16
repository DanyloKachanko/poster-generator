'use client';

import { usePathname } from 'next/navigation';
import Header from './Header';

export default function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const hideHeader = pathname === '/login';

  return (
    <>
      {!hideHeader && <Header />}
      {children}
    </>
  );
}
