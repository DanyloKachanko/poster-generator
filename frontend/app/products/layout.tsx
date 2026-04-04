'use client';

import { usePathname } from 'next/navigation';
import ModuleLayout from '@/components/ModuleLayout';

const tabs = [
  { href: '/products', label: 'All Products' },
  { href: '/products/seo', label: 'SEO' },
  { href: '/products/sync', label: 'Sync' },
  { href: '/products/import-export', label: 'Import/Export' },
];

export default function ProductsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Don't show tabs on product detail pages like /products/abc123
  const isDetailPage = pathname.match(/^\/products\/[^/]+$/) && pathname !== '/products/seo' && pathname !== '/products/sync' && pathname !== '/products/import-export';

  if (isDetailPage) return <>{children}</>;
  return <ModuleLayout tabs={tabs}>{children}</ModuleLayout>;
}
