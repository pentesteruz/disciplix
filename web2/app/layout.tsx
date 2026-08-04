import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import { TelegramProvider } from '@/lib/telegram-provider'
import Script from 'next/script'
import './globals.css'

const inter = Inter({ 
  subsets: ["latin"],
  variable: '--font-inter'
});

export const metadata: Metadata = {
  title: 'Disciplix - AI Finance & Discipline Coach',
  description: 'Your AI-driven personal finance and discipline coach',
  generator: 'v0.app',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <head>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
        <script dangerouslySetInnerHTML={{ __html: `
          (function() {
            if (typeof window !== 'undefined') {
              if (window.location.pathname.startsWith('/privacy')) {
                return;
              }
              var isTelegram = !!(window.Telegram?.WebApp?.initData);
              var isTgUrl = window.location.hash.includes('tgWebAppData') || 
                            window.location.search.includes('tgWebApp') || 
                            window.location.search.includes('user_id');
              var isLocalDev = window.location.hostname === 'localhost' || 
                               window.location.hostname === '127.0.0.1';
              if (!isTelegram && !isTgUrl && !isLocalDev) {
                document.documentElement.style.display = 'none';
                window.location.href = 'https://disciplix.uz';
              }
            }
          })()
        ` }} />
      </head>
      <body className={`${inter.variable} font-sans antialiased`}>
        <TelegramProvider>
          {children}
          <Analytics />
        </TelegramProvider>
      </body>
    </html>
  )
}
