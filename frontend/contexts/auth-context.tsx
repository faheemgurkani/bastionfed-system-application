'use client';

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
  GoogleAuthProvider,
  type User,
} from 'firebase/auth';
import { doc, getDoc, setDoc, serverTimestamp } from 'firebase/firestore';
import { auth, db } from '@/lib/firebase';
import type { UserProfile } from '@/lib/types';
import { apiFetchJson } from '@/lib/api';

const GUEST_STORAGE_KEY = 'bastionfed_guest';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  isGuest: boolean;
  signInWithGoogle: () => Promise<void>;
  signOutUser: () => Promise<void>;
  continueAsGuest: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

async function upsertUserProfile(user: User): Promise<void> {
  const profile: Omit<UserProfile, 'createdAt' | 'lastLoginAt'> & {
    createdAt: ReturnType<typeof serverTimestamp>;
    lastLoginAt: ReturnType<typeof serverTimestamp>;
  } = {
    uid: user.uid,
    email: user.email ?? null,
    displayName: user.displayName ?? null,
    photoURL: user.photoURL ?? null,
    createdAt: serverTimestamp(),
    lastLoginAt: serverTimestamp(),
  };
  await setDoc(doc(db, 'users', user.uid), profile, { merge: true });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isGuest, setIsGuest] = useState(false);

  useEffect(() => {
    const stored = typeof window !== 'undefined' && localStorage.getItem(GUEST_STORAGE_KEY);
    if (stored === 'true') setIsGuest(true);
  }, []);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      if (firebaseUser) {
        setIsGuest(false);
        if (typeof window !== 'undefined') localStorage.removeItem(GUEST_STORAGE_KEY);
        try {
          await upsertUserProfile(firebaseUser);
          const token = await firebaseUser.getIdToken();
          await apiFetchJson('/api/auth/session', {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
            body: JSON.stringify({
              uid: firebaseUser.uid,
              email: firebaseUser.email ?? null,
              displayName: firebaseUser.displayName ?? null,
              photoURL: firebaseUser.photoURL ?? null,
            }),
          });
        } catch (err) {
          console.error('Failed to upsert user profile or backend session', err);
        }
      }
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const signInWithGoogle = async () => {
    const provider = new GoogleAuthProvider();
    await signInWithPopup(auth, provider);
  };

  const continueAsGuest = () => {
    setIsGuest(true);
    if (typeof window !== 'undefined') localStorage.setItem(GUEST_STORAGE_KEY, 'true');
  };

  const signOutUser = async () => {
    await firebaseSignOut(auth);
    setIsGuest(false);
    if (typeof window !== 'undefined') localStorage.removeItem(GUEST_STORAGE_KEY);
  };

  const value: AuthContextValue = {
    user,
    loading,
    isGuest,
    signInWithGoogle,
    signOutUser,
    continueAsGuest,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
