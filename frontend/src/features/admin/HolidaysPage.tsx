import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { AxiosError } from "axios";
import { useState } from "react";

import {
  apiCreateHoliday,
  apiDeleteHoliday,
  apiListHolidays,
  type HolidayOut,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const JP_WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"];

export default function HolidaysPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const qc = useQueryClient();

  const q = useQuery<HolidayOut[]>({
    queryKey: ["holidays", year],
    queryFn: () => apiListHolidays(year),
  });

  const [date, setDate] = useState(`${year}-01-01`);
  const [name, setName] = useState("");
  const [type, setType] = useState<"national" | "company">("national");
  const [error, setError] = useState<string | null>(null);

  const add = useMutation({
    mutationFn: () => apiCreateHoliday(date, name.trim(), type),
    onSuccess: () => {
      setName("");
      setError(null);
      void qc.invalidateQueries({ queryKey: ["holidays"] });
    },
    onError: (err) => {
      setError(
        err instanceof AxiosError && err.response?.status === 409
          ? "同じ日付は既に登録されています。"
          : "登録に失敗しました。",
      );
    },
  });

  const del = useMutation({
    mutationFn: (id: string) => apiDeleteHoliday(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["holidays"] }),
  });

  return (
    <>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <div className="mb-1 text-[12px] text-text-tertiary">
            ホーム / 管理 / 祝日
          </div>
          <h1 className="text-[22px] font-bold text-text-primary">祝日マスタ</h1>
          <p className="mt-1 text-[13px] text-text-secondary">
            国民の祝日・会社休日を登録します。
          </p>
        </div>
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

      <section className="mb-5 rounded-xl bg-surface p-5 shadow-card">
        <h2 className="mb-3 text-[14px] font-bold text-text-primary">追加</h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="mb-1 block text-[11.5px] font-bold text-text-secondary">
              日付
            </span>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="h-9 rounded-lg border border-border-default bg-surface px-3 text-[13px]"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-[11.5px] font-bold text-text-secondary">
              名前
            </span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例: 憲法記念日"
              className="h-9 w-56 rounded-lg border border-border-default bg-surface px-3 text-[13px]"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-[11.5px] font-bold text-text-secondary">
              種別
            </span>
            <select
              value={type}
              onChange={(e) =>
                setType(e.target.value as "national" | "company")
              }
              className="h-9 rounded-lg border border-border-default bg-surface px-3 text-[13px]"
            >
              <option value="national">国民の祝日</option>
              <option value="company">会社休日</option>
            </select>
          </label>
          <button
            type="button"
            disabled={!name || add.isPending}
            onClick={() => add.mutate()}
            className={cn(
              "inline-flex h-9 items-center rounded-lg bg-brand-500 px-4 text-[12.5px] font-bold text-white shadow-[0_2px_0_hsl(var(--brand-700))] hover:bg-brand-600",
              "disabled:cursor-not-allowed disabled:bg-brand-100 disabled:text-brand-600 disabled:shadow-none",
            )}
          >
            追加
          </button>
          {error && (
            <div className="w-full text-[12px] font-medium text-status-red">
              {error}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-xl bg-surface p-5 shadow-card">
        {q.data && q.data.length === 0 && (
          <div className="py-6 text-center text-[13px] text-text-tertiary">
            {year} 年の祝日は登録されていません。
          </div>
        )}
        {q.data && q.data.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-divider">
            <table className="w-full text-[13px]">
              <thead className="bg-surface-alt text-[11.5px] uppercase tracking-wide text-text-secondary">
                <tr>
                  <th className="px-4 py-2 text-left">日付</th>
                  <th className="px-4 py-2 text-left">名前</th>
                  <th className="px-4 py-2 text-left">種別</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {q.data.map((h) => {
                  const d = new Date(h.date + "T00:00:00");
                  return (
                    <tr key={h.id} className="border-t border-divider">
                      <td className="px-4 py-3 tabular">
                        {h.date}{" "}
                        <span className="text-text-tertiary">
                          ({JP_WEEKDAYS[d.getDay()]})
                        </span>
                      </td>
                      <td className="px-4 py-3 font-bold text-text-primary">
                        {h.name}
                      </td>
                      <td className="px-4 py-3 text-text-secondary">
                        {h.type === "national" ? "国民の祝日" : "会社休日"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          disabled={del.isPending}
                          onClick={() => del.mutate(h.id)}
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
        )}
      </section>
    </>
  );
}
