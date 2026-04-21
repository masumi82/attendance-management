import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { AxiosError } from "axios";
import { useState } from "react";

import {
  apiCreateEmployee,
  apiListDepartments,
  apiListEmployees,
  apiUpdateEmployee,
  type DepartmentOut,
  type EmployeeOut,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const ROLE_LABEL: Record<EmployeeOut["role"], string> = {
  admin: "管理者",
  approver: "承認者",
  member: "一般社員",
};

export default function EmployeesPage() {
  const qc = useQueryClient();
  const q = useQuery<EmployeeOut[]>({
    queryKey: ["employees"],
    queryFn: () => apiListEmployees(),
  });
  const deptQ = useQuery<DepartmentOut[]>({
    queryKey: ["departments"],
    queryFn: apiListDepartments,
  });

  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<EmployeeOut | null>(null);

  const toggleActive = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      apiUpdateEmployee(id, { active }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["employees"] }),
  });

  return (
    <>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="mb-1 text-[12px] text-text-tertiary">
            ホーム / 管理 / 社員
          </div>
          <h1 className="text-[22px] font-bold text-text-primary">社員マスタ</h1>
          <p className="mt-1 text-[13px] text-text-secondary">
            社員の登録・役割変更・無効化を行います。
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="inline-flex h-9 items-center rounded-lg bg-brand-500 px-4 text-[12.5px] font-bold text-white shadow-[0_2px_0_hsl(var(--brand-700))] hover:bg-brand-600"
        >
          + 新規社員
        </button>
      </div>

      <section className="rounded-xl bg-surface p-5 shadow-card">
        {q.isLoading && (
          <div className="py-6 text-center text-[13px] text-text-tertiary">
            読み込み中…
          </div>
        )}
        {q.data && q.data.length === 0 && (
          <div className="py-6 text-center text-[13px] text-text-tertiary">
            社員は登録されていません。
          </div>
        )}
        {q.data && q.data.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-divider">
            <table className="w-full text-[13px]">
              <thead className="bg-surface-alt text-[11.5px] uppercase tracking-wide text-text-secondary">
                <tr>
                  <th className="px-4 py-2 text-left">氏名</th>
                  <th className="px-4 py-2 text-left">メール</th>
                  <th className="px-4 py-2 text-left">役割</th>
                  <th className="px-4 py-2 text-left">部署</th>
                  <th className="px-4 py-2 text-left">入社日</th>
                  <th className="px-4 py-2 text-left">状態</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {q.data.map((emp) => {
                  const dept = deptQ.data?.find(
                    (d) => d.id === emp.department_id,
                  );
                  return (
                    <tr key={emp.id} className="border-t border-divider">
                      <td className="px-4 py-3 font-bold text-text-primary">
                        {emp.name}
                      </td>
                      <td className="px-4 py-3 text-text-secondary">
                        {emp.email}
                      </td>
                      <td className="px-4 py-3">
                        <RoleBadge role={emp.role} />
                      </td>
                      <td className="px-4 py-3 text-text-tertiary">
                        {dept?.name ?? "—"}
                      </td>
                      <td className="px-4 py-3 tabular text-text-tertiary">
                        {emp.hire_date ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        {emp.active ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-status-green-bg px-2 py-0.5 text-[11px] font-bold text-status-green">
                            有効
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-surface-alt px-2 py-0.5 text-[11px] font-bold text-text-tertiary ring-1 ring-inset ring-border-default">
                            無効
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-3">
                          <button
                            type="button"
                            onClick={() => setEditing(emp)}
                            className="text-[12px] font-bold text-brand-600 hover:underline"
                          >
                            編集
                          </button>
                          <button
                            type="button"
                            disabled={toggleActive.isPending}
                            onClick={() =>
                              toggleActive.mutate({
                                id: emp.id,
                                active: !emp.active,
                              })
                            }
                            className={cn(
                              "text-[12px] font-bold hover:underline disabled:text-text-tertiary",
                              emp.active ? "text-status-red" : "text-status-green",
                            )}
                          >
                            {emp.active ? "無効化" : "有効化"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {showCreate && (
        <CreateEmployeeDialog
          departments={deptQ.data ?? []}
          onClose={() => setShowCreate(false)}
          onSuccess={() => {
            setShowCreate(false);
            void qc.invalidateQueries({ queryKey: ["employees"] });
          }}
        />
      )}

      {editing && (
        <EditEmployeeDialog
          employee={editing}
          departments={deptQ.data ?? []}
          onClose={() => setEditing(null)}
          onSuccess={() => {
            setEditing(null);
            void qc.invalidateQueries({ queryKey: ["employees"] });
          }}
        />
      )}
    </>
  );
}

function RoleBadge({ role }: { role: EmployeeOut["role"] }) {
  const cls =
    role === "admin"
      ? "bg-brand-100 text-brand-600"
      : role === "approver"
        ? "bg-status-amber-bg text-status-amber"
        : "bg-surface-alt text-text-secondary ring-1 ring-inset ring-border-default";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-bold",
        cls,
      )}
    >
      {ROLE_LABEL[role]}
    </span>
  );
}

function CreateEmployeeDialog({
  departments,
  onClose,
  onSuccess,
}: {
  departments: DepartmentOut[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<EmployeeOut["role"]>("member");
  const [departmentId, setDepartmentId] = useState<string>("");
  const [hireDate, setHireDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("初期パスワードは 8 文字以上にしてください");
      return;
    }
    setSubmitting(true);
    try {
      await apiCreateEmployee({
        email: email.trim(),
        name: name.trim(),
        password,
        role,
        department_id: departmentId || null,
        hire_date: hireDate || null,
      });
      onSuccess();
    } catch (err) {
      if (err instanceof AxiosError && err.response?.status === 409) {
        setError("このメールアドレスは既に登録されています");
      } else {
        setError("登録に失敗しました");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal onClose={submitting ? undefined : onClose}>
      <h2 className="mb-1 text-[16px] font-bold text-text-primary">新規社員登録</h2>
      <p className="mb-4 text-[12px] text-text-tertiary">
        初期パスワードは本人に伝えてください。初回ログイン後に変更してもらうのが推奨です。
      </p>
      <form onSubmit={submit} className="space-y-3">
        <FieldText label="氏名" value={name} onChange={setName} required autoFocus />
        <FieldText
          label="メールアドレス"
          type="email"
          value={email}
          onChange={setEmail}
          required
        />
        <FieldText
          label="初期パスワード（8 文字以上）"
          type="text"
          value={password}
          onChange={setPassword}
          required
        />
        <FieldSelect
          label="役割"
          value={role}
          onChange={(v) => setRole(v as EmployeeOut["role"])}
          options={[
            { value: "member", label: "一般社員" },
            { value: "approver", label: "承認者" },
            { value: "admin", label: "管理者" },
          ]}
        />
        <FieldSelect
          label="部署"
          value={departmentId}
          onChange={setDepartmentId}
          options={[
            { value: "", label: "— 未設定 —" },
            ...departments.map((d) => ({ value: d.id, label: d.name })),
          ]}
        />
        <FieldText label="入社日" type="date" value={hireDate} onChange={setHireDate} />

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
            {submitting ? "登録中…" : "登録"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function EditEmployeeDialog({
  employee,
  departments,
  onClose,
  onSuccess,
}: {
  employee: EmployeeOut;
  departments: DepartmentOut[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [name, setName] = useState(employee.name);
  const [role, setRole] = useState<EmployeeOut["role"]>(employee.role);
  const [departmentId, setDepartmentId] = useState<string>(
    employee.department_id ?? "",
  );
  const [hireDate, setHireDate] = useState(employee.hire_date ?? "");
  const [resetPassword, setResetPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (resetPassword && resetPassword.length < 8) {
      setError("新しいパスワードは 8 文字以上にしてください");
      return;
    }
    setSubmitting(true);
    try {
      await apiUpdateEmployee(employee.id, {
        name,
        role,
        department_id: departmentId || null,
        hire_date: hireDate || null,
        ...(resetPassword ? { password: resetPassword } : {}),
      });
      onSuccess();
    } catch {
      setError("更新に失敗しました");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal onClose={submitting ? undefined : onClose}>
      <h2 className="mb-1 text-[16px] font-bold text-text-primary">社員情報を編集</h2>
      <p className="mb-4 text-[12px] text-text-tertiary">{employee.email}</p>
      <form onSubmit={submit} className="space-y-3">
        <FieldText label="氏名" value={name} onChange={setName} required />
        <FieldSelect
          label="役割"
          value={role}
          onChange={(v) => setRole(v as EmployeeOut["role"])}
          options={[
            { value: "member", label: "一般社員" },
            { value: "approver", label: "承認者" },
            { value: "admin", label: "管理者" },
          ]}
        />
        <FieldSelect
          label="部署"
          value={departmentId}
          onChange={setDepartmentId}
          options={[
            { value: "", label: "— 未設定 —" },
            ...departments.map((d) => ({ value: d.id, label: d.name })),
          ]}
        />
        <FieldText label="入社日" type="date" value={hireDate} onChange={setHireDate} />
        <FieldText
          label="パスワードをリセット（任意・8 文字以上）"
          type="text"
          value={resetPassword}
          onChange={setResetPassword}
        />

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
            {submitting ? "保存中…" : "保存"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// --- UI primitives ---
function Modal({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose?: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
    >
      <div className="w-full max-w-md rounded-2xl bg-surface p-6 shadow-card-hover">
        {children}
      </div>
    </div>
  );
}

function FieldText({
  label,
  value,
  onChange,
  type = "text",
  required,
  autoFocus,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  required?: boolean;
  autoFocus?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-[12px] font-bold text-text-secondary">
        {label}
      </span>
      <input
        type={type}
        required={required}
        autoFocus={autoFocus}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 w-full rounded-lg border border-border-default bg-surface px-3 text-[13px] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
      />
    </label>
  );
}

function FieldSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-[12px] font-bold text-text-secondary">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 w-full rounded-lg border border-border-default bg-surface px-3 text-[13px] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
