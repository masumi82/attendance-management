import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { AxiosError } from "axios";
import { useEffect, useState } from "react";

import {
  apiAssignEmploymentType,
  apiDeleteShift,
  apiListEmployees,
  apiListEmploymentTypes,
  apiMonthlyShifts,
  apiUpsertShift,
  type EmployeeOut,
  type EmploymentTypeOut,
  type ShiftMonthlyResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const JP_WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"];

export default function AdminShiftsPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const employeesQ = useQuery<EmployeeOut[]>({
    queryKey: ["employees"],
    queryFn: () => apiListEmployees(),
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => {
    if (!selectedId && employeesQ.data && employeesQ.data.length > 0) {
      setSelectedId(employeesQ.data[0].id);
    }
  }, [employeesQ.data, selectedId]);

  const typesQ = useQuery<EmploymentTypeOut[]>({
    queryKey: ["employment-types"],
    queryFn: apiListEmploymentTypes,
  });

  const shiftsQ = useQuery<ShiftMonthlyResponse>({
    queryKey: ["shifts", "admin", selectedId, year, month],
    queryFn: () => apiMonthlyShifts(year, month, selectedId ?? undefined),
    enabled: !!selectedId,
  });

  const qc = useQueryClient();
  const assignMut = useMutation({
    mutationFn: (typeId: string | null) =>
      apiAssignEmploymentType(selectedId!, typeId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["employees"] });
    },
  });

  return (
    <>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="mb-1 text-[12px] text-text-tertiary">
            ホーム / 管理 / シフト
          </div>
          <h1 className="text-[22px] font-bold text-text-primary">シフト管理</h1>
          <p className="mt-1 text-[13px] text-text-secondary">
            社員を選択してシフトを登録・編集できます。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedId ?? ""}
            onChange={(e) => setSelectedId(e.target.value || null)}
            className="h-9 rounded-lg border border-border-default bg-surface px-3 text-[13px]"
          >
            {employeesQ.data?.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}（{e.email}）
              </option>
            ))}
          </select>
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

      {selectedId && typesQ.data && (
        <section className="mb-5 flex flex-wrap items-center gap-3 rounded-xl bg-surface p-4 shadow-card">
          <div className="text-[12.5px] font-bold text-text-secondary">
            勤務形態:
          </div>
          {typesQ.data.map((t) => (
            <button
              key={t.id}
              type="button"
              disabled={assignMut.isPending}
              onClick={() => assignMut.mutate(t.id)}
              className={cn(
                "inline-flex h-8 items-center rounded-full px-3 text-[12px] font-bold transition",
                "border border-border-default hover:border-brand-500 hover:text-brand-600",
                "disabled:cursor-not-allowed",
              )}
            >
              {t.name}
              {t.core_start && (
                <span className="ml-1 text-text-tertiary">
                  （{t.core_start.slice(0, 5)}–{t.core_end?.slice(0, 5)}）
                </span>
              )}
            </button>
          ))}
          <button
            type="button"
            disabled={assignMut.isPending}
            onClick={() => assignMut.mutate(null)}
            className="text-[11.5px] text-text-tertiary hover:underline"
          >
            解除
          </button>
        </section>
      )}

      <section className="mb-5 rounded-xl bg-surface p-5 shadow-card">
        <h2 className="mb-3 text-[14px] font-bold text-text-primary">
          シフト追加
        </h2>
        {selectedId && (
          <ShiftAddForm
            employeeId={selectedId}
            onSaved={() =>
              qc.invalidateQueries({ queryKey: ["shifts", "admin"] })
            }
          />
        )}
      </section>

      <section className="rounded-xl bg-surface p-5 shadow-card">
        <h2 className="mb-3 text-[14px] font-bold text-text-primary">
          登録済みシフト
        </h2>
        {shiftsQ.isLoading && (
          <div className="py-6 text-center text-[13px] text-text-tertiary">
            読み込み中…
          </div>
        )}
        {shiftsQ.data && shiftsQ.data.shifts.length === 0 && (
          <div className="py-6 text-center text-[13px] text-text-tertiary">
            登録されたシフトはありません。
          </div>
        )}
        {shiftsQ.data && shiftsQ.data.shifts.length > 0 && (
          <ShiftList
            shifts={shiftsQ.data.shifts}
            onDeleted={() =>
              qc.invalidateQueries({ queryKey: ["shifts", "admin"] })
            }
          />
        )}
      </section>
    </>
  );
}

function ShiftAddForm({
  employeeId,
  onSaved,
}: {
  employeeId: string;
  onSaved: () => void;
}) {
  const today = new Date();
  const [workDate, setWorkDate] = useState(
    `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`,
  );
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("18:00");
  const [breakMinutes, setBreakMinutes] = useState(60);
  const [error, setError] = useState<string | null>(null);

  const mut = useMutation({
    mutationFn: () =>
      apiUpsertShift({
        employee_id: employeeId,
        work_date: workDate,
        start_time: startTime + ":00",
        end_time: endTime + ":00",
        break_minutes: breakMinutes,
      }),
    onSuccess: () => {
      setError(null);
      onSaved();
    },
    onError: (err) => {
      const detail =
        err instanceof AxiosError
          ? (err.response?.data?.detail as string | undefined)
          : undefined;
      setError(
        detail === "end_before_start"
          ? "終了時刻は開始時刻より後にしてください。"
          : "保存に失敗しました。",
      );
    },
  });

  const cls =
    "h-9 rounded-lg border border-border-default bg-surface px-3 text-[13px] focus:border-brand-500 focus:ring-2 focus:ring-brand-100";

  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="block">
        <span className="mb-1 block text-[11.5px] font-bold text-text-secondary">
          日付
        </span>
        <input
          type="date"
          value={workDate}
          onChange={(e) => setWorkDate(e.target.value)}
          className={cls}
        />
      </label>
      <label className="block">
        <span className="mb-1 block text-[11.5px] font-bold text-text-secondary">
          開始
        </span>
        <input
          type="time"
          value={startTime}
          onChange={(e) => setStartTime(e.target.value)}
          className={cls}
        />
      </label>
      <label className="block">
        <span className="mb-1 block text-[11.5px] font-bold text-text-secondary">
          終了
        </span>
        <input
          type="time"
          value={endTime}
          onChange={(e) => setEndTime(e.target.value)}
          className={cls}
        />
      </label>
      <label className="block">
        <span className="mb-1 block text-[11.5px] font-bold text-text-secondary">
          休憩(分)
        </span>
        <input
          type="number"
          min={0}
          max={480}
          value={breakMinutes}
          onChange={(e) => setBreakMinutes(Number(e.target.value))}
          className={cn(cls, "w-24")}
        />
      </label>
      <button
        type="button"
        disabled={mut.isPending}
        onClick={() => mut.mutate()}
        className={cn(
          "inline-flex h-9 items-center rounded-lg bg-brand-500 px-4 text-[12.5px] font-bold text-white",
          "shadow-[0_2px_0_hsl(var(--brand-700))] hover:bg-brand-600",
          "disabled:cursor-not-allowed disabled:bg-brand-100 disabled:text-brand-600 disabled:shadow-none",
        )}
      >
        {mut.isPending ? "保存中…" : "登録 / 更新"}
      </button>
      {error && (
        <div className="w-full text-[12px] font-medium text-status-red">
          {error}
        </div>
      )}
    </div>
  );
}

function ShiftList({
  shifts,
  onDeleted,
}: {
  shifts: ShiftMonthlyResponse["shifts"];
  onDeleted: () => void;
}) {
  const del = useMutation({
    mutationFn: (id: string) => apiDeleteShift(id),
    onSuccess: onDeleted,
  });
  return (
    <div className="overflow-hidden rounded-lg border border-divider">
      <table className="w-full text-[13px]">
        <thead className="bg-surface-alt text-[11.5px] uppercase tracking-wide text-text-secondary">
          <tr>
            <th className="px-4 py-2 text-left">日付</th>
            <th className="px-4 py-2 text-left">時間</th>
            <th className="px-4 py-2 text-left">休憩</th>
            <th className="px-4 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {shifts.map((s) => {
            const d = new Date(s.work_date + "T00:00:00");
            const dow = JP_WEEKDAYS[d.getDay()];
            return (
              <tr key={s.id} className="border-t border-divider">
                <td className="px-4 py-3 tabular">
                  {s.work_date}{" "}
                  <span className="text-text-tertiary">({dow})</span>
                </td>
                <td className="px-4 py-3 tabular">
                  {s.start_time.slice(0, 5)} – {s.end_time.slice(0, 5)}
                </td>
                <td className="px-4 py-3 tabular">{s.break_minutes} 分</td>
                <td className="px-4 py-3 text-right">
                  <button
                    type="button"
                    disabled={del.isPending}
                    onClick={() => del.mutate(s.id)}
                    className="text-[12px] font-bold text-status-red hover:underline disabled:text-text-tertiary"
                  >
                    削除
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
