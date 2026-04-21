import { StrictMode, Suspense, lazy, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import App, { ClockPage } from "./App";
import LoginPage from "@/features/auth/LoginPage";
import { useAuth } from "@/features/auth/useAuth";
import ProtectedRoute from "@/routes/ProtectedRoute";
import "./index.css";

// Route-level code splitting: members that never visit admin pages skip
// the chunks for them entirely.
const RequestsPage = lazy(() => import("@/features/requests/RequestsPage"));
const MyShiftsPage = lazy(() => import("@/features/shifts/MyShiftsPage"));
const ApprovalsPage = lazy(() => import("@/features/approvals/ApprovalsPage"));
const AdminShiftsPage = lazy(() => import("@/features/admin/ShiftsPage"));
const ClosingPage = lazy(() => import("@/features/admin/ClosingPage"));
const DepartmentsPage = lazy(() => import("@/features/admin/DepartmentsPage"));
const EmployeesPage = lazy(() => import("@/features/admin/EmployeesPage"));
const HolidaysPage = lazy(() => import("@/features/admin/HolidaysPage"));
const LeavesPage = lazy(() => import("@/features/admin/LeavesPage"));
const OvertimePage = lazy(() => import("@/features/admin/OvertimePage"));

function PageFallback() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center text-[13px] text-text-tertiary">
      読み込み中…
    </div>
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function Root() {
  const { bootstrap } = useAuth();
  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  return (
    <BrowserRouter>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<App />}>
              <Route index element={<ClockPage />} />
              <Route path="requests" element={<RequestsPage />} />
              <Route path="my/shifts" element={<MyShiftsPage />} />
              <Route element={<ProtectedRoute roles={["admin", "approver"]} />}>
                <Route path="approvals" element={<ApprovalsPage />} />
              </Route>
              <Route element={<ProtectedRoute roles={["admin"]} />}>
                <Route path="admin/employees" element={<EmployeesPage />} />
                <Route path="admin/shifts" element={<AdminShiftsPage />} />
                <Route path="admin/overtime" element={<OvertimePage />} />
                <Route path="admin/leaves" element={<LeavesPage />} />
                <Route path="admin/closing" element={<ClosingPage />} />
                <Route path="admin/departments" element={<DepartmentsPage />} />
                <Route path="admin/holidays" element={<HolidaysPage />} />
              </Route>
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Root />
    </QueryClientProvider>
  </StrictMode>,
);
