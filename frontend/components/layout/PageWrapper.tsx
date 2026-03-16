'use client';

import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { usePathname } from 'next/navigation';

export function PageWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isHome = pathname === '/';

  if (isHome) {
    return <>{children}</>;
  }

  return (
    <div className="h-screen flex overflow-hidden">
      <Sidebar />
      <Header />
      <main className="flex-1 min-h-0 ml-[240px] mt-16 p-6 bg-bg-base h-[calc(100vh-64px)] overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
