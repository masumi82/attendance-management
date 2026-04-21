import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import {
  apiFlexSettlement,
  apiMonthlyShifts,
  type FlexSettlementOut,
  type ShiftMonthlyResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function formatMinutes(total: number): string {
  const sign = total < 0 ? "-" : "";
  const abs = Math.abs(total);
  const h = Math.floor(abs / 60);
  const m = abs % 60;
  return `${sign}${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

const JP_WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"];

export default function MyShiftsPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const shiftsQ = useQuery<ShiftMonthlyResponse>({
    queryKey: ["shifts", "my", year, month],
    queryFn: () => apiMonthlyShifts(year, month),
  });

  const flexQ = useQuery<FlexSettlementOut>({
    queryKey: ["shifts", "flex", year, month],
    queryFn: () => apiFlexSettlement(year, month),
  });

  const isFlex = flexQ.data?.employment_type_code === "flex";

  return (
    <>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <div className="mb-1 text-[12px] text-text-tertiary">
            ホーム / 勤怠表
          </div>
          <h1 className="text-[22px] font-bold text-text-primary">勤怠表</h1>
          <p className="mt-1 text-[13px] text-text-secondary">
            シフトと当月の勤務状況を確認します。
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

      {flexQ.data && (
        <section
          className={cn(
            "mb-5 rounded-xl p-5 shadow-card",
            isFlex
              ? "bg-gradient-to-br from-brand-50 to-surface"
              : "bg-surface",
          )}
        >
          <div className="mb-2 text-[12px] font-bold uppercase tracking-wide text-text-tertiary">
            {flexQ.data.employment_type_code ?? "勤務形態未設定"} ·{" "}
            {flexQ.data.year}年{flexQ.data.month}月清算
          </div>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <MetricTile
              label="所定労働"
              value={formatMinutes(flexQ.data.required_minutes)}
            />
            <MetricTile
              label="実労働"
              value={formatMinutes(flexQ.data.worked_minutes)}
            />
            <MetricTile
              label="過不足"
              value={formatMinutes(flexQ.data.surplus_minutes)}
              tone={
                flexQ.data.surplus_minutes >= 0
                  ? "positive"
                  : "negative"
              }
            />
            <MetricTile
              label="勤務日数"
              value={`${flexQ.data.working_days} 日`}
            />
          </div>
          {isFlex && flexQ.data.core_start && flexQ.data.core_end && (
            <div className="mt-4 flex flex-col gap-1 border-t border-divider pt-3 text-[12.5px]">
              <div className="text-text-secondary">
                コアタイム:{" "}
                <span className="font-bold text-text-primary">
                  {flexQ.data.core_start.slice(0, 5)} –{" "}
                  {flexQ.data.core_end.slice(0, 5)}
                </span>
              </div>
              {flexQ.data.core_violation_dates.length > 0 ? (
                <div className="text-status-red">
                  <span className="font-bold">
                    違反日 ({flexQ.data.core_violation_dates.length})
                  </span>
                  : {flexQ.data.core_violation_dates.join(", ")}
                </div>
              ) : (
                <div className="text-status-green">コアタイム違反はありません</div>
              )}
            </div>
          )}
        </section>
      )}

      <section className="rounded-xl bg-surface p-5 shadow-card">
        <h2 className="mb-4 text-[14px] font-bold text-text-primary">
          今月のシフト
        </h2>
        {shiftsQ.isLoading && (
          <div className="py-6 text-center text-[13px] text-text-tertiary">
            読み込み中…
          </div>
        )}
        {shiftsQ.data && shiftsQ.data.shifts.length === 0 && (
          <div className="py-6 text-center text-[13px] text-text-tertiary">
            シフトは登録されていません。
          </div>
        )}
        {shiftsQ.data && shiftsQ.data.shifts.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-divider">
            <table className="w-full text-[13px]">
              <thead className="bg-surface-alt text-[11.5px] uppercase tracking-wide text-text-secondary">
                <tr>
                  <th className="px-4 py-2 text-left">日付</th>
                  <th className="px-4 py-2 text-left">開始</th>
                  <th className="px-4 py-2 text-left">終了</th>
                  <th className="px-4 py-2 text-left">休憩</th>
                </tr>
              </thead>
              <tbody>
                {shiftsQ.data.shifts.map((s) => {
                  const d = new Date(s.work_date + "T00:00:00");
                  const dow = JP_WEEKDAYS[d.getDay()];
                  return (
                    <tr key={s.id} className="border-t border-divider">
                      <td className="px-4 py-3 tabular">
                        {s.work_date}{" "}
                        <span className="text-text-tertiary">({dow})</span>
                      </td>
                      <td className="px-4 py-3 tabular">
                        {s.start_time.slice(0, 5)}
                      </td>
                      <td className="px-4 py-3 tabular">
                        {s.end_time.slice(0, 5)}
                      </td>
                      <td className="px-4 py-3 tabular">
                        {s.break_minutes} 分
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

function MetricTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "positive" | "negative";
}) {
  return (
    <div className="rounded-lg bg-surface p-3 shadow-[0_1px_0_hsl(var(--divider))]">
      <div className="text-[11.5px] text-text-tertiary">{label}</div>
      <div
        className={cn(
          "mt-1 tabular text-[20px] font-bold",
          tone === "positive" && "text-status-green",
          tone === "negative" && "text-status-red",
          !tone && "text-text-primary",
        )}
      >
        {value}
      </div>
    </div>
  );
}
