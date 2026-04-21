import { useState } from "react";
import { AxiosError } from "axios";

import { apiChangePassword } from "@/lib/api";

type Props = {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
};

export default function ChangePasswordDialog({ open, onClose, onSuccess }: Props) {
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  if (!open) return null;

  function reset() {
    setCurrentPw("");
    setNewPw("");
    setConfirmPw("");
    setError(null);
    setDone(false);
  }

  function close() {
    if (submitting) return;
    reset();
    onClose();
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPw.length < 12) {
      setError("新しいパスワードは 12 文字以上にしてください");
      return;
    }
    if (newPw !== confirmPw) {
      setError("新しいパスワードの確認が一致しません");
      return;
    }
    if (newPw === currentPw) {
      setError("現在のパスワードと同じものは使えません");
      return;
    }

    setSubmitting(true);
    try {
      await apiChangePassword(currentPw, newPw);
      setDone(true);
      onSuccess?.();
    } catch (err) {
      const detail =
        err instanceof AxiosError
          ? (err.response?.data as { detail?: string } | undefined)?.detail
          : undefined;
      if (detail === "invalid_current_password") {
        setError("現在のパスワードが正しくありません");
      } else if (detail === "new_password_same_as_current") {
        setError("現在のパスワードと同じものは使えません");
      } else {
        setError("変更に失敗しました。時間を置いて再試行してください");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="w-full max-w-md rounded-2xl bg-surface p-6 shadow-card-hover">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-[16px] font-bold text-text-primary">
              パスワード変更
            </h2>
            <p className="mt-0.5 text-[12px] text-text-tertiary">
              12 文字以上で新しいパスワードを設定してください
            </p>
          </div>
          <button
            type="button"
            onClick={close}
            className="rounded-md p-1 text-text-tertiary hover:bg-surface-alt hover:text-text-primary"
            aria-label="閉じる"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M5 5l10 10M15 5L5 15" />
            </svg>
          </button>
        </div>

        {done ? (
          <div className="space-y-4">
            <div className="rounded-lg bg-status-green-bg p-3 text-[13px] text-status-green">
              パスワードを変更しました。他の端末のセッションはすべて無効化されました。
            </div>
            <button
              type="button"
              onClick={close}
              className="inline-flex h-10 w-full items-center justify-center rounded-lg bg-brand-500 text-[13px] font-bold text-white hover:bg-brand-600"
            >
              閉じる
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <label className="block">
              <span className="mb-1 block text-[12px] font-bold text-text-secondary">
                現在のパスワード
              </span>
              <input
                type="password"
                autoComplete="current-password"
                required
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                className="h-10 w-full rounded-lg border border-border-default bg-surface px-3 text-[13px] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[12px] font-bold text-text-secondary">
                新しいパスワード
              </span>
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={12}
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                className="h-10 w-full rounded-lg border border-border-default bg-surface px-3 text-[13px] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[12px] font-bold text-text-secondary">
                新しいパスワード（確認）
              </span>
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={12}
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                className="h-10 w-full rounded-lg border border-border-default bg-surface px-3 text-[13px] focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
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
                onClick={close}
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
                {submitting ? "変更中…" : "変更する"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
