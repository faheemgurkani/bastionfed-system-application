import './globals.css';
import type { Metadata } from 'next';
import { AuthProvider } from '@/contexts/auth-context';
import { ViewModeProvider } from '@/contexts/view-mode-context';
import { AlertsProvider } from '@/contexts/alerts-context';
import { FLClientsProvider } from '@/contexts/fl-clients-context';
import { PageWrapper } from '@/components/layout/PageWrapper';

export const metadata: Metadata = {
  title: 'BastionFed | IoMT SOC',
  description: 'Blue Team platform for IoMT with tenant-scoped ingest, ATT&CK-mapped triage, forensics workflows, and research/demo FL surfaces.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className="scroll-smooth dark"
    >
      <body className="bg-bg-base text-text-primary font-sans antialiased">
        <AuthProvider>
          <ViewModeProvider>
            <AlertsProvider>
              <FLClientsProvider>
                <PageWrapper>{children}</PageWrapper>
              </FLClientsProvider>
            </AlertsProvider>
          </ViewModeProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
