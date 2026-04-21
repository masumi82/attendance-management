import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useState } from "react";

import {
  apiAdminCarryoverLeaves,
  apiAdminGrantAllLeaves,
  apiAdminGrantLeave,
  apiAdminLeaveBalances,
  type LeaveBalanceReport,
  type LeaveBalanceSummary,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export default function LeavesPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [grantTarget, setGrantTarget] = useState<LeaveBalanceSummary | null>(null);
  const qc = useQueryClient();

  const q = useQuery<LeaveBalanceReport>({
    queryKey: ["admin", "leaves", year],
    queryFn: () => apiAdminLeaveBalances(year),
  });

  const grantMut = useMutation({
    mutationFn: () => apiAdminGrantAllLeaves(year),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: ["admin", "leaves", year] }),
  });

  const carryMut = useMutation({
    mutationFn: () => apiAdminCarryoverLeaves(year),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: ["admin", "leaves"] }),
  });

  return (
    <>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <div className="mb-1 text-[12px] text-text-tertiary">
            ホーム / 管理 / 休暇残高
          </div>
          <h1 className="text-[22px] font-bold text-text-primary">休暇残高</h1>
          <p className="mt-1 text-[13px] text-text-secondary">
            社員別の年次有給休暇の残日数を確認・付与できます。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="h-9 rounded-lg border border-border-default bg-surface px-3 text-[13px]"
          >
            {Array.from({ length: 5 }).map((_, i) => {
              const y = now.getFullYear() - 2 + i;
              return (
                <option key={y} value={y}>
                  {y}年
                </option>
              );
            })}
          </select>
        </div>
      </div>

      <section className="mb-4 flex flex-wrap items-center gap-3 rounded-xl bg-surface p-4 shadow-card">
        <div className="flex-1 text-[12.5px] text-text-secondary">
          勤続 6 ヶ月以上の社員に、年次有給を勤続年数ベース（最低 10 日、+1/年、上限 20 日）で一斉付与します。
        </div>
        <button
          type="button"
          disabled={grantMut.isPending}
          onClick={() => grantMut.mutate()}
          className={cn(
            "inline-flex h-9 items-center rounded-lg bg-brand-500 px-4 text-[12.5px] font-bold text-white",
            "shadow-[0_2px_0_hsl(var(--brand-700))] hover:bg-brand-600",
            "disabled:cursor-not-allowed disabled:bg-brand-100 disabled:text-brand-600 disabled:shadow-none",
          )}
        >
          {grantMut.isPending ? "付与中…" : `${year} 年の一斉付与`}
        </button>
        <button
          type="button"
          disabled={carryMut.isPending}
          onClick={() => carryMut.mutate()}
          className={cn(
            "inline-flex h-9 items-center rounded-lg border border-brand-500 bg-surface px-4 text-[12.5px] font-bold text-brand-600",
            "hover:bg-brand-50 disabled:cursor-not-allowed disabled:border-divider disabled:text-text-tertiary",
          )}
        >
          {carryMut.isPending ? "繰越中…" : `${year} 年から翌年へ繰越`}
        </button>
      </section>

      {grantMut.isSuccess && (
        <div className="mb-3 rounded-lg bg-status-green-bg px-3 py-2 text-[12.5px] font-medium text-status-green">
          {grantMut.data.granted_for_employees} 名に {grantMut.data.year} 年分を付与しました。
        </div>
      )}
      {carryMut.isSuccess && (
        <div className="mb-3 rounded-lg bg-brand-50 px-3 py-2 text-[12.5px] font-medium text-brand-700">
          {carryMut.data.from_year}→{carryMut.data.to_year} に {carryMut.data.moved} 件繰り越しました。
        </div>
      )}

      <section className="rounded-xl bg-surface p-5 shadow-card">
        {q.isLoading && (
          <div className="py-6 text-center text-[13px] text-text-tertiary">
            読み込み中…
          </div>
        )}
        {q.data && q.data.rows.length === 0 && (
          <div className="py-6 text-center text-[13px] text-text-tertiary">
            対象年のデータがありません。
          </div>
        )}
        {q.data && q.data.rows.length > 0 && (
          <BalanceTable
            rows={q.data.rows}
            onGrant={(row) => setGrantTarget(row)}
          />
        )}
      </section>

      {grantTarget && (
        <GrantOneDialog
          target={grantTarget}
          year={year}
          onClose={() => setGrantTarget(null)}
          onSuccess={() => {
            setGrantTarget(null);
            void qc.invalidateQueries({ queryKey: ["admin", "leaves", year] });
          }}
        />
      )}
    </>
  );
}

function GrantOneDialog({
  target,
  year,
  onClose,
  onSuccess,
}: {
  target: LeaveBalanceSummary;
  year: number;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [days, setDays] = useState<string>(
    Number(target.granted_days).toFixed(1),
  );
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const n = Number(days);
    if (!Number.isFinite(n) || n < 0 || n > 60) {
      setError("0〜60 の数値を入力してください");
      return;
    }
    setSubmitting(true);
    try {
      await apiAdminGrantLeave({
        employee_id: target.employee_id,
        year,
        days: n,
      });
      onSuccess();
    } catch {
      setError("付与に失敗しました");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !submitting) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-2xl bg-surface p-6 shadow-card-hover">
        <h2 className="mb-1 text-[16px] font-bold text-text-primary">個別付与</h2>
        <p className="mb-4 text-[12px] text-text-tertiary">
          {target.employee_name}（{target.employee_email}）の {year} 年分の付与日数を直接設定します。
          <br />
          現在: 付与 {Number(target.granted_days).toFixed(1)} 日 / 残 {Number(target.remaining_days).toFixed(1)} 日
        </p>
        <form onSubmit={submit} className="space-y-3">
          <label className="block">
            <span className="mb-1 block text-[12px] font-bold text-text-secondary">
              付与日数（0.5 刻み）
            </span>
            <input
              type="number"
              min={0}
              max={60}
              step={0.5}
              value={days}
              onChange={(e) => setDays(e.target.value)}
              className="h-10 w-full rounded-lg border border-border-default bg-surface px-3 text-[13px] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              autoFocus
            />
          </label>
          {error && (
            <div className="rounded-lg bg-status-red-bg px-3 py-2 text-[12.5px] text-status-red">
              {error}
            </div>
          )}
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="inline-flex h-10 flex-1 items-center justify-center rounded-lg border border-border-default bg-surface text-[13px] font-bold text-text-primary hover:bg-surface-alt disabled:opacity-50"
            >
              キャンセル
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex h-10 flex-1 items-center justify-center rounded-lg bg-brand-500 text-[13px] font-bold text-white hover:bg-brand-600 disabled:opacity-50"
            >
              {submitting ? "付与中…" : "付与する"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function BalanceTable({
  rows,
  onGrant,
}: {
  rows: LeaveBalanceSummary[];
  onGrant: (row: LeaveBalanceSummary) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-divider">
      <table className="w-full text-[13px]">
        <thead className="bg-surface-alt text-[11.5px] uppercase tracking-wide text-text-secondary">
          <tr>
            <th className="px-4 py-2 text-left">社員</th>
            <th className="px-4 py-2 text-right">付与</th>
            <th className="px-4 py-2 text-right">繰越</th>
            <th className="px-4 py-2 text-right">使用</th>
            <th className="px-4 py-2 text-right">残</th>
            <th className="px-4 py-2 text-left">進捗</th>
            <th className="px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const granted = Number(r.granted_days);
            const carried = Number(r.carried_over_days);
            const used = Number(r.used_days);
            const remaining = Number(r.remaining_days);
            const totalAvail = granted + carried;
            const pct = totalAvail > 0 ? (used / totalAvail) * 100 : 0;
            const tone =
              remaining <= 0
                ? "text-status-red"
                : remaining < 5
                  ? "text-status-amber"
                  : "text-status-green";
            return (
              <tr key={r.employee_id} className="border-t border-divider align-middle">
                <td className="px-4 py-3">
                  <div className="font-bold text-text-primary">{r.employee_name}</div>
                  <div className="text-[11.5px] text-text-tertiary">
                    {r.employee_email}
                  </div>
                </td>
                <td className="px-4 py-3 text-right tabular">{granted}</td>
                <td className="px-4 py-3 text-right tabular text-text-tertiary">
                  {carried}
                </td>
                <td className="px-4 py-3 text-right tabular">{used}</td>
                <td className={cn("px-4 py-3 text-right font-bold tabular", tone)}>
                  {remaining}
                </td>
                <td className="px-4 py-3">
                  <div className="relative h-2 w-40 overflow-hidden rounded-full bg-divider">
                    <div
                      className="h-full bg-brand-500"
                      style={{ width: `${Math.min(100, pct)}%` }}
                    />
                  </div>
                  <div className="mt-1 text-[10.5px] text-text-tertiary">
                    {used.toFixed(1)} / {totalAvail.toFixed(1)} 日
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onGrant(r)}
                    className="text-[12px] font-bold text-brand-600 hover:underline"
                  >
                    個別付与
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
