import { zodResolver } from "@hookform/resolvers/zod";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { AxiosError } from "axios";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  apiCancelRequest,
  apiCreateRequest,
  apiListOwnRequests,
  type PunchType,
  type RequestOut,
  type RequestPayload,
  type RequestStatus,
  type RequestType,
} from "@/lib/api";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Schemas & helpers
// ---------------------------------------------------------------------------
const punchFixSchema = z.object({
  target_date: z.string().min(1, "対象日を入力してください"),
  punch_type: z.enum(["clock_in", "clock_out", "break_start", "break_end"]),
  punched_at: z.string().min(1, "時刻を入力してください"),
  reason: z.string().min(1, "理由を記入してください").max(500),
});
type PunchFixForm = z.infer<typeof punchFixSchema>;

const overtimeSchema = z.object({
  target_date: z.string().min(1),
  planned_minutes: z.coerce.number().int().positive().max(600),
  reason: z.string().min(1).max(500),
});
type OvertimeForm = z.infer<typeof overtimeSchema>;

const overtimePostSchema = z.object({
  target_date: z.string().min(1),
  actual_minutes: z.coerce.number().int().positive().max(600),
  reason: z.string().min(1).max(500),
});
type OvertimePostForm = z.infer<typeof overtimePostSchema>;

const leaveSchema = z
  .object({
    start_date: z.string().min(1),
    end_date: z.string().min(1),
    leave_kind: z.enum(["full_day", "half_day_am", "half_day_pm"]),
    reason: z.string().min(1).max(500),
  })
  .refine((d) => d.end_date >= d.start_date, {
    message: "終了日は開始日以降にしてください",
    path: ["end_date"],
  });
type LeaveForm = z.infer<typeof leaveSchema>;

const REQUEST_TYPE_LABEL: Record<RequestType, string> = {
  punch_fix: "打刻修正",
  overtime_pre: "残業（事前）",
  overtime_post: "残業（事後）",
  leave: "休暇",
};

const REQUEST_STATUS_LABEL: Record<
  RequestStatus,
  { label: string; cls: string }
> = {
  draft: {
    label: "下書き",
    cls: "bg-surface-alt text-text-tertiary ring-1 ring-inset ring-border-default",
  },
  pending: { label: "承認待ち", cls: "bg-status-amber-bg text-status-amber" },
  approved: { label: "承認済", cls: "bg-status-green-bg text-status-green" },
  rejected: { label: "却下", cls: "bg-status-red-bg text-status-red" },
  canceled: {
    label: "取消",
    cls: "bg-surface-alt text-text-tertiary ring-1 ring-inset ring-border-default",
  },
};

const PUNCH_TYPE_LABEL: Record<PunchType, string> = {
  clock_in: "出勤",
  clock_out: "退勤",
  break_start: "休憩開始",
  break_end: "休憩終了",
};

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function nowLocalIsoMinute(): string {
  const d = new Date();
  return `${todayIso()}T${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
type Tab = "punch_fix" | "overtime_pre" | "overtime_post" | "leave";

export default function RequestsPage() {
  const [tab, setTab] = useState<Tab>("punch_fix");
  const requests = useQuery<RequestOut[]>({
    queryKey: ["requests", "own"],
    queryFn: apiListOwnRequests,
  });

  return (
    <>
      <div className="mb-6">
        <div className="mb-1 text-[12px] text-text-tertiary">ホーム / 申請</div>
        <h1 className="text-[22px] font-bold text-text-primary">申請</h1>
        <p className="mt-1 text-[13px] text-text-secondary">
          打刻修正・残業事前申請・休暇などの提出と進捗確認ができます。
        </p>
      </div>

      <div className="space-y-6">
        <section className="rounded-xl bg-surface p-6 shadow-card">
          <h2 className="mb-3 text-[14px] font-bold text-text-primary">新規申請</h2>
          <div className="mb-5 inline-flex rounded-lg bg-surface-alt p-1">
            {(
              ["punch_fix", "overtime_pre", "overtime_post", "leave"] as const
            ).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTab(t)}
                className={cn(
                  "rounded-md px-4 py-1.5 text-[12.5px] font-bold transition",
                  tab === t
                    ? "bg-surface text-brand-600 shadow-[0_1px_2px_rgba(0,0,0,0.05)]"
                    : "text-text-secondary hover:text-text-primary",
                )}
              >
                {REQUEST_TYPE_LABEL[t]}
              </button>
            ))}
          </div>

          {tab === "punch_fix" && <PunchFixForm />}
          {tab === "overtime_pre" && <OvertimeForm />}
          {tab === "overtime_post" && <OvertimePostForm />}
          {tab === "leave" && <LeaveForm />}
        </section>

        <section className="rounded-xl bg-surface p-5 shadow-card">
          <h2 className="mb-4 text-[14px] font-bold text-text-primary">自分の申請一覧</h2>
          {requests.isLoading && (
            <div className="py-6 text-center text-[13px] text-text-tertiary">
              読み込み中…
            </div>
          )}
          {requests.data && requests.data.length === 0 && (
            <div className="py-6 text-center text-[13px] text-text-tertiary">
              申請はまだありません。
            </div>
          )}
          {requests.data && requests.data.length > 0 && (
            <RequestTable rows={requests.data} />
          )}
        </section>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Forms
// ---------------------------------------------------------------------------
function FormShell({
  onSubmit,
  error,
  submitting,
  children,
}: {
  onSubmit: (e: React.FormEvent) => void;
  error?: string | null;
  submitting?: boolean;
  children: React.ReactNode;
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {children}
      {error && (
        <div className="rounded-lg bg-status-red-bg px-3 py-2 text-[12.5px] font-medium text-status-red">
          {error}
        </div>
      )}
      <button
        type="submit"
        disabled={submitting}
        className={cn(
          "inline-flex h-10 items-center justify-center rounded-lg bg-brand-500 px-6 text-[13px] font-bold text-white",
          "shadow-[0_3px_0_hsl(var(--brand-700))] hover:bg-brand-600",
          "active:translate-y-[3px] active:shadow-none",
          "disabled:cursor-not-allowed disabled:bg-brand-100 disabled:text-brand-600 disabled:shadow-none",
        )}
      >
        {submitting ? "送信中…" : "申請する"}
      </button>
    </form>
  );
}

function PunchFixForm() {
  const qc = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PunchFixForm>({
    resolver: zodResolver(punchFixSchema),
    defaultValues: {
      target_date: todayIso(),
      punch_type: "clock_in",
      punched_at: nowLocalIsoMinute(),
      reason: "",
    },
  });

  const mut = useMutation({
    mutationFn: (p: RequestPayload) => apiCreateRequest(p),
    onSuccess: () => {
      setServerError(null);
      reset({
        target_date: todayIso(),
        punch_type: "clock_in",
        punched_at: nowLocalIsoMinute(),
        reason: "",
      });
      void qc.invalidateQueries({ queryKey: ["requests", "own"] });
    },
    onError: (err) => {
      setServerError(
        err instanceof AxiosError
          ? `送信に失敗しました（${err.response?.status ?? "?"}）`
          : "送信に失敗しました",
      );
    },
  });

  return (
    <FormShell
      onSubmit={handleSubmit((d) =>
        mut.mutate({
          kind: "punch_fix",
          target_date: d.target_date,
          punch_type: d.punch_type,
          punched_at: new Date(d.punched_at).toISOString(),
          reason: d.reason,
        }),
      )}
      error={serverError}
      submitting={mut.isPending}
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="対象日" error={errors.target_date?.message}>
          <input type="date" {...register("target_date")} className={inputCls} />
        </Field>
        <Field label="打刻種別" error={errors.punch_type?.message}>
          <select {...register("punch_type")} className={inputCls}>
            {(Object.keys(PUNCH_TYPE_LABEL) as PunchType[]).map((k) => (
              <option key={k} value={k}>
                {PUNCH_TYPE_LABEL[k]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="打刻時刻" error={errors.punched_at?.message}>
          <input
            type="datetime-local"
            {...register("punched_at")}
            className={inputCls}
          />
        </Field>
      </div>
      <Field label="理由" error={errors.reason?.message}>
        <textarea rows={3} {...register("reason")} className={textareaCls} />
      </Field>
    </FormShell>
  );
}

function OvertimeForm() {
  const qc = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<OvertimeForm>({
    resolver: zodResolver(overtimeSchema),
    defaultValues: {
      target_date: todayIso(),
      planned_minutes: 60,
      reason: "",
    },
  });

  const mut = useMutation({
    mutationFn: (p: RequestPayload) => apiCreateRequest(p),
    onSuccess: () => {
      setServerError(null);
      reset();
      void qc.invalidateQueries({ queryKey: ["requests", "own"] });
    },
    onError: (err) =>
      setServerError(
        err instanceof AxiosError ? "送信に失敗しました" : "送信に失敗しました",
      ),
  });

  return (
    <FormShell
      onSubmit={handleSubmit((d) =>
        mut.mutate({
          kind: "overtime_pre",
          target_date: d.target_date,
          planned_minutes: d.planned_minutes,
          reason: d.reason,
        }),
      )}
      error={serverError}
      submitting={mut.isPending}
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="対象日" error={errors.target_date?.message}>
          <input type="date" {...register("target_date")} className={inputCls} />
        </Field>
        <Field
          label="予定残業（分）"
          error={errors.planned_minutes?.message}
        >
          <input
            type="number"
            min={1}
            max={600}
            {...register("planned_minutes")}
            className={inputCls}
          />
        </Field>
      </div>
      <Field label="理由" error={errors.reason?.message}>
        <textarea rows={3} {...register("reason")} className={textareaCls} />
      </Field>
    </FormShell>
  );
}

function OvertimePostForm() {
  const qc = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<OvertimePostForm>({
    resolver: zodResolver(overtimePostSchema),
    defaultValues: {
      target_date: todayIso(),
      actual_minutes: 60,
      reason: "",
    },
  });

  const mut = useMutation({
    mutationFn: (p: RequestPayload) => apiCreateRequest(p),
    onSuccess: () => {
      setServerError(null);
      reset();
      void qc.invalidateQueries({ queryKey: ["requests", "own"] });
    },
    onError: () => setServerError("送信に失敗しました"),
  });

  return (
    <FormShell
      onSubmit={handleSubmit((d) =>
        mut.mutate({
          kind: "overtime_post",
          target_date: d.target_date,
          actual_minutes: d.actual_minutes,
          reason: d.reason,
        }),
      )}
      error={serverError}
      submitting={mut.isPending}
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="対象日" error={errors.target_date?.message}>
          <input type="date" {...register("target_date")} className={inputCls} />
        </Field>
        <Field
          label="実績残業（分）"
          error={errors.actual_minutes?.message}
        >
          <input
            type="number"
            min={1}
            max={600}
            {...register("actual_minutes")}
            className={inputCls}
          />
        </Field>
      </div>
      <Field label="理由" error={errors.reason?.message}>
        <textarea rows={3} {...register("reason")} className={textareaCls} />
      </Field>
    </FormShell>
  );
}

function LeaveForm() {
  const qc = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<LeaveForm>({
    resolver: zodResolver(leaveSchema),
    defaultValues: {
      start_date: todayIso(),
      end_date: todayIso(),
      leave_kind: "full_day",
      reason: "",
    },
  });

  const mut = useMutation({
    mutationFn: (p: RequestPayload) => apiCreateRequest(p),
    onSuccess: () => {
      setServerError(null);
      reset();
      void qc.invalidateQueries({ queryKey: ["requests", "own"] });
    },
    onError: () => setServerError("送信に失敗しました"),
  });

  return (
    <FormShell
      onSubmit={handleSubmit((d) =>
        mut.mutate({
          kind: "leave",
          start_date: d.start_date,
          end_date: d.end_date,
          leave_kind: d.leave_kind,
          reason: d.reason,
        }),
      )}
      error={serverError}
      submitting={mut.isPending}
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Field label="開始日" error={errors.start_date?.message}>
          <input type="date" {...register("start_date")} className={inputCls} />
        </Field>
        <Field label="終了日" error={errors.end_date?.message}>
          <input type="date" {...register("end_date")} className={inputCls} />
        </Field>
        <Field label="種別" error={errors.leave_kind?.message}>
          <select {...register("leave_kind")} className={inputCls}>
            <option value="full_day">全日</option>
            <option value="half_day_am">半休（午前）</option>
            <option value="half_day_pm">半休（午後）</option>
          </select>
        </Field>
      </div>
      <Field label="理由" error={errors.reason?.message}>
        <textarea rows={3} {...register("reason")} className={textareaCls} />
      </Field>
    </FormShell>
  );
}

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------
function RequestTable({ rows }: { rows: RequestOut[] }) {
  const qc = useQueryClient();
  const cancel = useMutation({
    mutationFn: (id: string) => apiCancelRequest(id),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: ["requests", "own"] }),
  });

  return (
    <div className="overflow-hidden rounded-lg border border-divider">
      <table className="w-full text-[13px]">
        <thead className="bg-surface-alt text-[11.5px] uppercase tracking-wide text-text-secondary">
          <tr>
            <th className="px-4 py-2 text-left">種別</th>
            <th className="px-4 py-2 text-left">対象日</th>
            <th className="px-4 py-2 text-left">状態</th>
            <th className="px-4 py-2 text-left">提出日時</th>
            <th className="px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const st = REQUEST_STATUS_LABEL[r.status];
            const canCancel = r.status === "pending";
            return (
              <tr key={r.id} className="border-t border-divider align-top">
                <td className="px-4 py-3">
                  <div className="font-bold text-text-primary">
                    {REQUEST_TYPE_LABEL[r.type]}
                  </div>
                  {r.requester_comment && (
                    <div className="mt-0.5 line-clamp-1 text-[11.5px] text-text-tertiary">
                      {r.requester_comment}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 tabular text-text-secondary">
                  {r.target_date ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      "inline-flex rounded-full px-2 py-0.5 text-[11px] font-bold",
                      st.cls,
                    )}
                  >
                    {st.label}
                  </span>
                </td>
                <td className="px-4 py-3 tabular text-[12px] text-text-tertiary">
                  {new Date(r.submitted_at).toLocaleString("ja-JP")}
                </td>
                <td className="px-4 py-3 text-right">
                  {canCancel && (
                    <button
                      type="button"
                      disabled={cancel.isPending}
                      onClick={() => cancel.mutate(r.id)}
                      className="text-[12px] font-bold text-status-red hover:underline disabled:text-text-tertiary"
                    >
                      取消
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Field primitives
// ---------------------------------------------------------------------------
const inputCls =
  "h-10 w-full rounded-lg border border-border-default bg-surface px-3 text-[13px] outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100";
const textareaCls =
  "w-full rounded-lg border border-border-default bg-surface px-3 py-2 text-[13px] outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100";

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[12px] font-bold text-text-secondary">
        {label}
      </span>
      {children}
      {error && (
        <span className="mt-1 block text-[11.5px] font-medium text-status-red">
          {error}
        </span>
      )}
    </label>
  );
}
