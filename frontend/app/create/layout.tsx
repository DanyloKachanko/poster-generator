import ModuleLayout from '@/components/ModuleLayout';

const tabs = [
  { href: '/create', label: 'Generate' },
  { href: '/create/batch', label: 'Batch' },
  { href: '/create/history', label: 'History' },
];

export default function CreateLayout({ children }: { children: React.ReactNode }) {
  return <ModuleLayout tabs={tabs}>{children}</ModuleLayout>;
}
