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
      <body className="bg-gray-950 text-gray-100 min-h-screen antialiased">
        {children}
      </body>
    </html>
  )
}
