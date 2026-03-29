'use client';

import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

export function PageWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isHome = pathname === '/';
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  if (isHome) {
    return <>{children}</>;
  }

  return (
    <div className="h-screen flex overflow-hidden">
      <Sidebar collapsed={sidebarCollapsed} onToggleCollapsed={() => setSidebarCollapsed((value) => !value)} />
      <Header sidebarCollapsed={sidebarCollapsed} />
      <main
        className={`flex-1 min-h-0 mt-16 p-6 bg-bg-base h-[calc(100vh-64px)] overflow-y-auto transition-[margin] duration-200 ${
          sidebarCollapsed ? 'ml-[88px]' : 'ml-[240px]'
        }`}
      >
        {children}
      </main>
    </div>
  );
}
