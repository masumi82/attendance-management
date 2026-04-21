import { zodResolver } from "@hookform/resolvers/zod";
import { AxiosError } from "axios";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { useAuth } from "@/features/auth/useAuth";
import { cn } from "@/lib/utils";

const schema = z.object({
  email: z.string().email("メールアドレスの形式が不正です"),
  password: z.string().min(1, "パスワードを入力してください"),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as { state?: { from?: string } };
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (data: FormValues) => {
    setServerError(null);
    try {
      await login(data.email, data.password);
      nav(loc.state?.from ?? "/", { replace: true });
    } catch (err) {
      if (err instanceof AxiosError && err.response?.status === 401) {
        setServerError("メールアドレスまたはパスワードが正しくありません。");
      } else {
        setServerError("ログインに失敗しました。時間をおいて再度お試しください。");
      }
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-page-bg px-4">
      {/* decorative background */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-0"
        style={{
          background:
            "radial-gradient(1200px 600px at 80% -10%, hsl(var(--brand-100)) 0%, transparent 60%), radial-gradient(800px 400px at 10% 110%, hsl(var(--brand-50)) 0%, transparent 60%)",
        }}
      />
      <div className="relative w-full max-w-[400px]">
        <div className="mb-6 flex items-center justify-center gap-2">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500 text-[16px] font-bold text-white shadow-[0_3px_0_hsl(var(--brand-700))]">
            勤
          </span>
          <span className="text-[17px] font-bold tracking-wide text-text-primary">
            勤怠管理システム
          </span>
        </div>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="rounded-2xl bg-surface p-8 shadow-card"
        >
          <h1 className="text-[18px] font-bold text-text-primary">ログイン</h1>
          <p className="mt-1 text-[12px] text-text-tertiary">
            勤怠管理システムへようこそ
          </p>

          <div className="mt-6 space-y-4">
            <Field
              label="メールアドレス"
              error={errors.email?.message}
              htmlFor="email"
            >
              <input
                id="email"
                type="email"
                autoComplete="email"
                inputMode="email"
                className={cn(
                  "h-10 w-full rounded-lg border bg-surface px-3 text-[14px] outline-none transition",
                  errors.email
                    ? "border-status-red focus:ring-2 focus:ring-status-red/30"
                    : "border-border-default focus:border-brand-500 focus:ring-2 focus:ring-brand-100",
                )}
                placeholder="you@example.com"
                {...register("email")}
              />
            </Field>

            <Field
              label="パスワード"
              error={errors.password?.message}
              htmlFor="password"
            >
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                className={cn(
                  "h-10 w-full rounded-lg border bg-surface px-3 text-[14px] outline-none transition",
                  errors.password
                    ? "border-status-red focus:ring-2 focus:ring-status-red/30"
                    : "border-border-default focus:border-brand-500 focus:ring-2 focus:ring-brand-100",
                )}
                {...register("password")}
              />
            </Field>
          </div>

          {serverError && (
            <div className="mt-4 rounded-lg bg-status-red-bg px-3 py-2 text-[12.5px] font-medium text-status-red">
              {serverError}
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className={cn(
              "mt-6 flex h-11 w-full items-center justify-center rounded-lg bg-brand-500 text-[14px] font-bold text-white transition-all",
              "shadow-[0_3px_0_hsl(var(--brand-700))] hover:bg-brand-600",
              "active:translate-y-[3px] active:shadow-none",
              "disabled:cursor-not-allowed disabled:bg-brand-100 disabled:text-brand-600 disabled:shadow-none",
            )}
          >
            {isSubmitting ? "ログイン中…" : "ログイン"}
          </button>
        </form>

        <p className="mt-6 text-center text-[11px] text-text-tertiary">
          勤怠管理 v0.1.0 · © 2026 Sample Inc.
        </p>
      </div>
    </div>
  );
}

function Field({
  label,
  error,
  htmlFor,
  children,
}: {
  label: string;
  error?: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <label htmlFor={htmlFor} className="block">
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
