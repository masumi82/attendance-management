import { Navigate, Outlet, useLocation } from "react-router-dom";

import { type Role, useAuthStore } from "@/lib/auth-store";

export default function ProtectedRoute({
  roles,
}: {
  roles?: Role[];
}) {
  const { user, accessToken, isBootstrapping } = useAuthStore();
  const loc = useLocation();

  if (isBootstrapping) {
    return <BootstrapSplash />;
  }

  if (!user || !accessToken) {
    return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  }

  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}

function BootstrapSplash() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-page-bg">
      <div className="flex items-center gap-3 text-[13px] text-text-secondary">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-100 border-t-brand-500" />
        読み込み中…
      </div>
    </div>
  );
}
