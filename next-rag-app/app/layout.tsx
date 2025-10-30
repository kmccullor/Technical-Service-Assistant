import type { Metadata } from 'next'
import './globals.css'
import { AuthProvider } from '@/src/context/AuthContext'

export const metadata: Metadata = {
  title: 'Technical Services Assistant',
  description: 'Intelligent document search and chat with RAG capabilities',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <AuthProvider>
          <div className="min-h-screen bg-background">
            {children}
          </div>
        </AuthProvider>
      </body>
    </html>
  )
}
