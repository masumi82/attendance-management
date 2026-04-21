import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useState } from "react";

import {
  apiClosingClose,
  apiClosingRecompute,
  apiClosingReopen,
  apiClosingStatus,
  downloadCsv,
  leavesCsvPath,
  monthlyCsvPath,
  type ClosingStatusReport,
  type ClosingStatusRow,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function formatMinutes(total: number): string {
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export default function ClosingPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const qc = useQueryClient();

  const q = useQuery<ClosingStatusReport>({
    queryKey: ["closings", year, month],
    queryFn: () => apiClosingStatus(year, month),
  });

  const recomputeAll = useMutation({
    mutationFn: () => apiClosingRecompute(year, month),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: ["closings", year, month] }),
  });

  const closeAll = useMutation({
    mutationFn: () => apiClosingClose(year, month),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: ["closings", year, month] }),
  });

  const closeOne = useMutation({
    mutationFn: (employeeId: string) =>
      apiClosingClose(year, month, employeeId),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: ["closings", year, month] }),
  });

  const reopenOne = useMutation({
    mutationFn: (employeeId: string) =>
      apiClosingReopen(year, month, employeeId),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: ["closings", year, month] }),
  });

  const ymLabel = `${year}年${month}月`;

  return (
    <>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="mb-1 text-[12px] text-text-tertiary">
            ホーム / 管理 / 月次締め
          </div>
          <h1 className="text-[22px] font-bold text-text-primary">月次締め</h1>
          <p className="mt-1 text-[13px] text-text-secondary">
            {ymLabel}の勤怠集計を確定し、CSV を出力できます。
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
          <select
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
            className="h-9 rounded-lg border border-border-default bg-surface px-3 text-[13px]"
          >
            {Array.from({ length: 12 }).map((_, i) => (
              <option key={i + 1} value={i + 1}>
                {i + 1}月
              </option>
            ))}
          </select>
        </div>
      </div>

      <section className="mb-5 flex flex-wrap gap-3 rounded-xl bg-surface p-4 shadow-card">
        <button
          type="button"
          disabled={recomputeAll.isPending}
          onClick={() => recomputeAll.mutate()}
          className={cn(
            "inline-flex h-9 items-center rounded-lg border border-brand-500 bg-surface px-4 text-[12.5px] font-bold text-brand-600 hover:bg-brand-50",
            "disabled:cursor-not-allowed disabled:border-divider disabled:text-text-tertiary",
          )}
        >
          {recomputeAll.isPending ? "再計算中…" : `${ymLabel} を再計算`}
        </button>
        <button
          type="button"
          disabled={closeAll.isPending}
          onClick={() => {
            if (confirm(`${ymLabel} を全社員ぶん締めますか？`)) {
              closeAll.mutate();
            }
          }}
          className={cn(
            "inline-flex h-9 items-center rounded-lg bg-brand-500 px-4 text-[12.5px] font-bold text-white shadow-[0_2px_0_hsl(var(--brand-700))] hover:bg-brand-600",
            "disabled:cursor-not-allowed disabled:bg-brand-100 disabled:text-brand-600 disabled:shadow-none",
          )}
        >
          {closeAll.isPending ? "締め中…" : `${ymLabel} を一斉締め`}
        </button>

        <div className="flex-1" />

        <button
          type="button"
          onClick={() =>
            downloadCsv(
              monthlyCsvPath(year, month),
              `attendance_${year}-${String(month).padStart(2, "0")}.csv`,
            )
          }
          className="inline-flex h-9 items-center rounded-lg border border-border-default bg-surface px-4 text-[12.5px] font-bold text-text-primary hover:border-brand-500 hover:text-brand-600"
        >
          勤怠 CSV をダウンロード
        </button>
        <button
          type="button"
          onClick={() =>
            downloadCsv(leavesCsvPath(year), `leaves_${year}.csv`)
          }
          className="inline-flex h-9 items-center rounded-lg border border-border-default bg-surface px-4 text-[12.5px] font-bold text-text-primary hover:border-brand-500 hover:text-brand-600"
        >
          休暇残 CSV ({year}年)
        </button>
      </section>

      <section className="rounded-xl bg-surface p-5 shadow-card">
        {q.isLoading && (
          <div className="py-6 text-center text-[13px] text-text-tertiary">
            読み込み中…
          </div>
        )}
        {q.data && <StatusTable
          rows={q.data.rows}
          busy={closeOne.isPending || reopenOne.isPending}
          onClose={(id) => closeOne.mutate(id)}
          onReopen={(id) => reopenOne.mutate(id)}
        />}
      </section>
    </>
  );
}

function StatusTable({
  rows,
  busy,
  onClose,
  onReopen,
}: {
  rows: ClosingStatusRow[];
  busy: boolean;
  onClose: (id: string) => void;
  onReopen: (id: string) => void;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-divider">
      <table className="w-full text-[13px]">
        <thead className="bg-surface-alt text-[11.5px] uppercase tracking-wide text-text-secondary">
          <tr>
            <th className="px-4 py-2 text-left">社員</th>
            <th className="px-4 py-2 text-right">勤務日数</th>
            <th className="px-4 py-2 text-right">総労働</th>
            <th className="px-4 py-2 text-right">残業</th>
            <th className="px-4 py-2 text-left">状態</th>
            <th className="px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.employee_id} className="border-t border-divider">
              <td className="px-4 py-3">
                <div className="font-bold text-text-primary">
                  {r.employee_name}
                </div>
                <div className="text-[11.5px] text-text-tertiary">
                  {r.employee_email}
                </div>
              </td>
              <td className="px-4 py-3 text-right tabular">
                {r.working_days}
              </td>
              <td className="px-4 py-3 text-right tabular">
                {formatMinutes(r.total_worked_minutes)}
              </td>
              <td className="px-4 py-3 text-right tabular">
                {formatMinutes(r.total_overtime_minutes)}
              </td>
              <td className="px-4 py-3">
                {r.closed ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-status-green-bg px-2 py-0.5 text-[11px] font-bold text-status-green">
                    締め済
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-surface-alt px-2 py-0.5 text-[11px] font-bold text-text-tertiary ring-1 ring-inset ring-border-default">
                    未締め
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-right">
                {r.closed ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onReopen(r.employee_id)}
                    className="text-[12px] font-bold text-status-amber hover:underline disabled:text-text-tertiary"
                  >
                    再オープン
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onClose(r.employee_id)}
                    className="text-[12px] font-bold text-brand-600 hover:underline disabled:text-text-tertiary"
                  >
                    締める
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
