const SENSITIVE_KEY = /(secret|token|password|authorization|cookie|connection.?string|api[_-]?key|clerk)/i;

const SENSITIVE_VALUE = /(bearer\s+\S+|sk_[a-z0-9]+|clerk[_-]?secret)/i;

export function isSensitiveKey(key: string): boolean {
  return SENSITIVE_KEY.test(key);
}

export function sanitizeTelemetryPayload(
  input: Record<string, unknown>,
): Record<string, string | number | boolean | null> {
  const cleaned: Record<string, string | number | boolean | null> = {};
  for (const [key, value] of Object.entries(input)) {
    if (isSensitiveKey(key)) {
      continue;
    }
    if (typeof value === "string") {
      if (SENSITIVE_VALUE.test(value)) {
        continue;
      }
      cleaned[key] = value.slice(0, 200);
      continue;
    }
    if (typeof value === "number" || typeof value === "boolean" || value === null) {
      cleaned[key] = value;
    }
  }
  return cleaned;
}

export function safePath(pathname: string): string {
  const path = pathname.split("?")[0] ?? "/";
  return path.slice(0, 200);
}
