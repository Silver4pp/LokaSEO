import { createFileRoute } from "@tanstack/react-router";
import { LokaWorkspace } from "@/client/features/lokaseo/LokaWorkspace";
export const Route = createFileRoute("/_app/")({ component: LokaWorkspace });
