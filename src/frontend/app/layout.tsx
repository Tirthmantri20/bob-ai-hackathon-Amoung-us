import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'SupplyGuard AI — Control Tower',
  description: 'Autonomous Supply Chain Disruption Intelligence powered by IBM watsonx.ai',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-slate-100 text-slate-800 min-h-screen antialiased">
        {children}
      </body>
    </html>
  )
}
