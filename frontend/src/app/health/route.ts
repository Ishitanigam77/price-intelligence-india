import { NextResponse } from "next/server";

import { getFrontendEnvironment, getFrontendServiceName } from "@/lib/observability/config";

export function GET() {
  return NextResponse.json({
    status: "ok",
    service: getFrontendServiceName(),
    environment: getFrontendEnvironment(),
  });
}
