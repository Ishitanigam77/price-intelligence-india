import { apiGet, apiPatch, type ApiAuth } from "@/lib/api/client";
import type { UserProfileRead, UserProfileUpdate } from "@/lib/types/api";

export function getProfile(auth?: ApiAuth): Promise<UserProfileRead> {
  return apiGet<UserProfileRead>("/me", undefined, auth);
}

export function updateProfile(
  payload: UserProfileUpdate,
  auth?: ApiAuth,
): Promise<UserProfileRead> {
  return apiPatch<UserProfileRead>("/me", payload, auth);
}
