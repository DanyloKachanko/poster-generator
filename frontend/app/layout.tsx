import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import AuthGuard from '@/components/AuthGuard'
import LayoutShell from '@/components/LayoutShell'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Poster Generator',
  description: 'Generate beautiful posters using AI',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <AuthGuard>
          <LayoutShell>{children}</LayoutShell>
        </AuthGuard>
      </body>
    </html>
  )
}
