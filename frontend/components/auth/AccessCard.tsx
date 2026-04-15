"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { FirebaseError } from "firebase/app";
import { useAuth } from "@/contexts/auth-context";
import {
  Building2,
  ChevronDown,
  FlaskConical,
  Loader2,
  Lock,
  Mail,
} from "lucide-react";

function humanizeFirebaseError(e: FirebaseError): string {
  const code = e.code;
  if (
    code === "auth/invalid-credential" ||
    code === "auth/wrong-password" ||
    code === "auth/user-not-found"
  ) {
    return "Email or password doesn’t match. Confirm with your admin that your account is provisioned and use the credentials they gave you.";
  }
  if (code === "auth/email-already-in-use") {
    return "This email is already in use — try Sign in.";
  }
  if (code === "auth/weak-password") {
    return "Password doesn’t meet requirements. Ask your admin to reset or re-issue credentials.";
  }
  if (code === "auth/invalid-email") {
    return "Enter a valid email address.";
  }
  if (code === "auth/too-many-requests") {
    return "Too many attempts. Wait a moment and try again.";
  }
  return (
    e.message
      .replace(/^Firebase:\s*/i, "")
      .replace(/\s*\(auth\/[^)]+\)\s*\.?$/i, "") ||
    "Something went wrong. Try again."
  );
}

export function AccessCard() {
  const router = useRouter();
  const { signInWithGoogle, signInWithEmailPassword, continueInDevMode } =
    useAuth();
  const [googleBusy, setGoogleBusy] = useState(false);
  const [emailBusy, setEmailBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [demoModeEnabled, setDemoModeEnabled] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/public-config", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { demo_mode?: boolean } | null) => {
        if (!cancelled && data?.demo_mode) setDemoModeEnabled(true);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const handleDevModeAccess = async () => {
    await continueInDevMode();
    router.push("/dashboard");
  };

  const handleGoogleSignIn = async () => {
    if (googleBusy) return;
    setGoogleBusy(true);
    try {
      const ok = await signInWithGoogle();
      if (ok) router.push("/dashboard");
    } finally {
      setGoogleBusy(false);
    }
  };

  const handleEmailSignIn = async () => {
    setEmailError(null);
    if (emailBusy || !email.trim() || !password) {
      setEmailError(
        "Enter the email and password your administrator provided.",
      );
      return;
    }
    setEmailBusy(true);
    try {
      const ok = await signInWithEmailPassword(email, password);
      if (ok) router.push("/dashboard");
    } catch (e) {
      setEmailError(
        e instanceof FirebaseError
          ? humanizeFirebaseError(e)
          : "Sign-in failed.",
      );
    } finally {
      setEmailBusy(false);
    }
  };

  return (
    <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-bg-surface shadow-[0_24px_80px_-24px_rgba(0,0,0,0.9)] ring-1 ring-white/[0.04]">
      <div className="flex flex-col gap-5 p-6 sm:p-8 sm:pb-6 lg:gap-4 lg:px-8 lg:py-5">
        <div className="space-y-2.5 text-center sm:text-left">
          <h2 className="font-display text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Enter the SOC
          </h2>
          <p className="max-w-2xl text-pretty text-sm leading-snug text-text-secondary">
            {demoModeEnabled ? (
              <>
                Sign in for your real tenant, or open the read-only demo when
                the server runs with{" "}
                <code className="rounded bg-bg-overlay px-1.5 py-0.5 font-mono text-[11px] text-white/90">
                  DEMO_MODE=1
                </code>
                .
              </>
            ) : (
              <>
                Sign in for your real tenant with Google, or expand the invite
                section for client credentials from your administrator.
              </>
            )}
          </p>
          <div className="flex flex-wrap justify-center gap-2 sm:justify-start">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/20 bg-emerald-500/[0.07] px-2.5 py-1 text-[11px] font-medium text-emerald-200/90">
              <Building2 className="h-3.5 w-3.5 opacity-80" aria-hidden />
              Production
            </span>
            {demoModeEnabled ? (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-amber-500/20 bg-amber-500/[0.07] px-2.5 py-1 text-[11px] font-medium text-amber-100/90">
                <FlaskConical className="h-3.5 w-3.5 opacity-80" aria-hidden />
                Demo tenant
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex flex-col gap-4">
          {/* Workspace + demo grouped */}
          <div className="space-y-3 rounded-xl border border-white/[0.08] bg-gradient-to-b from-white/[0.04] to-transparent p-3.5 sm:p-4">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
              {demoModeEnabled ? "Workspace & demo" : "Workspace"}
            </p>
            <button
              onClick={() => void handleGoogleSignIn()}
              type="button"
              disabled={googleBusy}
              className="group flex w-full items-center justify-center gap-2.5 rounded-xl border border-white/15 bg-white/[0.06] px-4 py-2.5 text-sm font-medium text-white transition-all duration-200 hover:border-white/25 hover:bg-white/[0.1] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/40 disabled:pointer-events-none disabled:opacity-45"
            >
              {googleBusy ? (
                <Loader2
                  className="h-5 w-5 shrink-0 animate-spin text-white/80"
                  aria-hidden
                />
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  className="h-5 w-5 shrink-0"
                  aria-hidden
                >
                  <path
                    d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"
                    fill="currentColor"
                  />
                </svg>
              )}
              {googleBusy ? "Opening Google…" : "Continue with Google"}
            </button>
            <p className="text-center text-[11px] leading-snug text-text-muted sm:text-left">
              Owners, admins, and analysts — Google workspace account.
            </p>

            {demoModeEnabled ? (
              <>
                <button
                  onClick={() => void handleDevModeAccess()}
                  type="button"
                  className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-white/20 bg-transparent px-4 py-2.5 text-sm font-medium text-text-secondary transition-all duration-200 hover:border-white/35 hover:bg-white/[0.03] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/30"
                >
                  <FlaskConical className="h-4 w-4" aria-hidden />
                  Continue in dev mode
                </button>
                <p className="text-center text-[11px] leading-snug text-text-muted sm:text-left">
                  Read-only demo tenant — not for production data.
                </p>
              </>
            ) : null}
          </div>

          {/* Collapsible client invite sign-in */}
          <div className="overflow-hidden rounded-xl border border-white/[0.08]">
            <button
              type="button"
              id="access-invite-toggle"
              aria-expanded={inviteOpen}
              aria-controls="access-invite-panel"
              onClick={() => setInviteOpen((o) => !o)}
              className="flex w-full items-center justify-between gap-3 px-3.5 py-3 text-left transition-colors hover:bg-white/[0.03] sm:px-4"
            >
              <span className="flex min-w-0 flex-1 items-center gap-2.5">
                <Mail
                  className="h-4 w-4 shrink-0 text-text-muted"
                  aria-hidden
                />
                <span>
                  <span className="block font-mono text-[10px] uppercase tracking-[0.15em] text-text-muted">
                    Invite link
                  </span>
                  <span className="block text-sm font-medium text-white">
                    Client / site sign-in
                  </span>
                </span>
              </span>
              <ChevronDown
                className={`h-4 w-4 shrink-0 text-text-muted transition-transform duration-200 ${inviteOpen ? "rotate-180" : ""}`}
                aria-hidden
              />
            </button>

            {inviteOpen ? (
              <div
                id="access-invite-panel"
                role="region"
                aria-labelledby="access-invite-toggle"
                className="space-y-3 border-t border-white/[0.06] px-3.5 pb-3.5 pt-3 sm:px-4 sm:pb-4"
              >
                <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 sm:gap-3">
                  <label className="block min-w-0">
                    <span className="sr-only">Email</span>
                    <div className="relative">
                      <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
                      <input
                        type="email"
                        autoComplete="email"
                        placeholder="Email from your invite"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full rounded-lg border border-border-default bg-bg-base py-2 pl-10 pr-3 text-sm text-white placeholder:text-text-muted/80 transition-colors focus:border-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                      />
                    </div>
                  </label>
                  <label className="block min-w-0">
                    <span className="sr-only">Password</span>
                    <div className="relative">
                      <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
                      <input
                        type="password"
                        autoComplete="current-password"
                        placeholder="Password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full rounded-lg border border-border-default bg-bg-base py-2 pl-10 pr-3 text-sm text-white placeholder:text-text-muted/80 transition-colors focus:border-white/30 focus:outline-none focus:ring-1 focus:ring-white/20"
                      />
                    </div>
                  </label>
                </div>
                {emailError ? (
                  <p
                    role="alert"
                    className="rounded-lg border border-red-500/25 bg-red-500/[0.08] px-3 py-2 text-xs leading-snug text-red-200/95"
                  >
                    {emailError}
                  </p>
                ) : null}
                <button
                  type="button"
                  disabled={emailBusy}
                  onClick={() => void handleEmailSignIn()}
                  className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/15 bg-bg-base px-3 py-2.5 text-sm font-medium text-white transition-all duration-200 hover:border-white/25 hover:bg-bg-overlay focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/35 disabled:opacity-45"
                >
                  {emailBusy ? (
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  ) : null}
                  Sign in
                </button>
                <p className="text-[10px] leading-snug text-text-muted sm:text-[11px]">
                  Your administrator creates the Firebase user and shares
                  credentials with you. Use the same email as on your invite.
                  Email/password sign-in must be enabled in Firebase for your
                  project.
                </p>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <p className="border-t border-white/[0.06] px-5 py-2.5 text-center text-[10px] leading-snug text-text-muted sm:px-8 sm:text-[11px]">
        By continuing you agree to the Terms of Service and Privacy Policy.
      </p>
    </div>
  );
}
