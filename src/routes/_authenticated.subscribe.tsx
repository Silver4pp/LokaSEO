import { createFileRoute, notFound } from "@tanstack/react-router";

// LokaSEO has no checkout, subscription, credits, or upgrade pages.
export const Route = createFileRoute("/_authenticated/subscribe")({
  beforeLoad: () => {
    throw notFound();
  },
});
