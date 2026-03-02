import ModuleLayout from '@/components/ModuleLayout';

const tabs = [
  { href: '/monitor', label: 'Overview' },
  { href: '/monitor/analytics', label: 'Analytics' },
  { href: '/monitor/competitors', label: 'Competitors' },
  { href: '/monitor/dovshop', label: 'DovShop' },
];

export default function MonitorLayout({ children }: { children: React.ReactNode }) {
  return <ModuleLayout tabs={tabs}>{children}</ModuleLayout>;
}
