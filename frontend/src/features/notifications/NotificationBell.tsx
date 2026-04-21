import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  apiApprovalQueue,
  apiListOwnRequests,
  type ApprovalQueueItem,
  type RequestOut,
  type RequestType,
} from "@/lib/api";
import type { Role } from "@/lib/auth-store";
import { cn } from "@/lib/utils";

const REQUEST_TYPE_LABEL: Record<RequestType, string> = {
  punch_fix: "打刻修正",
  overtime_pre: "残業（事前）",
  overtime_post: "残業（事後）",
  leave: "休暇",
};

const STORAGE_KEY = "notifications_seen_at";

function getSeenAt(): number {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return 0;
  const n = Number(raw);
  return Number.isFinite(n) ? n : 0;
}

function setSeenAt(ms: number) {
  localStorage.setItem(STORAGE_KEY, String(ms));
}

export default function NotificationBell({ role }: { role: Role }) {
  const [open, setOpen] = useState(false);
  const [seenAt, setSeenAtState] = useState<number>(() => getSeenAt());
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const canApprove = role === "admin" || role === "approver";

  // Own requests: surface approved/rejected within last 7 days
  const own = useQuery<RequestOut[]>({
    queryKey: ["requests", "own"],
    queryFn: apiListOwnRequests,
    refetchInterval: 60_000,
  });

  // Approval queue (approvers/admins only)
  const queue = useQuery<ApprovalQueueItem[]>({
    queryKey: ["approvals", "queue"],
    queryFn: apiApprovalQueue,
    enabled: canApprove,
    refetchInterval: 60_000,
  });

  const decidedItems = useMemo(() => {
    const list = own.data ?? [];
    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
    return list
      .filter(
        (r) =>
          (r.status === "approved" || r.status === "rejected") &&
          r.decided_at !== null &&
          new Date(r.decided_at).getTime() >= cutoff,
      )
      .sort((a, b) => {
        const ta = a.decided_at ? new Date(a.decided_at).getTime() : 0;
        const tb = b.decided_at ? new Date(b.decided_at).getTime() : 0;
        return tb - ta;
      })
      .slice(0, 10);
  }, [own.data]);

  const unreadDecided = decidedItems.filter(
    (r) => r.decided_at && new Date(r.decided_at).getTime() > seenAt,
  ).length;

  const pendingCount = canApprove ? (queue.data?.length ?? 0) : 0;
  const unreadTotal = unreadDecided + pendingCount;

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

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) {
      const now = Date.now();
      setSeenAt(now);
      setSeenAtState(now);
    }
  }

  return (
    <div ref={menuRef} className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-label="通知"
        className="relative flex h-9 w-9 items-center justify-center rounded-full text-text-secondary hover:bg-surface-alt hover:text-text-primary"
      >
        <svg
          viewBox="0 0 24 24"
          className="h-[18px] w-[18px]"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2H4.5L6 16z" />
          <path d="M10 20a2 2 0 0 0 4 0" />
        </svg>
        {unreadTotal > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-status-red px-1 text-[10px] font-bold text-white">
            {unreadTotal > 99 ? "99+" : unreadTotal}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-[calc(100%+6px)] z-40 w-80 overflow-hidden rounded-xl bg-surface shadow-card-hover">
          <div className="border-b border-divider px-4 py-2.5">
            <div className="text-[12.5px] font-bold text-text-primary">通知</div>
          </div>

          <div className="max-h-[60vh] overflow-y-auto">
            {canApprove && pendingCount > 0 && (
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  navigate("/approvals");
                }}
                className="flex w-full items-start gap-3 border-b border-divider px-4 py-3 text-left hover:bg-surface-alt"
              >
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-100 text-brand-600">
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 10l3 3 9-9" />
                  </svg>
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-[12.5px] font-bold text-text-primary">
                    承認待ちの申請が {pendingCount} 件あります
                  </div>
                  <div className="text-[11.5px] text-text-tertiary">
                    クリックで承認キューへ
                  </div>
                </div>
              </button>
            )}

            {decidedItems.length === 0 && pendingCount === 0 && (
              <div className="px-4 py-10 text-center text-[12.5px] text-text-tertiary">
                通知はありません
              </div>
            )}

            {decidedItems.map((r) => {
              const isNew =
                r.decided_at && new Date(r.decided_at).getTime() > seenAt;
              const approved = r.status === "approved";
              return (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    navigate("/requests");
                  }}
                  className="flex w-full items-start gap-3 border-b border-divider px-4 py-3 text-left hover:bg-surface-alt"
                >
                  <span
                    className={cn(
                      "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                      approved
                        ? "bg-status-green-bg text-status-green"
                        : "bg-status-red-bg text-status-red",
                    )}
                  >
                    {approved ? (
                      <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M4 10l3 3 9-9" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        <path d="M5 5l10 10M15 5L5 15" />
                      </svg>
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[12.5px] font-bold text-text-primary">
                      {REQUEST_TYPE_LABEL[r.type]} が{approved ? "承認" : "却下"}されました
                      {isNew && (
                        <span className="ml-2 rounded-full bg-brand-500 px-1.5 py-[1px] align-middle text-[9.5px] font-bold text-white">
                          NEW
                        </span>
                      )}
                    </div>
                    <div className="text-[11.5px] text-text-tertiary">
                      {r.decided_at &&
                        new Date(r.decided_at).toLocaleString("ja-JP")}
                      {r.target_date && ` ・ ${r.target_date}`}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
