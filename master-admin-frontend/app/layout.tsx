import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'CORTEX Master Control Plane',
  description: 'Manage all CORTEX company deployments',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
