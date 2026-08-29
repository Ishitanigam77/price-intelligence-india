"use client";

import { useAuth, useUser } from "@clerk/nextjs";
import { FormEvent, useCallback, useState } from "react";

import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { getProfile, updateProfile } from "@/lib/api/profile";
import { useAsync } from "@/lib/hooks/useAsync";
import type { UserProfileRead } from "@/lib/types/api";

export function ProfileView() {
  const { getToken, isSignedIn, isLoaded } = useAuth();
  const { user } = useUser();
  const [status, setStatus] = useState<string | null>(null);

  const load = useCallback(async (): Promise<UserProfileRead> => {
    const accessToken = await getToken();
    return getProfile({ accessToken });
  }, [getToken]);

  const state = useAsync(load, [load], { enabled: isLoaded && Boolean(isSignedIn) });

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (state.status !== "success") {
      return;
    }
    const form = new FormData(event.currentTarget);
    const displayName = String(form.get("display_name") ?? "").trim();
    const emailAlerts = form.get("email_alerts_enabled") === "on";
    const accessToken = await getToken();
    await updateProfile(
      {
        display_name: displayName || state.data.display_name,
        preferences: { email_alerts_enabled: emailAlerts },
      },
      { accessToken },
    );
    setStatus("Saved.");
    state.reload();
  }

  if (!isLoaded || state.status === "idle" || state.status === "loading") {
    return <LoadingSkeleton label="Loading your profile" rows={4} />;
  }
  if (state.status === "error") {
    return (
      <ErrorState title="Profile could not be loaded" error={state.error} onRetry={state.reload} />
    );
  }

  const profile = state.data;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-display text-4xl text-ink">Your profile</h1>
        <p className="text-ink-muted">
          Sign-in is handled by Clerk. This application does not store passwords. Email comes from
          your Clerk identity when the token includes it.
        </p>
      </header>
      <dl className="grid gap-3 rounded-2xl border border-paper-muted bg-paper-card p-5 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-wide text-ink-muted">Clerk user id</dt>
          <dd className="mt-1 font-medium text-ink">{profile.clerk_user_id}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-ink-muted">Email</dt>
          <dd className="mt-1 font-medium text-ink">
            {profile.email ??
              user?.primaryEmailAddress?.emailAddress ??
              "Not provided by Clerk token"}
          </dd>
        </div>
      </dl>
      <form onSubmit={(event) => void onSubmit(event)} className="max-w-lg space-y-4">
        <label className="block space-y-1 text-sm">
          <span className="font-medium text-ink">Display name</span>
          <input
            name="display_name"
            defaultValue={profile.display_name ?? user?.fullName ?? ""}
            className="w-full rounded-xl border border-paper-muted bg-paper px-3 py-2 text-ink"
          />
        </label>
        <label className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            name="email_alerts_enabled"
            defaultChecked={profile.preferences.email_alerts_enabled}
          />
          Email alerts enabled (stored preference; delivery is not implemented in this phase)
        </label>
        <button
          type="submit"
          className="inline-flex min-h-11 items-center rounded-xl bg-brand px-4 text-sm font-semibold text-white hover:bg-brand-dark"
        >
          Save profile
        </button>
        {status ? <p className="text-sm text-brand-dark">{status}</p> : null}
      </form>
    </div>
  );
}
