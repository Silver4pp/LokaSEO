import { createFileRoute, notFound } from "@tanstack/react-router";

// LokaSEO has no checkout, subscription, credits, or upgrade pages.
export const Route = createFileRoute("/_app/billing_/fix-payment")({
  beforeLoad: () => {
    throw notFound();
  },
});
