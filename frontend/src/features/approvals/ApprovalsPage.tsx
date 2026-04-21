import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { AxiosError } from "axios";
import { useState } from "react";

import {
  apiApprovalQueue,
  apiApprove,
  apiReject,
  type ApprovalQueueItem,
  type PunchType,
  type RequestPayload,
  type RequestType,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const DECISION_ERROR_LABEL: Record<string, string> = {
  self_approval_forbidden:
    "自分で出した申請は自分では承認／却下できません。別の承認者に依頼してください。",
  request_not_pending: "この申請は既に処理済みです。画面を更新してください。",
  request_not_found: "申請が見つかりません（削除された可能性があります）。",
  month_closed:
    "対象月が締め済みのため処理できません。先に月次締めを再オープンしてください。",
  already_decided: "この申請は既に処理済みです。",
};

function translateDetail(detail: string): string | null {
  if (DECISION_ERROR_LABEL[detail]) return DECISION_ERROR_LABEL[detail];
  // leave_insufficient_balance: remaining=0.0, requested=1
  const m = detail.match(
    /^leave_insufficient_balance:\s*remaining=([\d.]+),\s*requested=([\d.]+)/,
  );
  if (m) {
    const remaining = Number(m[1]).toFixed(1);
    const requested = Number(m[2]).toFixed(1);
    return `有給残日数が足りません（残 ${remaining} 日 / 要求 ${requested} 日）。管理者が「休暇残高」→「全社員に付与」または個別付与を実行してください。`;
  }
  if (detail.startsWith("leave_")) {
    return `休暇申請を処理できませんでした（${detail.replace("leave_", "")}）`;
  }
  return null;
}

function extractErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof AxiosError) {
    const detail = (err.response?.data as { detail?: string } | undefined)
      ?.detail;
    if (detail) {
      const translated = translateDetail(detail);
      if (translated) return translated;
      return `${fallback}（${detail}）`;
    }
  }
  return fallback;
}

const REQUEST_TYPE_LABEL: Record<RequestType, string> = {
  punch_fix: "打刻修正",
  overtime_pre: "残業（事前）",
  overtime_post: "残業（事後）",
  leave: "休暇",
};

const PUNCH_TYPE_LABEL: Record<PunchType, string> = {
  clock_in: "出勤",
  clock_out: "退勤",
  break_start: "休憩開始",
  break_end: "休憩終了",
};

const LEAVE_KIND_LABEL: Record<string, string> = {
  full_day: "全日",
  half_day_am: "半休（午前）",
  half_day_pm: "半休（午後）",
};

export default function ApprovalsPage() {
  const queue = useQuery<ApprovalQueueItem[]>({
    queryKey: ["approvals", "queue"],
    queryFn: apiApprovalQueue,
    refetchInterval: 30_000,
  });

  return (
    <>
      <div className="mb-6">
        <div className="mb-1 text-[12px] text-text-tertiary">ホーム / 承認</div>
        <h1 className="text-[22px] font-bold text-text-primary">承認キュー</h1>
        <p className="mt-1 text-[13px] text-text-secondary">
          提出された申請を確認し、承認または却下します。
        </p>
      </div>

      <section className="rounded-xl bg-surface p-5 shadow-card">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[14px] font-bold text-text-primary">
            未処理 <span className="ml-1 text-text-tertiary">({queue.data?.length ?? 0})</span>
          </h2>
        </div>

        {queue.isLoading && (
          <div className="py-8 text-center text-[13px] text-text-tertiary">
            読み込み中…
          </div>
        )}

        {queue.data && queue.data.length === 0 && (
          <div className="py-8 text-center text-[13px] text-text-tertiary">
            承認待ちの申請はありません。
          </div>
        )}

        {queue.data && queue.data.length > 0 && (
          <ul className="space-y-3">
            {queue.data.map((item) => (
              <ApprovalCard key={item.approval_id} item={item} />
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

function ApprovalCard({ item }: { item: ApprovalQueueItem }) {
  const qc = useQueryClient();
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);

  const approve = useMutation({
    mutationFn: () => apiApprove(item.approval_id, comment || null),
    onSuccess: () => {
      setError(null);
      void qc.invalidateQueries({ queryKey: ["approvals", "queue"] });
    },
    onError: (err) => setError(extractErrorMessage(err, "承認に失敗しました")),
  });
  const reject = useMutation({
    mutationFn: () => apiReject(item.approval_id, comment || null),
    onSuccess: () => {
      setError(null);
      void qc.invalidateQueries({ queryKey: ["approvals", "queue"] });
    },
    onError: (err) => setError(extractErrorMessage(err, "却下に失敗しました")),
  });

  const busy = approve.isPending || reject.isPending;

  return (
    <li className="rounded-xl border border-divider p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="rounded-md bg-brand-50 px-2 py-0.5 text-[11.5px] font-bold text-brand-600">
              {REQUEST_TYPE_LABEL[item.request.type]}
            </span>
            <span className="text-[12px] text-text-tertiary">
              ステップ {item.step}
            </span>
          </div>
          <div className="mt-1.5 text-[14px] font-bold text-text-primary">
            {item.requested_by_name}{" "}
            <span className="font-normal text-text-tertiary">
              {item.requested_by_email}
            </span>
          </div>
          <div className="mt-0.5 text-[11.5px] text-text-tertiary">
            提出 {new Date(item.request.submitted_at).toLocaleString("ja-JP")}
          </div>
          <PayloadPreview payload={item.request.payload} />
          {item.request.requester_comment && (
            <div className="mt-2 rounded-md bg-surface-alt p-2 text-[12.5px] text-text-secondary">
              「{item.request.requester_comment}」
            </div>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          type="text"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="コメント（任意）"
          className="h-9 w-full rounded-lg border border-border-default bg-surface px-3 text-[13px] outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100 sm:flex-1"
          disabled={busy}
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => reject.mutate()}
            className={cn(
              "inline-flex h-9 items-center rounded-lg border px-4 text-[12.5px] font-bold",
              "border-status-red text-status-red hover:bg-status-red-bg",
              "disabled:cursor-not-allowed disabled:border-divider disabled:text-text-tertiary disabled:hover:bg-transparent",
            )}
          >
            却下
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => approve.mutate()}
            className={cn(
              "inline-flex h-9 items-center rounded-lg bg-brand-500 px-5 text-[12.5px] font-bold text-white",
              "shadow-[0_2px_0_hsl(var(--brand-700))] hover:bg-brand-600",
              "disabled:cursor-not-allowed disabled:bg-brand-100 disabled:text-brand-600 disabled:shadow-none",
            )}
          >
            承認
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-2 text-[12px] font-medium text-status-red">{error}</div>
      )}
    </li>
  );
}

function PayloadPreview({ payload }: { payload: RequestPayload }) {
  if (payload.kind === "punch_fix") {
    return (
      <div className="mt-2 space-y-0.5 text-[12.5px] text-text-secondary">
        <Row label="対象日" value={payload.target_date} />
        <Row label="打刻種別" value={PUNCH_TYPE_LABEL[payload.punch_type]} />
        <Row
          label="打刻時刻"
          value={new Date(payload.punched_at).toLocaleString("ja-JP")}
        />
        <Row label="理由" value={payload.reason} />
      </div>
    );
  }
  if (payload.kind === "overtime_pre") {
    return (
      <div className="mt-2 space-y-0.5 text-[12.5px] text-text-secondary">
        <Row label="対象日" value={payload.target_date} />
        <Row label="予定残業" value={`${payload.planned_minutes} 分`} />
        <Row label="理由" value={payload.reason} />
      </div>
    );
  }
  if (payload.kind === "overtime_post") {
    return (
      <div className="mt-2 space-y-0.5 text-[12.5px] text-text-secondary">
        <Row label="対象日" value={payload.target_date} />
        <Row label="実績残業" value={`${payload.actual_minutes} 分`} />
        <Row label="理由" value={payload.reason} />
      </div>
    );
  }
  return (
    <div className="mt-2 space-y-0.5 text-[12.5px] text-text-secondary">
      <Row label="期間" value={`${payload.start_date} 〜 ${payload.end_date}`} />
      <Row label="種別" value={LEAVE_KIND_LABEL[payload.leave_kind]} />
      <Row label="理由" value={payload.reason} />
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-3">
      <span className="min-w-[64px] text-text-tertiary">{label}</span>
      <span className="text-text-primary">{value}</span>
    </div>
  );
}
