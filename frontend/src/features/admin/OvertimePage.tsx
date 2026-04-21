import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import {
  apiAdminMonthlyOvertime,
  type OvertimeReport,
  type OvertimeRowOut,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function formatMinutes(total: number): string {
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export default function OvertimePage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const q = useQuery<OvertimeReport>({
    queryKey: ["admin", "overtime", year, month],
    queryFn: () => apiAdminMonthlyOvertime(year, month),
  });

  return (
    <>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <div className="mb-1 text-[12px] text-text-tertiary">
            ホーム / 管理 / 残業レポート
          </div>
          <h1 className="text-[22px] font-bold text-text-primary">
            月次残業レポート
          </h1>
          <p className="mt-1 text-[13px] text-text-secondary">
            36 協定の目安閾値（45h / 80h / 100h）に対する進捗を一覧表示します。
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

      <section className="rounded-xl bg-surface p-5 shadow-card">
        {q.isLoading && (
          <div className="py-6 text-center text-[13px] text-text-tertiary">
            読み込み中…
          </div>
        )}
        {q.data && q.data.rows.length === 0 && (
          <div className="py-6 text-center text-[13px] text-text-tertiary">
            対象月のデータがありません。
          </div>
        )}
        {q.data && q.data.rows.length > 0 && (
          <OvertimeTable
            report={q.data}
            thresholds={q.data.thresholds_minutes}
          />
        )}
      </section>
    </>
  );
}

function OvertimeTable({
  report,
  thresholds,
}: {
  report: OvertimeReport;
  thresholds: number[];
}) {
  const maxThreshold = thresholds[thresholds.length - 1] ?? 45 * 60;
  return (
    <div className="overflow-hidden rounded-lg border border-divider">
      <table className="w-full text-[13px]">
        <thead className="bg-surface-alt text-[11.5px] uppercase tracking-wide text-text-secondary">
          <tr>
            <th className="px-4 py-2 text-left">社員</th>
            <th className="px-4 py-2 text-left">勤務日数</th>
            <th className="px-4 py-2 text-left">総労働</th>
            <th className="px-4 py-2 text-left">残業</th>
            <th className="px-4 py-2 text-left">進捗</th>
            <th className="px-4 py-2 text-left">通知履歴</th>
          </tr>
        </thead>
        <tbody>
          {report.rows.map((row) => (
            <OvertimeRow key={row.employee_id} row={row} thresholds={thresholds} maxThreshold={maxThreshold} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OvertimeRow({
  row,
  thresholds,
  maxThreshold,
}: {
  row: OvertimeRowOut;
  thresholds: number[];
  maxThreshold: number;
}) {
  const pct = Math.min(100, (row.total_overtime_minutes / maxThreshold) * 100);
  const level =
    row.total_overtime_minutes >= (thresholds[2] ?? 100 * 60)
      ? "red"
      : row.total_overtime_minutes >= (thresholds[1] ?? 80 * 60)
        ? "amber-strong"
        : row.total_overtime_minutes >= (thresholds[0] ?? 45 * 60)
          ? "amber"
          : "green";

  const barCls = {
    green: "bg-status-green",
    amber: "bg-status-amber",
    "amber-strong": "bg-status-amber",
    red: "bg-status-red",
  }[level];

  return (
    <tr className="border-t border-divider align-middle">
      <td className="px-4 py-3">
        <div className="font-bold text-text-primary">{row.employee_name}</div>
        <div className="text-[11.5px] text-text-tertiary">{row.employee_email}</div>
      </td>
      <td className="px-4 py-3 tabular">{row.working_days} 日</td>
      <td className="px-4 py-3 tabular">{formatMinutes(row.total_worked_minutes)}</td>
      <td className="px-4 py-3 tabular">
        <span
          className={cn(
            "font-bold",
            level === "red" && "text-status-red",
            (level === "amber" || level === "amber-strong") && "text-status-amber",
            level === "green" && "text-text-primary",
          )}
        >
          {formatMinutes(row.total_overtime_minutes)}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="relative h-2 w-40 overflow-hidden rounded-full bg-divider">
          <div
            className={cn("h-full", barCls)}
            style={{ width: `${pct}%` }}
          />
          {thresholds.map((t) => (
            <div
              key={t}
              className="absolute top-0 h-full w-px bg-text-tertiary/60"
              style={{ left: `${Math.min(100, (t / maxThreshold) * 100)}%` }}
              title={`${t / 60}h`}
            />
          ))}
        </div>
        <div className="mt-1 flex justify-between text-[10px] text-text-tertiary">
          {thresholds.map((t) => (
            <span key={t}>{t / 60}h</span>
          ))}
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {thresholds.map((t) => {
            const sent = row.alerts_sent.includes(t);
            return (
              <span
                key={t}
                className={cn(
                  "inline-flex items-center rounded-full px-2 py-0.5 text-[10.5px] font-bold",
                  sent
                    ? "bg-status-red-bg text-status-red"
                    : "bg-surface-alt text-text-tertiary",
                )}
                title={sent ? "通知済" : "未通知"}
              >
                {t / 60}h{sent ? "✓" : ""}
              </span>
            );
          })}
        </div>
      </td>
    </tr>
  );
}
