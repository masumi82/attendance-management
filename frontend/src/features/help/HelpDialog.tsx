import type { Role } from "@/lib/auth-store";

type Props = {
  open: boolean;
  role: Role;
  onClose: () => void;
};

export default function HelpDialog({ open, role, onClose }: Props) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-surface p-6 shadow-card-hover">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-[16px] font-bold text-text-primary">
              使い方ガイド
            </h2>
            <p className="mt-0.5 text-[12px] text-text-tertiary">
              主な機能の操作方法です
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="閉じる"
            className="rounded-md p-1 text-text-tertiary hover:bg-surface-alt hover:text-text-primary"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M5 5l10 10M15 5L5 15" />
            </svg>
          </button>
        </div>

        <Section title="打刻">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              トップ画面（打刻）で
              <Kbd>出勤</Kbd>
              <Kbd>休憩開始</Kbd>
              <Kbd>休憩終了</Kbd>
              <Kbd>退勤</Kbd> を押すと、その時刻で打刻されます。
            </li>
            <li>
              既に出勤済みの状態で再度「出勤」は押せません（重複防止）。
            </li>
            <li>
              月次締めが行われた月に対しては打刻できません（エラー表示されます）。
            </li>
          </ul>
        </Section>

        <Section title="勤怠の確認">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              トップ画面には 今月の勤務日数／総労働／残業／深夜労働 と 今週の日別勤怠が並びます。
            </li>
            <li>
              「勤怠表」ではシフト予定 vs 実績を日次で確認できます。
            </li>
          </ul>
        </Section>

        <Section title="申請の出し方">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              サイドバー「申請」→「新規申請」ボタンから申請を作成します。
            </li>
            <li>
              種別: <strong>打刻修正</strong>・<strong>残業（事前/事後）</strong>・<strong>休暇</strong>
            </li>
            <li>
              申請後は一覧で状態（下書き/承認待ち/承認済み/却下/取り消し）が確認できます。
            </li>
            <li>
              承認待ちの申請は自分で <strong>取り消し</strong> 可能です。
            </li>
          </ul>
        </Section>

        <Section title="有給休暇">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              トップ画面の「有給休暇残」タイルで 残日数／付与／繰越／消化 が見られます。
            </li>
            <li>
              「休暇を申請」から全日・半休を指定して申請できます（残日数不足時はエラー）。
            </li>
          </ul>
        </Section>

        {(role === "approver" || role === "admin") && (
          <Section title="承認者機能">
            <ul className="list-disc space-y-1 pl-5">
              <li>
                サイドバー「承認」で未処理の承認キューが一覧されます。
              </li>
              <li>
                各カードの
                <Kbd>承認</Kbd>
                <Kbd>却下</Kbd>
                で決定します。コメントを付けることができます。
              </li>
              <li>
                <strong>自分が出した申請は自分では承認・却下できません</strong>（別の承認者に依頼してください）。
              </li>
            </ul>
          </Section>
        )}

        {role === "admin" && (
          <Section title="管理者機能">
            <ul className="list-disc space-y-1 pl-5">
              <li>
                <strong>社員</strong>: 新規登録・役割変更・無効化・パスワードリセット
              </li>
              <li>
                <strong>部署・祝日</strong>: マスタの追加・削除
              </li>
              <li>
                <strong>月次締め</strong>: 月を選んで 再計算 →
                全社員一斉締め・個別締め・再オープンが可能。CSV（勤怠・休暇残）もここから出力します。
              </li>
              <li>
                <strong>シフト</strong>: 社員ごとの月別シフトを登録。フレックス所定労働との差分を確認できます。
              </li>
              <li>
                <strong>残業レポート</strong>: 36協定の閾値（45h/80h/100h）超過を社員別に可視化。閾値を初めて超えた時点で自動メール通知されます。
              </li>
              <li>
                <strong>休暇残高</strong>: 年度の付与・繰越・消化状況の一覧、全社員への付与、年末の繰越処理。
              </li>
            </ul>
          </Section>
        )}

        <Section title="パスワード変更">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              画面右上のユーザーメニュー →「パスワード変更」から変更できます。
            </li>
            <li>
              変更すると他の端末のセッションは全て無効化されます（現在の端末は継続）。
            </li>
          </ul>
        </Section>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 items-center rounded-lg bg-brand-500 px-5 text-[13px] font-bold text-white hover:bg-brand-600"
          >
            閉じる
          </button>
        </div>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-4 rounded-lg border border-divider p-4">
      <h3 className="mb-2 text-[13.5px] font-bold text-text-primary">{title}</h3>
      <div className="text-[12.5px] leading-relaxed text-text-secondary">
        {children}
      </div>
    </section>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="mx-1 inline-flex h-5 items-center rounded border border-border-default bg-surface-alt px-1.5 text-[11px] font-bold text-text-primary">
      {children}
    </kbd>
  );
}
