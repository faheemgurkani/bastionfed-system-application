"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthGate } from "@/components/auth/AuthGate";
import { useAuth } from "@/contexts/auth-context";
import { useViewMode } from "@/contexts/view-mode-context";
import { apiFetchJson, ApiError } from "@/lib/api";
import type { FLClient, FLClientType } from "@/lib/types";
import { AdminSetupWizard } from "@/components/onboarding/AdminSetupWizard";
import type {
  ClientDef,
  ClientProvisionResult,
} from "@/components/onboarding/AdminSetupWizard";

type FLClientsResponse = { clients: FLClient[] };

type InviteRow = {
  inviteId: string;
  email: string | null;
  flClientIds: string[];
  expiresAt: string;
  createdAt: string;
  consumedAt: string | null;
};

type InvitesListResponse = { invites: InviteRow[] };

type OnboardingLimits = {
  maxClientsPerAdmin: number;
  alreadyProvisioned: number;
  remaining: number;
};

type OnboardingPostResponse = {
  results: ClientProvisionResult[];
  createdCount: number;
  errorCount: number;
};

export default function SettingsAccessPage() {
  const router = useRouter();
  const { user, role, sessionReady } = useAuth();
  const { canUseAdminClientView, mode: adminViewMode } = useViewMode();
  const [clients, setClients] = useState<FLClient[]>([]);
  const [patchBusy, setPatchBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [invites, setInvites] = useState<InviteRow[]>([]);
  const [addWizardOpen, setAddWizardOpen] = useState(false);
  const [addWizardBusy, setAddWizardBusy] = useState(false);
  const [addWizardResults, setAddWizardResults] = useState<
    ClientProvisionResult[] | null
  >(null);
  const [onboardingLimits, setOnboardingLimits] =
    useState<OnboardingLimits | null>(null);

  const loadClients = useCallback(async () => {
    if (!user || role === "client_user") return;
    const token = await user.getIdToken();
    const data = await apiFetchJson<FLClientsResponse>("/api/fl/clients", {
      headers: { Authorization: `Bearer ${token}` },
    });
    setClients(data.clients);
  }, [user, role]);

  const loadInvites = useCallback(async () => {
    if (!user || role === "client_user") return;
    const token = await user.getIdToken();
    const data = await apiFetchJson<InvitesListResponse>(
      "/api/access/invites/client",
      {
        headers: { Authorization: `Bearer ${token}` },
      },
    );
    setInvites(data.invites);
  }, [user, role]);

  const loadOnboardingLimits = useCallback(async () => {
    if (!user || role === "client_user") return;
    try {
      const token = await user.getIdToken();
      const data = await apiFetchJson<OnboardingLimits>(
        "/api/onboarding/limits",
        {
          headers: { Authorization: `Bearer ${token}` },
        },
      );
      setOnboardingLimits(data);
    } catch {
      setOnboardingLimits(null);
    }
  }, [user, role]);

  useEffect(() => {
    if (!user || role === "client_user") return;
    let cancelled = false;
    (async () => {
      try {
        await loadClients();
        await loadInvites();
        await loadOnboardingLimits();
      } catch {
        if (!cancelled) {
          setClients([]);
          setInvites([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, role, loadClients, loadInvites, loadOnboardingLimits]);

  const canEditProvisioning =
    canUseAdminClientView && adminViewMode === "tenant";

  useEffect(() => {
    if (canUseAdminClientView && adminViewMode === "client") {
      router.replace("/dashboard");
    }
  }, [canUseAdminClientView, adminViewMode, router]);

  useEffect(() => {
    if (!sessionReady || !user || !role) return;
    if (!canUseAdminClientView) {
      router.replace("/dashboard");
    }
  }, [sessionReady, user, role, canUseAdminClientView, router]);

  async function patchClientType(clientId: string, clientType: FLClientType) {
    if (!user || !canEditProvisioning) return;
    setPatchBusy(clientId);
    setError(null);
    try {
      const token = await user.getIdToken();
      await apiFetchJson(`/api/fl/clients/${encodeURIComponent(clientId)}`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ clientType }),
      });
      await loadClients();
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Failed to update client type",
      );
    } finally {
      setPatchBusy(null);
    }
  }

  async function submitAddClients(clients: ClientDef[]) {
    if (!user || !canEditProvisioning) return;
    setAddWizardBusy(true);
    setAddWizardResults(null);
    try {
      const token = await user.getIdToken();
      const res = await apiFetchJson<OnboardingPostResponse>(
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
      setAddWizardResults(res.results);
      await loadClients();
      await loadOnboardingLimits();
      await loadInvites();
    } catch (e) {
      if (e instanceof ApiError && e.code === "CLIENT_LIMIT_REACHED") {
        setAddWizardResults([
          {
            nodeName: "Limit",
            clientType: "DEVICE",
            status: "error",
            error: e.message,
          },
        ]);
      } else {
        setAddWizardResults([
          {
            nodeName: "Setup",
            clientType: "DEVICE",
            status: "error",
            error: e instanceof ApiError ? e.message : "Provisioning failed.",
          },
        ]);
      }
    } finally {
      setAddWizardBusy(false);
    }
  }

  function closeAddWizard() {
    setAddWizardOpen(false);
    setAddWizardResults(null);
  }

  return (
    <AuthGate>
      <div className="mx-auto max-w-3xl px-6 py-10 space-y-10">
        <div>
          <h1 className="text-2xl font-semibold text-white">Provisioning</h1>
          <p className="text-sm text-text-muted mt-2">
            Classify FL clients as device nodes (admin scope only) or
            person-operated (email invites + login). Production invites should
            use real tenant data; dev mode on the home page is the isolated demo
            tenant.
          </p>
        </div>
        {!canUseAdminClientView ? (
          <p className="text-sm text-amber-400">
            Provisioning is only available to signed-in owners and admins.
          </p>
        ) : adminViewMode === "client" ? (
          <p className="py-12 text-center text-sm text-text-muted">
            Single-client preview is active. Tenant-wide provisioning is
            available after you switch to &quot;All clients&quot; in the header.
            Redirecting…
          </p>
        ) : (
          <>
            <div className="space-y-6 border border-border-default rounded-xl p-6 bg-bg-surface">
              <div className="space-y-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <h2 className="text-sm font-semibold text-white">
                    Provision additional clients
                  </h2>
                  <button
                    type="button"
                    disabled={
                      onboardingLimits !== null && onboardingLimits.remaining < 1
                    }
                    onClick={() => {
                      setAddWizardResults(null);
                      setAddWizardOpen(true);
                    }}
                    className="rounded-lg bg-white text-black px-4 py-2 text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    Add clients
                  </button>
                </div>
                {onboardingLimits ? (
                  <p className="text-xs text-text-muted font-mono">
                    Per-admin limit: {onboardingLimits.alreadyProvisioned} /{" "}
                    {onboardingLimits.maxClientsPerAdmin} provisioned ·{" "}
                    {onboardingLimits.remaining} slot(s) remaining.
                  </p>
                ) : (
                  <p className="text-xs text-text-muted">Loading limits…</p>
                )}
                <p className="text-xs text-text-secondary">
                  Same flow as initial setup: choose Device vs Person, node name,
                  and email for person clients. Invites and access for
                  person-operated clients are created through this provisioning
                  flow—use the status below to track outstanding or accepted
                  invites tied to your tenant.
                </p>
              </div>

              <div className="border-t border-border-default pt-6 space-y-3">
                <h3 className="text-xs font-semibold text-white uppercase tracking-wider">
                  Person-operator invite status
                </h3>
                <p className="text-xs text-text-muted">
                  Reflects invites issued when provisioning person-operated
                  clients (pending acceptance or already used).
                </p>
                {invites.length === 0 ? (
                  <p className="text-sm text-text-muted">No invites yet.</p>
                ) : (
                  <ul className="space-y-3 text-sm">
                    {invites.map((inv) => (
                      <li
                        key={inv.inviteId}
                        className="rounded-lg border border-border-default/80 bg-bg-base/50 px-3 py-2 space-y-1"
                      >
                        <div className="flex flex-wrap gap-x-3 gap-y-1 text-white">
                          <span className="font-mono text-xs">
                            {inv.inviteId}
                          </span>
                          {inv.consumedAt ? (
                            <span className="text-xs text-green-400">
                              Used {inv.consumedAt}
                            </span>
                          ) : (
                            <span className="text-xs text-amber-400">
                              Pending · expires {inv.expiresAt}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-text-muted">
                          Email: {inv.email ?? "—"} · Clients:{" "}
                          {inv.flClientIds.join(", ")}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            <div className="space-y-4 border border-border-default rounded-xl p-6 bg-bg-surface">
              <h2 className="text-sm font-semibold text-white">
                FL client classification
              </h2>
              <p className="text-xs text-text-muted">
                Device node: no human login; admins can switch into this client
                view. Person-operated: invited users sign in (Google or
                email/password) and see only scoped data.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-border-default text-text-muted text-xs uppercase tracking-wider">
                      <th className="py-2 pr-4">Client</th>
                      <th className="py-2 pr-4">Department</th>
                      <th className="py-2">Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clients.map((c) => (
                      <tr
                        key={c.id}
                        className="border-b border-border-default/60"
                      >
                        <td className="py-2 pr-4 font-mono text-white">
                          {c.id}
                        </td>
                        <td className="py-2 pr-4 text-text-muted">
                          {c.department}
                        </td>
                        <td className="py-2">
                          <select
                            aria-label={`Client type for ${c.id}`}
                            title={`Client type for ${c.id}`}
                            value={c.clientType ?? "DEVICE"}
                            disabled={patchBusy === c.id}
                            onChange={(e) =>
                              void patchClientType(
                                c.id,
                                e.target.value as FLClientType,
                              )
                            }
                            className="rounded-md border border-border-default bg-bg-base px-2 py-1 text-xs text-white font-mono"
                          >
                            <option value="DEVICE">Device node</option>
                            <option value="PERSON">Person-operated</option>
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {error ? (
              <p className="text-sm text-red-400" role="alert">
                {error}
              </p>
            ) : null}
          </>
        )}
        <AdminSetupWizard
          open={addWizardOpen}
          busy={addWizardBusy}
          results={addWizardResults}
          onSubmit={(c) => void submitAddClients(c)}
          onSkip={closeAddWizard}
          remainingSlots={onboardingLimits?.remaining ?? null}
          maxClientsPerAdmin={onboardingLimits?.maxClientsPerAdmin ?? null}
          title="Add clients"
          description="Define additional device or person clients. Person clients receive login credentials by email."
          hideSkip
        />
      </div>
    </AuthGate>
  );
}
