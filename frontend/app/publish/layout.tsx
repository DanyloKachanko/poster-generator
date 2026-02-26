import ModuleLayout from '@/components/ModuleLayout';

const tabs = [
  { href: '/publish', label: 'Queue' },
  { href: '/publish/calendar', label: 'Calendar' },
  { href: '/publish/dovshop', label: 'DovShop' },
];

export default function PublishLayout({ children }: { children: React.ReactNode }) {
  return <ModuleLayout tabs={tabs}>{children}</ModuleLayout>;
}
