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
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  type User,
} from "firebase/auth";
import { doc, setDoc, serverTimestamp } from "firebase/firestore";
import { auth, db } from "@/lib/firebase";
import type { UserProfile } from "@/lib/types";
import { apiFetchJson, ApiError } from "@/lib/api";
import { AccountTypeModal } from "@/components/auth/AccountTypeModal";
import { AdminSetupWizard } from "@/components/onboarding/AdminSetupWizard";
import type {
  ClientDef,
  ClientProvisionResult,
} from "@/components/onboarding/AdminSetupWizard";

/** Canonical dev-mode flag; legacy `bastionfed_guest` still read for migration. */
const DEV_MODE_STORAGE_KEY = "bastionfed_dev_mode";
const LEGACY_GUEST_STORAGE_KEY = "bastionfed_guest";
const PENDING_CLIENT_INVITE_KEY = "bastionfed_pending_client_invite_token";

type AuthBootstrapResponse = {
  hasMembership: boolean;
  tenantId: string | null;
  role: string | null;
};

type AuthSessionResponse = {
  tenantId: string | null;
  role: string | null;
  needsClientInvite: boolean;
  isNewTenant: boolean;
};

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
  isDevMode: boolean;
  /** Firebase user has completed backend session (tenant or explicit pending invite state handled). */
  sessionReady: boolean;
  /** Account type / client-credential onboarding (API session not established yet). */
  accountModalOpen: boolean;
  /** Post–sign-up admin wizard before dashboard (session intentionally not ready until finish). */
  adminWizardOpen: boolean;
  needsClientInvite: boolean;
  tenantId: string | null;
  role: string | null;
  signInWithGoogle: () => Promise<boolean>;
  signInWithEmailPassword: (
    email: string,
    password: string,
  ) => Promise<boolean>;
  registerWithEmailPassword: (
    email: string,
    password: string,
  ) => Promise<boolean>;
  signOutUser: () => Promise<void>;
  continueInDevMode: () => Promise<void>;
  submitAccountType: (t: "SYSTEM_OWNER" | "CLIENT_USER") => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

async function upsertUserProfile(user: User): Promise<void> {
  if (
    typeof process !== "undefined" &&
    process.env.NEXT_PUBLIC_SYNC_FIRESTORE_USER_PROFILE === "false"
  ) {
    return;
  }

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
  const [isDevMode, setIsDevMode] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [needsClientInvite, setNeedsClientInvite] = useState(false);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [accountModalBusy, setAccountModalBusy] = useState(false);
  const [accountInfoMessage, setAccountInfoMessage] = useState<string | null>(
    null,
  );
  /** Shows the admin-credential sign-in form instead of the type-selection buttons. */
  const [clientEntryMode, setClientEntryMode] = useState(false);
  const [adminWizardOpen, setAdminWizardOpen] = useState(false);
  const [adminWizardBusy, setAdminWizardBusy] = useState(false);
  const [adminWizardResults, setAdminWizardResults] = useState<
    ClientProvisionResult[] | null
  >(null);
  const [adminWizardLimits, setAdminWizardLimits] = useState<{
    maxClientsPerAdmin: number;
    alreadyProvisioned: number;
    remaining: number;
  } | null>(null);
  const googlePopupInFlight = useRef(false);
  const sessionSyncGeneration = useRef(0);
  /**
   * True while a client credential sign-in is in flight.
   * Prevents the intermediate auth/null event (triggered by Firebase signing out the
   * previous Google user before signing in with email/password) from closing the modal.
   */
  const clientSignInInProgress = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const v =
      localStorage.getItem(DEV_MODE_STORAGE_KEY) === "true" ||
      localStorage.getItem(LEGACY_GUEST_STORAGE_KEY) === "true";
    if (v) setIsDevMode(true);
  }, []);

  useEffect(() => {
    if (!adminWizardOpen || !user || isDevMode) {
      if (!adminWizardOpen) setAdminWizardLimits(null);
      return;
    }
    let cancelled = false;
    setAdminWizardLimits(null);
    void (async () => {
      try {
        const token = await user.getIdToken();
        const lim = await apiFetchJson<{
          maxClientsPerAdmin: number;
          alreadyProvisioned: number;
          remaining: number;
        }>("/api/onboarding/limits", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) setAdminWizardLimits(lim);
      } catch {
        if (!cancelled) setAdminWizardLimits(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [adminWizardOpen, user, isDevMode]);

  async function runSessionSync(firebaseUser: User, gen: number) {
    const token = await firebaseUser.getIdToken();
    const headers = { Authorization: `Bearer ${token}` };

    if (typeof window !== "undefined") {
      const pending = sessionStorage.getItem(PENDING_CLIENT_INVITE_KEY);
      if (pending?.trim()) {
        try {
          await apiFetchJson<AuthSessionResponse>(
            "/api/access/invites/client/accept",
            {
              method: "POST",
              headers: { ...headers, "Content-Type": "application/json" },
              body: JSON.stringify({ token: pending.trim() }),
            },
          );
        } catch {
          /* accept page may show error; continue bootstrap */
        } finally {
          sessionStorage.removeItem(PENDING_CLIENT_INVITE_KEY);
        }
      }
    }

    const boot = await apiFetchJson<AuthBootstrapResponse>(
      "/api/auth/bootstrap",
      { headers },
    );
    if (gen !== sessionSyncGeneration.current) return;

    if (boot.hasMembership) {
      const sess = await apiFetchJson<AuthSessionResponse>(
        "/api/auth/session",
        {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({
            uid: firebaseUser.uid,
            email: firebaseUser.email ?? null,
            displayName: firebaseUser.displayName ?? null,
            photoURL: firebaseUser.photoURL ?? null,
          }),
        },
      );
      if (gen !== sessionSyncGeneration.current) return;
      setTenantId(sess.tenantId ?? boot.tenantId);
      setRole(sess.role ?? boot.role);
      setNeedsClientInvite(false);
      setClientEntryMode(false);
      setAccountModalOpen(false);
      setAccountModalBusy(false);
      setAccountInfoMessage(null);
      setSessionReady(true);
      return;
    }

    // No membership found. If the user signed in with email/password (i.e. they used
    // admin-provisioned credentials) but have no membership yet, show a contextual message
    // rather than the generic type-selection form.
    const isEmailPasswordUser = firebaseUser.providerData.some(
      (p) => p.providerId === "password",
    );
    setTenantId(null);
    setRole(null);
    setNeedsClientInvite(false);
    setSessionReady(false);
    setAccountModalOpen(true);
    setAccountModalBusy(false);
    if (isEmailPasswordUser) {
      setClientEntryMode(true);
      setAccountInfoMessage(
        "Your credentials are valid, but your admin hasn't provisioned your access yet. " +
          "Contact your BastionFed administrator to complete setup.",
      );
    } else {
      setClientEntryMode(false);
      setAccountInfoMessage(null);
    }
  }

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        // Reset the client-sign-in gate now that a user is available
        clientSignInInProgress.current = false;
        setUser(firebaseUser);
        setIsDevMode(false);
        if (typeof window !== "undefined") {
          localStorage.removeItem(DEV_MODE_STORAGE_KEY);
          localStorage.removeItem(LEGACY_GUEST_STORAGE_KEY);
        }
        const gen = ++sessionSyncGeneration.current;
        try {
          await upsertUserProfile(firebaseUser);
          await runSessionSync(firebaseUser, gen);
        } catch (err) {
          console.error("Failed to sync user profile or backend session", err);
          if (gen === sessionSyncGeneration.current) {
            setSessionReady(false);
            setAccountModalOpen(true);
            setAccountInfoMessage(
              err instanceof ApiError
                ? err.message
                : "Could not reach the server. Check your connection and try again.",
            );
          }
        }
      } else {
        // Firebase signed out. If this is the transient null event that happens
        // while re-signing-in with client credentials, do nothing — the new sign-in
        // event will arrive momentarily.
        if (clientSignInInProgress.current) {
          setLoading(false);
          return;
        }
        setUser(null);
        sessionSyncGeneration.current += 1;
        setSessionReady(false);
        setNeedsClientInvite(false);
        setTenantId(null);
        setRole(null);
        setAccountModalOpen(false);
        setAccountInfoMessage(null);
        setClientEntryMode(false);
      }
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const signInWithEmailPassword = async (
    email: string,
    password: string,
  ): Promise<boolean> => {
    if (googlePopupInFlight.current) return false;
    googlePopupInFlight.current = true;
    try {
      if (typeof window !== "undefined") {
        localStorage.removeItem(DEV_MODE_STORAGE_KEY);
        localStorage.removeItem(LEGACY_GUEST_STORAGE_KEY);
      }
      setIsDevMode(false);
      await signInWithEmailAndPassword(auth, email.trim(), password);
      return true;
    } catch (e) {
      console.error("[auth] Email sign-in failed", e);
      throw e;
    } finally {
      googlePopupInFlight.current = false;
    }
  };

  const registerWithEmailPassword = async (
    email: string,
    password: string,
  ): Promise<boolean> => {
    if (googlePopupInFlight.current) return false;
    googlePopupInFlight.current = true;
    try {
      if (typeof window !== "undefined") {
        localStorage.removeItem(DEV_MODE_STORAGE_KEY);
        localStorage.removeItem(LEGACY_GUEST_STORAGE_KEY);
      }
      setIsDevMode(false);
      await createUserWithEmailAndPassword(auth, email.trim(), password);
      return true;
    } catch (e) {
      console.error("[auth] Email registration failed", e);
      throw e;
    } finally {
      googlePopupInFlight.current = false;
    }
  };

  const signInWithGoogle = async (): Promise<boolean> => {
    if (googlePopupInFlight.current) {
      console.warn(
        "[auth] Google sign-in already in progress; ignoring duplicate request.",
      );
      return false;
    }
    googlePopupInFlight.current = true;
    try {
      if (typeof window !== "undefined") {
        localStorage.removeItem(DEV_MODE_STORAGE_KEY);
        localStorage.removeItem(LEGACY_GUEST_STORAGE_KEY);
      }
      setIsDevMode(false);
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

  const continueInDevMode = async () => {
    if (auth.currentUser) {
      await firebaseSignOut(auth);
    }
    setUser(null);
    setIsDevMode(true);
    setSessionReady(true);
    setNeedsClientInvite(false);
    setTenantId(null);
    setRole(null);
    setAccountModalOpen(false);
    if (typeof window !== "undefined") {
      localStorage.setItem(DEV_MODE_STORAGE_KEY, "true");
      localStorage.removeItem(LEGACY_GUEST_STORAGE_KEY);
    }
  };

  const signOutUser = async () => {
    if (auth.currentUser) {
      await firebaseSignOut(auth);
    }
    setUser(null);
    setIsDevMode(false);
    setSessionReady(false);
    setNeedsClientInvite(false);
    setTenantId(null);
    setRole(null);
    setAccountModalOpen(false);
    if (typeof window !== "undefined") {
      localStorage.removeItem(DEV_MODE_STORAGE_KEY);
      localStorage.removeItem(LEGACY_GUEST_STORAGE_KEY);
    }
  };

  const submitAccountType = async (t: "SYSTEM_OWNER" | "CLIENT_USER") => {
    if (!user) return;

    // CLIENT_USER: don't call the backend — instead switch to credential-entry mode so
    // the user can sign in with their admin-provisioned email/password credentials.
    if (t === "CLIENT_USER") {
      setClientEntryMode(true);
      setAccountInfoMessage(null);
      return;
    }

    setAccountModalBusy(true);
    setAccountInfoMessage(null);
    const gen = sessionSyncGeneration.current;
    try {
      const token = await user.getIdToken();
      const res = await apiFetchJson<AuthSessionResponse>("/api/auth/session", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          uid: user.uid,
          email: user.email ?? null,
          displayName: user.displayName ?? null,
          photoURL: user.photoURL ?? null,
          accountType: t,
        }),
      });
      if (gen !== sessionSyncGeneration.current) return;
      if (res.needsClientInvite) {
        setNeedsClientInvite(true);
        setSessionReady(false);
        setTenantId(null);
        setRole(null);
        setAccountInfoMessage(
          "No invitation was found for this account. Ask your BastionFed owner or admin to send a client/site invite link, open it, then sign in with the invited email (Google or email/password).",
        );
        return;
      }
      setTenantId(res.tenantId);
      setRole(res.role);
      setNeedsClientInvite(false);
      setAccountModalOpen(false);

      // New admin on a fresh tenant: show the client-setup wizard before dashboard
      if (res.isNewTenant && t === "SYSTEM_OWNER") {
        setAdminWizardResults(null);
        setAdminWizardLimits(null);
        setAdminWizardOpen(true);
        // sessionReady intentionally NOT set here; wizard will set it on completion
        return;
      }

      setSessionReady(true);
    } catch (e) {
      console.error(e);
      setAccountInfoMessage("Session request failed. Try again.");
    } finally {
      setAccountModalBusy(false);
    }
  };

  const submitAdminWizard = async (clients: ClientDef[]) => {
    if (!user) return;
    setAdminWizardBusy(true);
    try {
      const token = await user.getIdToken();
      type OnboardingResponse = {
        results: ClientProvisionResult[];
        createdCount: number;
        errorCount: number;
      };
      const res = await apiFetchJson<OnboardingResponse>(
        "/api/onboarding/clients",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            clients: clients.map((c) => ({
              nodeName: c.nodeName,
              clientType: c.clientType,
              email: c.email || null,
            })),
          }),
        },
      );
      setAdminWizardResults(res.results);
    } catch (e) {
      console.error("[auth] Admin wizard submit failed", e);
      if (e instanceof ApiError && e.code === "CLIENT_LIMIT_REACHED") {
        setAdminWizardResults([
          {
            nodeName: "Limit",
            clientType: "DEVICE",
            status: "error",
            error: e.message,
          },
        ]);
      } else {
        setAdminWizardResults([
          {
            nodeName: "Setup",
            clientType: "PERSON",
            status: "error",
            error:
              "Failed to reach server. You can add clients later from Settings → Provisioning.",
          },
        ]);
      }
    } finally {
      setAdminWizardBusy(false);
    }
  };

  const completeAdminWizard = () => {
    setAdminWizardOpen(false);
    setAdminWizardResults(null);
    setAdminWizardLimits(null);
    setSessionReady(true);
  };

  /**
   * Called from the credential-entry view in AccountTypeModal.
   * Signs in with admin-provisioned email/password credentials. Firebase will
   * automatically sign out the current (Google) user first, producing a transient
   * null auth event which is suppressed by `clientSignInInProgress`.
   */
  const signInWithClientCredentials = async (
    email: string,
    password: string,
  ): Promise<void> => {
    setAccountModalBusy(true);
    setAccountInfoMessage(null);
    clientSignInInProgress.current = true;
    try {
      await signInWithEmailAndPassword(auth, email.trim(), password);
      // onAuthStateChanged will fire: first with null (old user signed out),
      // then with the new email/password user. The null event is suppressed above.
    } catch (e) {
      clientSignInInProgress.current = false;
      setAccountModalBusy(false);
      if (e instanceof FirebaseError) {
        const code = e.code;
        if (
          code === "auth/invalid-credential" ||
          code === "auth/wrong-password" ||
          code === "auth/user-not-found" ||
          code === "auth/invalid-email"
        ) {
          throw new Error(
            "Invalid email or password. Check the credentials provided by your admin.",
          );
        }
        if (code === "auth/too-many-requests") {
          throw new Error("Too many sign-in attempts. Try again later.");
        }
      }
      throw new Error("Sign-in failed. Check your credentials and try again.");
    }
    // busy is cleared once onAuthStateChanged fires and runSessionSync completes
  };

  const backFromClientEntry = () => {
    setClientEntryMode(false);
    setAccountInfoMessage(null);
  };

  const value: AuthContextValue = {
    user,
    loading,
    isDevMode,
    sessionReady,
    accountModalOpen,
    adminWizardOpen,
    needsClientInvite,
    tenantId,
    role,
    signInWithGoogle,
    signInWithEmailPassword,
    registerWithEmailPassword,
    signOutUser,
    continueInDevMode,
    submitAccountType,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
      <AccountTypeModal
        open={!!user && accountModalOpen}
        busy={accountModalBusy}
        infoMessage={accountInfoMessage}
        onChoose={(t) => void submitAccountType(t)}
        clientEntryMode={clientEntryMode}
        onClientSignIn={signInWithClientCredentials}
        onClientBack={backFromClientEntry}
      />
      <AdminSetupWizard
        open={!!user && adminWizardOpen}
        busy={adminWizardBusy}
        results={adminWizardResults}
        onSubmit={(clients) => submitAdminWizard(clients)}
        onSkip={completeAdminWizard}
        remainingSlots={adminWizardLimits?.remaining ?? null}
        maxClientsPerAdmin={adminWizardLimits?.maxClientsPerAdmin ?? null}
      />
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export { PENDING_CLIENT_INVITE_KEY };
