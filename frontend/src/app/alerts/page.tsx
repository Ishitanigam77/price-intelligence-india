import type { Metadata } from "next";

import { AlertsView } from "@/components/alerts/AlertsView";

export const metadata: Metadata = {
  title: "Alerts",
};

export const dynamic = "force-dynamic";

export default function AlertsPage() {
  return <AlertsView />;
}
