import {
  Outlet,
  createFileRoute,
  useLocation,
  useParams,
} from "@tanstack/react-router";
import { useHostedAuthRouteGuard } from "@/client/features/auth/useHostedAuthRouteGuard";
import { SkeletonPage } from "@/client/components/SkeletonPresets";
import { AuthenticatedAppLayout } from "@/client/layout/AppShell";
export const Route = createFileRoute("/_app")({ component: AppRouteLayout });
function AppRouteLayout() {
  const authGate = useHostedAuthRouteGuard();
  const { projectId } = useParams({ strict: false });
  const pathname = useLocation({ select: (state) => state.pathname });
  const ready = authGate.canRenderAuthenticatedContent;
  if (pathname === "/") return ready ? <Outlet /> : <SkeletonPage />;
  return (
    <AuthenticatedAppLayout projectId={projectId} ready={ready}>
      {ready ? <Outlet /> : <SkeletonPage />}
    </AuthenticatedAppLayout>
  );
}
