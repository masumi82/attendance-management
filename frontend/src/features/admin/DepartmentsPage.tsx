import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { AxiosError } from "axios";
import { useState } from "react";

import {
  apiCreateDepartment,
  apiDeleteDepartment,
  apiListDepartments,
  type DepartmentOut,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export default function DepartmentsPage() {
  const qc = useQueryClient();
  const q = useQuery<DepartmentOut[]>({
    queryKey: ["departments"],
    queryFn: apiListDepartments,
  });

  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const add = useMutation({
    mutationFn: () => apiCreateDepartment(name.trim(), code.trim() || null),
    onSuccess: () => {
      setName("");
      setCode("");
      setError(null);
      void qc.invalidateQueries({ queryKey: ["departments"] });
    },
    onError: (err) => {
      setError(
        err instanceof AxiosError && err.response?.status === 409
          ? "名前またはコードが重複しています。"
          : "登録に失敗しました。",
      );
    },
  });

  const del = useMutation({
    mutationFn: (id: string) => apiDeleteDepartment(id),
    onSuccess: () =>
      void qc.invalidateQueries({ queryKey: ["departments"] }),
  });

  return (
    <>
      <div className="mb-6">
        <div className="mb-1 text-[12px] text-text-tertiary">ホーム / 管理 / 部署</div>
        <h1 className="text-[22px] font-bold text-text-primary">部署マスタ</h1>
        <p className="mt-1 text-[13px] text-text-secondary">
          部署の追加・削除を行います。
        </p>
      </div>

      <section className="mb-5 rounded-xl bg-surface p-5 shadow-card">
        <h2 className="mb-3 text-[14px] font-bold text-text-primary">新規追加</h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="mb-1 block text-[11.5px] font-bold text-text-secondary">
              名前
            </span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例: 開発部"
              className="h-9 w-56 rounded-lg border border-border-default bg-surface px-3 text-[13px]"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-[11.5px] font-bold text-text-secondary">
              コード
            </span>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="DEV"
              className="h-9 w-40 rounded-lg border border-border-default bg-surface px-3 text-[13px]"
            />
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
            部署は登録されていません。
          </div>
        )}
        {q.data && q.data.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-divider">
            <table className="w-full text-[13px]">
              <thead className="bg-surface-alt text-[11.5px] uppercase tracking-wide text-text-secondary">
                <tr>
                  <th className="px-4 py-2 text-left">コード</th>
                  <th className="px-4 py-2 text-left">名前</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {q.data.map((d) => (
                  <tr key={d.id} className="border-t border-divider">
                    <td className="px-4 py-3 tabular text-text-tertiary">
                      {d.code ?? "—"}
                    </td>
                    <td className="px-4 py-3 font-bold text-text-primary">
                      {d.name}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        disabled={del.isPending}
                        onClick={() => del.mutate(d.id)}
                        className="text-[12px] font-bold text-status-red hover:underline disabled:text-text-tertiary"
                      >
                        削除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
