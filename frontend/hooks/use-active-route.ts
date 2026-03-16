import { usePathname } from 'next/navigation';
import { useState, useEffect } from 'react';

export function useActiveRoute() {
  const pathname = usePathname();
  const [activeRoute, setActiveRoute] = useState(pathname);

  useEffect(() => {
    setActiveRoute(pathname);
  }, [pathname]);

  return activeRoute;
}
