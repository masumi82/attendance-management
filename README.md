# 勤怠管理システム

ラズベリーパイ 4 上で動作する本番運用レベルの勤怠管理 Web アプリケーション（学習目的）。

## 技術スタック

| レイヤ | 採用技術 |
|---|---|
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + TanStack Query |
| DB | PostgreSQL 16 |
| Auth | Argon2id パスワードハッシュ + JWT（access 15分 / refresh 14日ローテーション）+ JTI 失効リスト |
| Reverse Proxy | nginx |
| 外部公開 | Cloudflare Tunnel（ポート開放不要、常時 HTTPS） |
| デプロイ先 | Raspberry Pi 4 (arm64) / Docker Compose / systemd |

## 主な機能

- 認証（ログイン / リフレッシュローテーション / パスワード変更 / 再利用検知）
- 役割: 管理者 / 承認者 / 一般社員
- 打刻（出勤 / 休憩開始 / 休憩終了 / 退勤）と状態遷移ガード
- 日次集計（労働時間 / 残業 / 深夜労働 / 休憩）
- 月次締め（スナップショット化 + 以後の打刻ブロック + 再オープン）
- 申請・承認ワークフロー（打刻修正 / 残業事前 / 残業事後 / 休暇）
  - 自己承認禁止（内部統制）
- 36 協定アラート（45h / 80h / 100h、閾値を跨いだタイミングで 1 度だけメール通知）
- 有給休暇管理（勤続年数ベースの自動付与 + 個別付与 + 年度繰越 + 2 年失効）
- シフト / フレックス所定労働との差分集計
- 社員・部署・祝日マスタ管理
- 通知ベル（自分の申請が承認 / 却下された時、未読バッジ）
- ヘルプ（ロール別使い方ガイド）
- CSV 出力（勤怠 / 休暇残高、BOM 付き UTF-8 で Excel 対応）

## セットアップ（開発環境）

### 前提

- Docker / Docker Compose v2
- （任意）Python 3.12 / Node 20 でローカル実行する場合のみ

### 手順

```bash
# 1. 環境変数を設定
cp .env.example .env
# .env を編集して JWT_SECRET と POSTGRES_PASSWORD を強いランダム値に変更
#   openssl rand -hex 32    # JWT_SECRET に
#   openssl rand -base64 32 # POSTGRES_PASSWORD に

# 2. コンテナを起動
docker compose up -d --build

# 3. ブラウザで確認
#   http://localhost:8080/            → フロントエンド
#   http://localhost:8080/api/health  → バックエンドヘルスチェック

# 4. 初期管理者でログイン
#   email: .env の INITIAL_ADMIN_EMAIL
#   password: .env の INITIAL_ADMIN_PASSWORD
#   ログイン後、右上メニュー → パスワード変更で即時変更すること
```

### テスト実行

```bash
# バックエンド (pytest、66 ケース)
docker compose exec backend pytest -v
```

### 停止・クリーンアップ

```bash
docker compose down             # 停止
docker compose down -v          # 停止 + DB データも削除
```

## デプロイ（Raspberry Pi + Cloudflare Tunnel）

本番運用の骨格：

1. ラズパイ (Debian 13 / arm64) に Docker Engine + compose plugin をインストール
2. 本リポジトリを `/opt/attendance` に配置し、`.env` を本番値で作成
3. systemd unit `attendance.service` で起動管理（電源投入時の自動起動）
4. Cloudflare Zero Trust で Tunnel を作成し、トークンを `.env` の `CLOUDFLARE_TUNNEL_TOKEN` に設定
5. Public Hostname を `attendance.<your-domain>` → `http://localhost:8080` に設定
6. `pg_dump` の日次 cron で `/var/backups/attendance` に 7 世代ローテ
7. `ufw` で SSH 以外を拒否（Tunnel は outbound only なのでポート開放不要）

詳細は `ops/` 配下のスクリプトと systemd unit を参照してください（各環境の固有情報は含めていません）。

## ディレクトリ構成

```
.
├── backend/                   # FastAPI バックエンド
│   ├── app/
│   │   ├── api/v1/            # REST エンドポイント
│   │   ├── core/              # 設定・セキュリティ
│   │   ├── db/                # SQLAlchemy セッション
│   │   ├── jobs/              # APScheduler (36協定チェック等)
│   │   ├── models/            # ORM
│   │   ├── schemas/           # Pydantic
│   │   ├── services/          # 業務ロジック
│   │   └── main.py
│   ├── alembic/               # マイグレーション (0001〜0008)
│   ├── tests/                 # pytest (66 ケース)
│   └── Dockerfile
├── frontend/                  # React + Vite + Tailwind
│   ├── src/
│   │   ├── features/          # 画面単位の機能
│   │   │   ├── admin/         # 社員/部署/祝日/月次締め/シフト/残業/休暇
│   │   │   ├── approvals/
│   │   │   ├── auth/
│   │   │   ├── help/
│   │   │   ├── notifications/
│   │   │   ├── requests/
│   │   │   └── shifts/
│   │   ├── lib/               # API クライアント、zustand ストア
│   │   └── routes/            # ProtectedRoute
│   └── Dockerfile
├── nginx/                     # リバースプロキシ設定
├── docker-compose.yml
├── .env.example
└── README.md
```

## セキュリティ方針

- **シークレット**: `.env` は `.gitignore` 済み。`.env.example` のみを提供。
- **JWT**: access token 15 分、refresh token 14 日ローテーション、リフレッシュ再利用検知で全セッション失効、ログアウトで access JTI を denylist へ登録。
- **権限**: 役割ベース + 自己承認禁止のサーバ側ガード。
- **CSV インジェクション**: 出力値の先頭 `=/+/-/@` は現状未対策（要対応項目）。
- **レート制限**: `/auth/login` には現状未実装（要対応項目）。

## 実装完了フェーズ

| Phase | 内容 | 状態 |
|---|---|:---:|
| 0 | プロジェクト基盤 | ✅ |
| 1 | 認証・社員マスタ | ✅ |
| 2 | 打刻機能 | ✅ |
| 3 | 申請・承認ワークフロー | ✅ |
| 4 | 残業・36 協定アラート | ✅ |
| 5 | 休暇管理 | ✅ |
| 6 | シフト・フレックス | ✅ |
| 7 | 管理者機能・CSV | ✅ |
| 8 | ラズパイ実機運用 + Cloudflare Tunnel 外部公開 | ✅ |

## ライセンス

MIT License — 詳細は `LICENSE` を参照。
