export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(date);
}

export function formatRelativeTime(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  const deltaSeconds = Math.round((date.getTime() - Date.now()) / 1000);
  const abs = Math.abs(deltaSeconds);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  if (abs < 60) {
    return rtf.format(deltaSeconds, "second");
  }
  if (abs < 3600) {
    return rtf.format(Math.round(deltaSeconds / 60), "minute");
  }
  if (abs < 86400) {
    return rtf.format(Math.round(deltaSeconds / 3600), "hour");
  }
  return rtf.format(Math.round(deltaSeconds / 86400), "day");
}
