'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { getApiUrl } from '@/lib/api';
import { isAuthenticated } from '@/lib/auth';

/**
 * Checks if backend requires auth. If yes and no token, redirects to /login.
 * Locally (REQUIRE_AUTH not set), backend never returns 401, so this is transparent.
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (pathname === '/login') {
      setReady(true);
      return;
    }

    // If we have a token, show the app (authFetch handles expiry)
    if (isAuthenticated()) {
      setReady(true);
      return;
    }

    // No token — probe backend to see if auth is required
    fetch(`${getApiUrl()}/styles`)
      .then((r) => {
        if (r.status === 401) {
          router.replace('/login');
        } else {
          setReady(true); // auth not required
        }
      })
      .catch(() => setReady(true)); // backend unreachable, show anyway
  }, [pathname, router]);

  if (!ready) return null;
  return <>{children}</>;
}
