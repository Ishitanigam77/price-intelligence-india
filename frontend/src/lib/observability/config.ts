export function getFrontendEnvironment(): string {
  return (
    process.env.ENVIRONMENT?.trim() ||
    process.env.NEXT_PUBLIC_ENVIRONMENT?.trim() ||
    "development"
  );
}

export function getFrontendServiceName(): string {
  return "frontend";
}

export function applicationInsightsConfigured(): boolean {
  const value = process.env.APPLICATIONINSIGHTS_CONNECTION_STRING?.trim() ?? "";
  if (!value) {
    return false;
  }
  const lowered = value.toLowerCase();
  return lowered.includes("instrumentationkey=") && lowered !== "changeme";
}
