import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import ChangePasswordDialog from "@/features/auth/ChangePasswordDialog";
import { useAuth } from "@/features/auth/useAuth";
import HelpDialog from "@/features/help/HelpDialog";
import NotificationBell from "@/features/notifications/NotificationBell";
import {
  apiMonthly,
  apiMyLeaveBalance,
  apiPunch,
  apiToday,
  type DailyAttendanceOut,
  type LeaveBalanceSummary,
  type MonthlyResponse,
  type PunchState,
  type PunchType,
  type TodayResponse,
} from "@/lib/api";
import { type AuthUser, type Role, useAuthStore } from "@/lib/auth-store";
import { cn } from "@/lib/utils";

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

const pad = (n: number, len = 2) => n.toString().padStart(len, "0");
const JP_WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"];

function formatMinutes(total: number): string {
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${pad(h)}:${pad(m)}`;
}

function formatHM(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const PUNCH_ERROR_MESSAGES: Record<string, string> = {
  already_clocked_in: "すでに出勤済みです。",
  already_clocked_out: "すでに退勤済みです。",
  already_on_break: "すでに休憩中です。",
  not_clocked_in: "先に出勤を打刻してください。",
  not_on_break: "休憩を開始していません。",
  still_on_break: "休憩終了を先に打刻してください。",
};

/* ==========================================================================
   Icons — minimal stroke icons, freee-ish
   ========================================================================== */
type IconProps = { className?: string };
const IconClock = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </svg>
);
const IconCalendar = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M3 10h18M8 3v4M16 3v4" />
  </svg>
);
const IconDoc = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 3h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
    <path d="M14 3v5h5M8 13h8M8 17h5" />
  </svg>
);
const IconCheck = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 12l5 5L20 6" />
  </svg>
);
const IconUsers = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="9" cy="8" r="3.5" />
    <path d="M3 20c0-3 2.5-5 6-5s6 2 6 5" />
    <circle cx="17" cy="9" r="2.5" />
    <path d="M15 20c0-2.5 2-4 4-4" />
  </svg>
);
const IconChart = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 20V10M10 20V4M16 20v-8M22 20H2" />
  </svg>
);
const IconHelp = ({ className }: IconProps) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .8-1 1.5V14M12 17h.01" />
  </svg>
);
/* ==========================================================================
   Sidebar — freee-style dark navy with icon+label
   ========================================================================== */
type NavItem = {
  key: string;
  label: string;
  icon: (p: IconProps) => JSX.Element;
  to?: string;
  disabled?: boolean;
  approverOnly?: boolean;
};

const NAV_MAIN: NavItem[] = [
  { key: "clock", label: "打刻", icon: IconClock, to: "/" },
  { key: "timesheet", label: "勤怠表", icon: IconCalendar, to: "/my/shifts" },
  { key: "request", label: "申請", icon: IconDoc, to: "/requests" },
  {
    key: "approval",
    label: "承認",
    icon: IconCheck,
    to: "/approvals",
    approverOnly: true,
  },
];

const NAV_ADMIN: NavItem[] = [
  {
    key: "employees",
    label: "社員",
    icon: IconUsers,
    to: "/admin/employees",
  },
  {
    key: "closing",
    label: "月次締め",
    icon: IconCheck,
    to: "/admin/closing",
  },
  {
    key: "shifts",
    label: "シフト",
    icon: IconCalendar,
    to: "/admin/shifts",
  },
  {
    key: "reports",
    label: "残業レポート",
    icon: IconChart,
    to: "/admin/overtime",
  },
  {
    key: "leaves",
    label: "休暇残高",
    icon: IconCalendar,
    to: "/admin/leaves",
  },
  {
    key: "departments",
    label: "部署",
    icon: IconUsers,
    to: "/admin/departments",
  },
  {
    key: "holidays",
    label: "祝日",
    icon: IconCalendar,
    to: "/admin/holidays",
  },
];

function Sidebar({ role }: { role: Role }) {
  const isAdmin = role === "admin";
  const canApprove = role === "admin" || role === "approver";
  const mainItems = NAV_MAIN.filter((i) => !i.approverOnly || canApprove);
  const [helpOpen, setHelpOpen] = useState(false);
  return (
    <aside className="flex w-[220px] shrink-0 flex-col bg-nav-bg text-nav-fg">
      {/* brand */}
      <div className="flex h-14 items-center gap-2 px-5">
        <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-500 font-bold text-white">
          勤
        </span>
        <span className="text-[15px] font-bold tracking-wide">勤怠管理</span>
      </div>

      <div className="mx-4 mb-3 h-px bg-nav-divider" />

      <nav className="flex-1 px-3 text-[13px]">
        <SidebarSection items={mainItems} />
        {isAdmin && (
          <>
            <div className="mt-6 px-3 pb-2 text-[10.5px] font-bold uppercase tracking-[0.14em] text-nav-fg-muted">
              管理
            </div>
            <SidebarSection items={NAV_ADMIN} />
          </>
        )}
      </nav>

      <div className="border-t border-nav-divider p-3">
        <button
          type="button"
          onClick={() => setHelpOpen(true)}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-nav-fg-muted hover:bg-nav-bg-hover hover:text-nav-fg"
        >
          <IconHelp className="h-4 w-4" />
          <span className="text-[13px]">ヘルプ</span>
        </button>
      </div>

      <HelpDialog open={helpOpen} role={role} onClose={() => setHelpOpen(false)} />
    </aside>
  );
}

function SidebarSection({ items }: { items: NavItem[] }) {
  return (
    <ul className="space-y-0.5">
      {items.map((it) => {
        const Icon = it.icon;
        if (it.disabled || !it.to) {
          return (
            <li key={it.key}>
              <span
                className="group flex w-full cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-left text-nav-fg-muted/70"
                title="未実装"
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="font-medium">{it.label}</span>
              </span>
            </li>
          );
        }
        return (
          <li key={it.key}>
            <NavLink
              to={it.to}
              end={it.to === "/"}
              className={({ isActive }) =>
                cn(
                  "group flex w-full items-center gap-3 rounded-md px-3 py-2 text-left transition-colors",
                  isActive
                    ? "bg-nav-active-bg text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]"
                    : "text-nav-fg/90 hover:bg-nav-bg-hover hover:text-white",
                )
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="font-medium">{it.label}</span>
            </NavLink>
          </li>
        );
      })}
    </ul>
  );
}

/* ==========================================================================
   Top bar — white, minimal, freee-ish
   ========================================================================== */
const ROLE_LABEL: Record<Role, string> = {
  admin: "管理者",
  approver: "承認者",
  member: "一般社員",
};

function TopBar({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const initial = user.name.slice(0, 1);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-divider bg-surface px-6">
      <div>
        <div className="text-[11px] font-medium text-text-tertiary">合同会社 サンプル</div>
        <div className="text-[13px] font-bold text-text-primary">マイページ</div>
      </div>

      <div className="flex items-center gap-2">
        <NotificationBell role={user.role} />

        <div className="mx-1 h-6 w-px bg-divider" />

        <div ref={menuRef} className="relative">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-2.5 rounded-full py-1 pl-1 pr-3 hover:bg-surface-alt"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-[13px] font-bold text-brand-600">
              {initial}
            </span>
            <span className="text-left">
              <div className="text-[13px] font-bold leading-tight text-text-primary">
                {user.name}
              </div>
              <div className="text-[11px] leading-tight text-text-tertiary">
                {ROLE_LABEL[user.role]}
              </div>
            </span>
            <svg viewBox="0 0 12 12" className="h-3 w-3 text-text-tertiary" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M2 4l4 4 4-4" />
            </svg>
          </button>

          {open && (
            <div className="absolute right-0 top-[calc(100%+6px)] w-60 overflow-hidden rounded-xl bg-surface shadow-card-hover">
              <div className="border-b border-divider px-4 py-3">
                <div className="text-[12.5px] font-bold text-text-primary">{user.name}</div>
                <div className="mt-0.5 truncate text-[11.5px] text-text-tertiary">{user.email}</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  setPwOpen(true);
                }}
                className="flex w-full items-center gap-2 border-b border-divider px-4 py-2.5 text-left text-[13px] font-medium text-text-primary hover:bg-surface-alt"
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1l3 3-3 3M12 1v9M21 12a9 9 0 1 1-18 0M12 14v7" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                パスワード変更
              </button>
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  onLogout();
                }}
                className="flex w-full items-center gap-2 px-4 py-2.5 text-left text-[13px] font-medium text-status-red hover:bg-status-red-bg"
              >
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M15 12H3M10 7l-5 5 5 5M17 5h3a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-3" />
                </svg>
                ログアウト
              </button>
            </div>
          )}
        </div>
      </div>

      <ChangePasswordDialog
        open={pwOpen}
        onClose={() => setPwOpen(false)}
        onSuccess={() => void 0}
      />
    </header>
  );
}

/* ==========================================================================
   Page header
   ========================================================================== */
function PageHeader() {
  return (
    <div className="mb-6 flex items-end justify-between gap-4">
      <div>
        <div className="mb-1 flex items-center gap-2 text-[12px] text-text-tertiary">
          <a href="/" className="hover:text-brand-600 hover:underline">ホーム</a>
          <span>/</span>
          <span className="text-text-secondary">打刻</span>
        </div>
        <h1 className="text-[22px] font-bold leading-tight text-text-primary">打刻</h1>
        <p className="mt-1 text-[13px] text-text-secondary">
          本日の出勤・退勤を記録し、勤務状況を確認します。
        </p>
      </div>
    </div>
  );
}

/* ==========================================================================
   Hero clock card — signature freee moment (wired to API)
   ========================================================================== */
function useToday() {
  return useQuery<TodayResponse>({
    queryKey: ["attendance", "today"],
    queryFn: apiToday,
    refetchInterval: 60_000,
  });
}

function useMonthly(year: number, month: number) {
  return useQuery<MonthlyResponse>({
    queryKey: ["attendance", "monthly", year, month],
    queryFn: () => apiMonthly(year, month),
  });
}

function ClockHero() {
  const now = useClock();
  const today = useToday();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const punch = useMutation({
    mutationFn: (type: PunchType) => apiPunch(type),
    onSuccess: () => {
      setError(null);
      void qc.invalidateQueries({ queryKey: ["attendance", "today"] });
      void qc.invalidateQueries({ queryKey: ["attendance", "monthly"] });
    },
    onError: (err: unknown) => {
      if (err instanceof AxiosError) {
        const detail = err.response?.data?.detail as string | undefined;
        setError(
          (detail && PUNCH_ERROR_MESSAGES[detail]) ||
            "打刻に失敗しました。時間を置いて再度お試しください。",
        );
      } else {
        setError("打刻に失敗しました。");
      }
    },
  });

  const state: PunchState = today.data?.state ?? "none";
  const daily = today.data?.daily ?? null;

  const hh = pad(now.getHours());
  const mm = pad(now.getMinutes());
  const ss = pad(now.getSeconds());
  const dateJp = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日（${JP_WEEKDAYS[now.getDay()]}）`;

  const elapsed = useMemo(() => {
    const startIso = daily?.first_clock_in_at ?? null;
    if (!startIso) return "00:00:00";
    const start = new Date(startIso);
    const end = daily?.last_clock_out_at ? new Date(daily.last_clock_out_at) : now;
    const diff = Math.max(0, end.getTime() - start.getTime());
    const h = Math.floor(diff / 3_600_000);
    const m = Math.floor((diff % 3_600_000) / 60_000);
    const s = Math.floor((diff % 60_000) / 1000);
    return `${pad(h)}:${pad(m)}:${pad(s)}`;
  }, [daily, now]);

  const chipMap: Record<PunchState, { label: string; cls: string; dot?: "green" | "amber" }> = {
    none: {
      label: "未打刻",
      cls: "bg-surface-alt text-text-secondary ring-1 ring-inset ring-border-default",
    },
    working: { label: "勤務中", cls: "bg-status-green-bg text-status-green", dot: "green" },
    on_break: { label: "休憩中", cls: "bg-status-amber-bg text-status-amber", dot: "amber" },
    done: { label: "退勤済", cls: "bg-brand-100 text-brand-700" },
  };
  const chip = chipMap[state];

  const disabled = {
    clock_in: state !== "none" || punch.isPending,
    clock_out: !(state === "working") || punch.isPending,
    break_start: !(state === "working") || punch.isPending,
    break_end: !(state === "on_break") || punch.isPending,
  };

  return (
    <section className="overflow-hidden rounded-[14px] bg-surface shadow-card">
      <div
        aria-hidden
        className="h-1.5 w-full"
        style={{
          background:
            "linear-gradient(90deg, hsl(var(--brand-500)) 0%, hsl(var(--brand-500)/0.6) 60%, hsl(var(--brand-100)) 100%)",
        }}
      />
      <div className="grid gap-8 p-8 md:grid-cols-[1.1fr_1fr] md:items-center md:p-10">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[13px] font-medium text-text-secondary">
            <IconCalendar className="h-4 w-4 text-brand-500" />
            {dateJp}
          </div>

          <div className="flex items-baseline gap-1 font-sans tabular text-text-primary">
            <span className="text-[88px] font-bold leading-none tracking-tight md:text-[112px]">{hh}</span>
            <span className="text-[72px] font-bold leading-none text-brand-500 md:text-[96px]">:</span>
            <span className="text-[88px] font-bold leading-none tracking-tight md:text-[112px]">{mm}</span>
            <span className="ml-1 text-[36px] font-medium leading-none text-text-tertiary md:text-[44px]">
              :{ss}
            </span>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-bold",
                chip.cls,
              )}
            >
              {chip.dot && (
                <span className="relative flex h-2 w-2">
                  <span
                    className={cn(
                      "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
                      chip.dot === "green" ? "bg-status-green" : "bg-status-amber",
                    )}
                  />
                  <span
                    className={cn(
                      "relative inline-flex h-2 w-2 rounded-full",
                      chip.dot === "green" ? "bg-status-green" : "bg-status-amber",
                    )}
                  />
                </span>
              )}
              {chip.label}
            </span>
            {daily?.first_clock_in_at && (
              <span className="text-[13px] text-text-secondary">
                出勤{" "}
                <span className="tabular font-bold text-text-primary">
                  {formatHM(daily.first_clock_in_at)}
                </span>
              </span>
            )}
            {daily?.last_clock_out_at && (
              <span className="text-[13px] text-text-secondary">
                退勤{" "}
                <span className="tabular font-bold text-text-primary">
                  {formatHM(daily.last_clock_out_at)}
                </span>
              </span>
            )}
          </div>

          {error && (
            <div className="mt-4 inline-flex items-center gap-2 rounded-lg bg-status-red-bg px-3 py-2 text-[12.5px] font-medium text-status-red">
              <span>!</span>
              {error}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-3 md:pl-8">
          <div className="grid grid-cols-2 gap-3">
            <PunchButton
              label="出勤"
              variant="primary"
              disabled={disabled.clock_in}
              onClick={() => punch.mutate("clock_in")}
              icon={
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12l5 5L20 7" />
                </svg>
              }
            />
            <PunchButton
              label="退勤"
              variant="outline"
              disabled={disabled.clock_out}
              onClick={() => punch.mutate("clock_out")}
              icon={
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M15 12H3M10 7l-5 5 5 5M21 5v14" />
                </svg>
              }
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <PunchButton
              label="休憩開始"
              variant="ghost"
              disabled={disabled.break_start}
              onClick={() => punch.mutate("break_start")}
              icon={
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M6 4h10a4 4 0 0 1 0 8h-1" />
                  <path d="M6 4v12a4 4 0 0 0 4 4h2a4 4 0 0 0 4-4v-4" />
                  <path d="M4 20h18" />
                </svg>
              }
            />
            <PunchButton
              label="休憩終了"
              variant="ghost"
              disabled={disabled.break_end}
              onClick={() => punch.mutate("break_end")}
              icon={
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12l4 4L19 6" />
                </svg>
              }
            />
          </div>

          <div className="mt-1 flex items-center justify-between rounded-lg bg-surface-alt px-4 py-2.5 text-[12px]">
            <span className="text-text-secondary">経過時間</span>
            <span className="tabular text-[15px] font-bold text-text-primary">{elapsed}</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function PunchButton({
  label,
  icon,
  variant,
  disabled,
  onClick,
}: {
  label: string;
  icon: React.ReactNode;
  variant: "primary" | "outline" | "ghost";
  disabled?: boolean;
  onClick: () => void;
}) {
  const base =
    "group relative flex h-14 items-center justify-center gap-2 rounded-xl text-[14.5px] font-bold transition-all";
  const variants: Record<typeof variant, string> = {
    primary: disabled
      ? "cursor-not-allowed bg-brand-100 text-brand-600"
      : "bg-brand-500 text-white shadow-[0_4px_0_hsl(var(--brand-700))] hover:bg-brand-600 active:translate-y-[4px] active:shadow-none",
    outline: disabled
      ? "cursor-not-allowed border border-divider bg-surface text-text-tertiary"
      : "border-2 border-brand-500 bg-surface text-brand-600 hover:bg-brand-50",
    ghost: disabled
      ? "cursor-not-allowed bg-surface-alt text-text-tertiary"
      : "bg-surface-alt text-text-secondary hover:bg-brand-50 hover:text-brand-600",
  };
  return (
    <button type="button" onClick={onClick} disabled={disabled} className={cn(base, variants[variant])}>
      <span className="flex h-6 w-6 items-center justify-center">{icon}</span>
      <span>{label}</span>
    </button>
  );
}

/* ==========================================================================
   Stat tiles
   ========================================================================== */
function MonthlyStatsTiles() {
  const now = new Date();
  const monthly = useMonthly(now.getFullYear(), now.getMonth() + 1);
  const stats = monthly.data?.stats;

  const leave = useQuery<LeaveBalanceSummary>({
    queryKey: ["leaves", "balance", now.getFullYear()],
    queryFn: () => apiMyLeaveBalance(now.getFullYear()),
  });

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
      <StatTile
        label="今月の勤務日数"
        value={String(stats?.working_days ?? 0)}
        unit="日"
        tone="brand"
        caption="所定 20 日"
      />
      <StatTile
        label="今月の労働時間"
        value={formatMinutes(stats?.total_worked_minutes ?? 0)}
        caption={monthly.isLoading ? "集計中…" : undefined}
      />
      <StatTile
        label="残業時間"
        value={formatMinutes(stats?.total_overtime_minutes ?? 0)}
        tone={stats && stats.total_overtime_minutes > 0 ? "warn" : "neutral"}
        caption="上限 45:00"
      />
      <StatTile
        label="有給残"
        value={leave.data ? String(Number(leave.data.remaining_days)) : "—"}
        unit="日"
        caption={
          leave.data
            ? `付与 ${Number(leave.data.granted_days)} / 使用 ${Number(leave.data.used_days)}`
            : "集計中…"
        }
      />
    </div>
  );
}

function StatTile({
  label,
  value,
  unit,
  caption,
  tone = "neutral",
}: {
  label: string;
  value: string;
  unit?: string;
  caption?: string;
  tone?: "neutral" | "brand" | "warn";
}) {
  const toneCls = {
    neutral: "text-text-primary",
    brand: "text-brand-600",
    warn: "text-status-amber",
  }[tone];
  return (
    <div className="rounded-xl bg-surface p-5 shadow-card">
      <div className="text-[12px] font-medium text-text-secondary">{label}</div>
      <div className="mt-2 flex items-baseline gap-1">
        <span className={cn("tabular text-[28px] font-bold leading-none", toneCls)}>{value}</span>
        {unit && <span className="text-[13px] font-medium text-text-tertiary">{unit}</span>}
      </div>
      {caption && <div className="mt-2 text-[11.5px] text-text-tertiary">{caption}</div>}
    </div>
  );
}

/* ==========================================================================
   Today's record & weekly summary
   ========================================================================== */
function TodayCard() {
  const today = useToday();
  const daily = today.data?.daily ?? null;
  return (
    <Card
      title="本日の勤務"
      action={
        <button type="button" className="text-[12px] font-bold text-brand-600 hover:underline">
          編集を申請
        </button>
      }
    >
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-[13px]">
        <Row label="出勤時刻" value={formatHM(daily?.first_clock_in_at)} />
        <Row label="退勤時刻" value={formatHM(daily?.last_clock_out_at)} />
        <Row
          label="労働時間"
          value={formatMinutes(daily?.worked_minutes ?? 0)}
          mono
        />
        <Row
          label="残業時間"
          value={formatMinutes(daily?.overtime_minutes ?? 0)}
          mono
        />
        <Row
          label="休憩時間"
          value={formatMinutes(daily?.break_minutes ?? 0)}
          mono
        />
        <Row label="所定勤務時間" value="08:00" mono muted />
      </dl>
    </Card>
  );
}

function Row({
  label,
  value,
  mono,
  muted,
}: {
  label: string;
  value: string;
  mono?: boolean;
  muted?: boolean;
}) {
  return (
    <>
      <dt className="text-text-secondary">{label}</dt>
      <dd
        className={cn(
          "text-right font-medium",
          mono && "tabular",
          muted ? "text-text-tertiary" : "text-text-primary",
        )}
      >
        {value}
      </dd>
    </>
  );
}

function WeekCard() {
  const now = new Date();
  const monthly = useMonthly(now.getFullYear(), now.getMonth() + 1);

  const weekDays = useMemo(() => {
    // Monday as first day of week
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const jsDow = today.getDay(); // 0=Sun..6=Sat
    const offsetToMonday = (jsDow + 6) % 7;
    const monday = new Date(today);
    monday.setDate(today.getDate() - offsetToMonday);
    return Array.from({ length: 7 }).map((_, i) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      return d;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [now.toDateString()]);

  const byDate = new Map<string, DailyAttendanceOut>(
    (monthly.data?.days ?? []).map((d) => [d.work_date, d] as const),
  );

  const todayStr = new Date().toISOString().slice(0, 10);
  const labels = ["月", "火", "水", "木", "金", "土", "日"];

  let weekTotal = 0;
  let weekOvertime = 0;
  let weekDaysCount = 0;
  for (const d of weekDays) {
    const key = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    const rec = byDate.get(key);
    if (rec && rec.worked_minutes > 0) {
      weekTotal += rec.worked_minutes;
      weekOvertime += rec.overtime_minutes;
      weekDaysCount += 1;
    }
  }

  return (
    <Card
      title="今週の勤怠"
      action={
        <button type="button" className="text-[12px] font-bold text-brand-600 hover:underline">
          月次レポート ›
        </button>
      }
    >
      <div className="grid grid-cols-7 gap-2">
        {weekDays.map((d, i) => {
          const key = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
          const rec = byDate.get(key);
          const worked = rec?.worked_minutes ?? 0;
          const isToday = key === todayStr;
          const isWeekend = i >= 5;
          return (
            <div
              key={key}
              className={cn(
                "flex flex-col items-center gap-1 rounded-lg py-3 text-center",
                isToday ? "bg-brand-50 ring-2 ring-inset ring-brand-500" : "bg-surface-alt",
              )}
            >
              <span
                className={cn(
                  "text-[11px] font-bold",
                  isWeekend ? "text-status-red" : "text-text-secondary",
                  isToday && "text-brand-600",
                )}
              >
                {labels[i]}
                <span className="ml-0.5 font-normal text-text-tertiary">{d.getDate()}</span>
              </span>
              <span
                className={cn(
                  "tabular text-[13px] font-bold",
                  worked > 0 ? "text-text-primary" : "text-text-tertiary",
                )}
              >
                {worked > 0 ? formatMinutes(worked) : "—"}
              </span>
              <span
                className={cn(
                  "inline-flex h-1.5 w-6 rounded-full",
                  worked > 0 ? "bg-status-green" : "bg-divider",
                )}
              />
            </div>
          );
        })}
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3 border-t border-divider pt-4 text-center">
        <MiniStat label="勤務日数" value={String(weekDaysCount)} unit="日" />
        <MiniStat label="合計労働" value={formatMinutes(weekTotal)} />
        <MiniStat
          label="残業"
          value={formatMinutes(weekOvertime)}
          tone={weekOvertime > 0 ? "warn" : undefined}
        />
      </div>
    </Card>
  );
}

function MiniStat({
  label,
  value,
  unit,
  tone,
}: {
  label: string;
  value: string;
  unit?: string;
  tone?: "warn";
}) {
  return (
    <div>
      <div className="text-[11px] text-text-tertiary">{label}</div>
      <div
        className={cn(
          "tabular text-[17px] font-bold",
          tone === "warn" ? "text-status-amber" : "text-text-primary",
        )}
      >
        {value}
        {unit && <span className="ml-0.5 text-[11px] font-medium text-text-tertiary">{unit}</span>}
      </div>
    </div>
  );
}

/* ==========================================================================
   Leave balance card (visible to everyone)
   ========================================================================== */
function LeaveBalanceCard() {
  const q = useQuery<LeaveBalanceSummary>({
    queryKey: ["leaves", "me"],
    queryFn: () => apiMyLeaveBalance(),
    retry: 0,
  });

  const year = q.data?.year ?? new Date().getFullYear();

  return (
    <Card
      title={`${year}年 有給休暇残`}
      action={
        <NavLink
          to="/requests"
          className="text-[12px] font-bold text-brand-600 hover:underline"
        >
          休暇を申請 ›
        </NavLink>
      }
    >
      {q.isLoading && (
        <div className="py-4 text-center text-[13px] text-text-tertiary">
          読み込み中…
        </div>
      )}
      {q.isError && (
        <div className="py-4 text-center text-[13px] text-text-tertiary">
          今年度の付与はまだ行われていません。
        </div>
      )}
      {q.data && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <BalanceTile label="残日数" value={q.data.remaining_days} accent />
          <BalanceTile label="付与" value={q.data.granted_days} />
          <BalanceTile label="繰越" value={q.data.carried_over_days} />
          <BalanceTile label="消化" value={q.data.used_days} />
        </div>
      )}
    </Card>
  );
}

function BalanceTile({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  const num = Number(value);
  const display = Number.isFinite(num) ? num.toFixed(1) : value;
  return (
    <div
      className={cn(
        "rounded-lg p-3",
        accent ? "bg-brand-50 ring-1 ring-brand-100" : "bg-surface-alt",
      )}
    >
      <div className="text-[11px] font-medium text-text-tertiary">{label}</div>
      <div className="mt-1 flex items-baseline gap-1">
        <span
          className={cn(
            "text-[20px] font-bold tabular",
            accent ? "text-brand-600" : "text-text-primary",
          )}
        >
          {display}
        </span>
        <span className="text-[11px] text-text-tertiary">日</span>
      </div>
    </div>
  );
}

/* ==========================================================================
   Card shell
   ========================================================================== */
function Card({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl bg-surface p-5 shadow-card">
      <header className="mb-4 flex items-center justify-between gap-4">
        <h2 className="text-[14px] font-bold text-text-primary">{title}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}

/* ==========================================================================
   App
   ========================================================================== */
export default function App() {
  const user = useAuthStore((s) => s.user);
  const { logout } = useAuth();

  if (!user) return null; // guarded by ProtectedRoute, defensive only

  return (
    <div className="flex h-screen bg-page-bg">
      <Sidebar role={user.role} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar user={user} onLogout={() => void logout()} />
        <main className="flex-1 overflow-auto px-8 py-6">
          <div className="mx-auto max-w-[1120px]">
            <Outlet />
            <footer className="mt-10 border-t border-divider pt-5 text-[11px] text-text-tertiary">
              勤怠管理 v0.1.0 · © 2026 Sample Inc.
            </footer>
          </div>
        </main>
      </div>
    </div>
  );
}

export function ClockPage() {
  return (
    <>
      <PageHeader />
      <div className="space-y-6">
        <ClockHero />
        <MonthlyStatsTiles />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_1.35fr]">
          <TodayCard />
          <WeekCard />
        </div>
        <LeaveBalanceCard />
      </div>
    </>
  );
}
