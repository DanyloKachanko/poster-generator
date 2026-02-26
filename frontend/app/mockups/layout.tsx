import ModuleLayout from '@/components/ModuleLayout';

const tabs = [
  { href: '/mockups', label: 'Templates' },
  { href: '/mockups/workflow', label: 'Workflow' },
];

export default function MockupsLayout({ children }: { children: React.ReactNode }) {
  return <ModuleLayout tabs={tabs}>{children}</ModuleLayout>;
}
