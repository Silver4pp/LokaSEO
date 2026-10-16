import { createFileRoute, notFound } from "@tanstack/react-router";

// LokaSEO has no checkout, subscription, credits, or upgrade pages.
export const Route = createFileRoute("/_app/billing")({
  beforeLoad: () => {
    throw notFound();
  },
});
