"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { FirebaseError } from "firebase/app";
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
  GoogleAuthProvider,
  type User,
} from "firebase/auth";
import { doc, getDoc, setDoc, serverTimestamp } from "firebase/firestore";
import { auth, db } from "@/lib/firebase";
import type { UserProfile } from "@/lib/types";
import { apiFetchJson } from "@/lib/api";

const GUEST_STORAGE_KEY = "bastionfed_guest";

function isRecoverableGooglePopupError(e: unknown): boolean {
  return (
    e instanceof FirebaseError &&
    (e.code === "auth/cancelled-popup-request" ||
      e.code === "auth/popup-blocked" ||
      e.code === "auth/popup-closed-by-user")
  );
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  isGuest: boolean;
  /** Resolves `true` if Google sign-in completed; `false` if user closed/blocked popup or a duplicate request. */
  signInWithGoogle: () => Promise<boolean>;
  signOutUser: () => Promise<void>;
  continueAsGuest: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

async function upsertUserProfile(user: User): Promise<void> {
  const profile: Omit<UserProfile, "createdAt" | "lastLoginAt"> & {
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
  await setDoc(doc(db, "users", user.uid), profile, { merge: true });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isGuest, setIsGuest] = useState(false);
  const googlePopupInFlight = useRef(false);

  useEffect(() => {
    const stored =
      typeof window !== "undefined" && localStorage.getItem(GUEST_STORAGE_KEY);
    if (stored === "true") setIsGuest(true);
  }, []);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      if (firebaseUser) {
        setIsGuest(false);
        if (typeof window !== "undefined")
          localStorage.removeItem(GUEST_STORAGE_KEY);
        try {
          await upsertUserProfile(firebaseUser);
          const token = await firebaseUser.getIdToken();
          await apiFetchJson("/api/auth/session", {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
            body: JSON.stringify({
              uid: firebaseUser.uid,
              email: firebaseUser.email ?? null,
              displayName: firebaseUser.displayName ?? null,
              photoURL: firebaseUser.photoURL ?? null,
            }),
          });
        } catch (err) {
          console.error(
            "Failed to upsert user profile or backend session",
            err,
          );
        }
      }
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const signInWithGoogle = async (): Promise<boolean> => {
    if (googlePopupInFlight.current) {
      console.warn(
        "[auth] Google sign-in already in progress; ignoring duplicate request.",
      );
      return false;
    }
    googlePopupInFlight.current = true;
    try {
      const provider = new GoogleAuthProvider();
      await signInWithPopup(auth, provider);
      return true;
    } catch (e) {
      if (isRecoverableGooglePopupError(e)) {
        console.warn(
          "[auth] Google popup:",
          e instanceof FirebaseError ? e.code : e,
        );
        return false;
      }
      console.error("[auth] Google sign-in failed", e);
      throw e;
    } finally {
      googlePopupInFlight.current = false;
    }
  };

  const continueAsGuest = () => {
    setIsGuest(true);
    if (typeof window !== "undefined")
      localStorage.setItem(GUEST_STORAGE_KEY, "true");
  };

  const signOutUser = async () => {
    await firebaseSignOut(auth);
    setIsGuest(false);
    if (typeof window !== "undefined")
      localStorage.removeItem(GUEST_STORAGE_KEY);
  };

  const value: AuthContextValue = {
    user,
    loading,
    isGuest,
    signInWithGoogle,
    signOutUser,
    continueAsGuest,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
