import { Inter, JetBrains_Mono, Space_Mono, Bebas_Neue } from 'next/font/google';
import './globals.css';
import type { Metadata } from 'next';
import { AuthProvider } from '@/contexts/auth-context';
import { AlertsProvider } from '@/contexts/alerts-context';
import { FLClientsProvider } from '@/contexts/fl-clients-context';
import { PageWrapper } from '@/components/layout/PageWrapper';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  weight: ['400', '500', '600'],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
  weight: ['400', '500'],
});

const spaceMono = Space_Mono({
  subsets: ['latin'],
  variable: '--font-space-mono',
  weight: ['400', '700'],
});

const bebasNeue = Bebas_Neue({
  subsets: ['latin'],
  variable: '--font-bebas',
  weight: '400',
});

export const metadata: Metadata = {
  title: 'BastionFed | IoMT SOC',
  description: 'Enterprise Blue Team platform for IoMT: federated learning detection, SIEM-style correlation, ATT&CK mapping, SOAR playbooks, and forensics—privacy by design, analyst-centric.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} ${spaceMono.variable} ${bebasNeue.variable} scroll-smooth dark`}
    >
      <body className="bg-bg-base text-text-primary font-sans antialiased">
        <AuthProvider>
          <AlertsProvider>
            <FLClientsProvider>
              <PageWrapper>{children}</PageWrapper>
            </FLClientsProvider>
          </AlertsProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
