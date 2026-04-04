'use client';

import { usePathname } from 'next/navigation';
import ModuleLayout from '@/components/ModuleLayout';

const tabs = [
  { href: '/products', label: 'All Products' },
  { href: '/products/seo', label: 'SEO' },
  { href: '/products/sync', label: 'Sync' },
  { href: '/products/import-export', label: 'Import/Export' },
  { href: '/products/digital-downloads', label: 'Digital Downloads' },
  { href: '/products/digital-editor', label: 'Digital Editor' },
];

export default function ProductsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Don't show tabs on product detail pages like /products/abc123
  const isDetailPage = pathname.match(/^\/products\/[^/]+$/) && !pathname.startsWith('/products/seo') && !pathname.startsWith('/products/sync') && !pathname.startsWith('/products/import-export') && !pathname.startsWith('/products/digital');

  if (isDetailPage) return <>{children}</>;
  return <ModuleLayout tabs={tabs}>{children}</ModuleLayout>;
}
