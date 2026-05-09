# Valorant Premier Analyst

Valorant Premier の試合概要を **DuckDB に蓄積し、新しい試合があれば差分追加できるデータ基盤** です。

このリポジトリの目的は、まずは「壊れない取り込みパイプライン」を作ることです。
LLM レポート生成や勝率・ラウンド別などの高度な分析は、DuckDB 上にきれいなデータが溜まってから別レイヤとして乗せていきます。

---

## データフロー

```text
HenrikDev API
   │
   ▼
data/raw/latest_matches.json        ← 直近 fetch のバンドル（デバッグ用）
data/raw/matches/{match_id}.json    ← 試合単位の永続アーカイブ（再構築用ソース）
   │
   ▼
filter_premier (queue/mode に "premier" を含むもののみ)
   │
   ▼
normalize_matches / normalize_match_players  (pandas DataFrame)
   │
   ▼
DuckDB upsert (db/valorant.duckdb)
   ├─ matches         PK: match_id
   └─ match_players   PK: (match_id, puuid)
```

主要モジュール:

| モジュール | 役割 |
| --- | --- |
| `api/henrik_client.py` | HenrikDev API 取得（timeout / 例外整理） |
| `storage/raw_store.py` | バンドル JSON 入出力 + `data/raw/matches/` への per-match アーカイブ |
| `storage/duckdb_store.py` | `upsert_dataframe`（自然キー差分追加）/ `table_row_count` |
| `storage/roster_history.py` | `data/roster_history.json` の永続化と API/DB 由来メンバーのマージ |
| `processing/normalize.py` | `filter_premier` + `matches`/`match_players` 正規化 |
| `analysis/roster.py` | ロスター解析（discover / matches / payload フィルタ / Premier API メンバー抽出） |
| `cli.py` | `fetch` / `ingest` / `backfill` / `status` / `run` / `report` / `team-info` / `team-backfill` / `team-sync` / `roster-discover` / `roster-matches` / `roster-sync` |
| `server/scheduler.py` | FastAPI lifespan が起動する asyncio 定期ジョブ（既定 15 分ごとに `team-sync`） |

> `analysis/metrics.py` と `reporting/markdown_report.py` は **任意の `report` コマンド専用**として残してありますが、データ基盤の中心ではありません。

---

## セットアップ

### uv を使う場合

```bash
cp .env.example .env
uv sync
```

### pip + venv を使う場合

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

> Python 3.11 以上が必要です。

`.env` の例:

```env
HENRIK_API_KEY=          # HenrikDev で発行した API キー（必須）
VALORANT_REGION=ap       # ap / eu / na / kr / latam / br
VALORANT_NAME=           # Riot ID の名前部分（個人）
VALORANT_TAG=            # Riot ID のタグ部分（個人）
MATCH_SIZE=10            # 1 回の fetch で取得する直近試合数

# Premier チーム識別（公式戦バックフィル用 — 推奨）
PREMIER_TEAM_NAME=       # Premier チームの表示名
PREMIER_TEAM_TAG=        # Premier チームの 3 文字タグ

# 任意: ロスターを手動で固定したい場合
PREMIER_ROSTER=          # Name#Tag を カンマ区切り（空ならチームAPIから自動取得）
ROSTER_MIN_PRESENT=4     # 同チームに何人いれば「ロスター試合」と見なすか
```

API キーが空の状態で `fetch` を呼ぶと、わかりやすい `Configuration error` で停止します。

---

## 実行方法

### 通常の運用

```bash
# 試合履歴を取得 → DuckDB に差分追加 → 状態確認
python -m valorant_analyst.cli run

# 既に DuckDB にあるデータの状態を見るだけ
python -m valorant_analyst.cli status
```

`run` は内部で `fetch` → `ingest` → `status` を直列実行します。
**何度叩いても、新しい試合だけが追加されます**（`match_id` で判定）。

### 個別に実行したい場合

```bash
# 1) HenrikDev から直近試合を取得し、バンドル + per-match アーカイブを保存
python -m valorant_analyst.cli fetch

# 2) 直近 fetch のバンドルを DuckDB に upsert（Premier のみ）
python -m valorant_analyst.cli ingest

# 3) DuckDB の行数・最新試合を表示
python -m valorant_analyst.cli status
```

### Premier チーム名で公式戦をまとめて取得（推奨）

`.env` に Premier チーム名を入れてあれば、**HenrikDev の Premier 専用エンドポイント** から「公式リーグ戦の match_id 一覧」を直接取れます。一番素直で正確な経路です。

```env
PREMIER_TEAM_NAME=YourTeamName
PREMIER_TEAM_TAG=TAG
```

```bash
# チーム情報（公式メンバー / 戦績 / コンファレンス・ディビジョン）を表示
python -m valorant_analyst.cli team-info

# 公式戦を全部ダウンロードしてアーカイブ（既存はスキップ）
python -m valorant_analyst.cli team-backfill

# まずは数試合だけで動作確認
python -m valorant_analyst.cli team-backfill --max-matches 3

# アーカイブから DuckDB を構築
python -m valorant_analyst.cli ingest --from-archive
```

挙動:

1. `/valorant/v1/premier/{name}/{tag}/history` で公式戦の match_id を取得
2. 既に `data/raw/matches/` にある試合はスキップ（冪等）
3. 各 match_id を `/valorant/v2/match/{id}` で個別取得 → アーカイブ
4. レート制限を考慮して自動 sleep + 429 自動リトライ

### 過去の試合を「自分の履歴側から」まとめて取り込む（補助手段）

Premier チーム名が分からない場合や、Premier 以外の試合（カスタム / スクリム）も
拾いたい場合は、自分の履歴側（`/v1/stored-matches` ページング → `/v2/match/{id}`）からも取れます。

```bash
# 全ページ走査して Premier だけ取り込み
python -m valorant_analyst.cli backfill

# まず1〜2ページだけで試したい
python -m valorant_analyst.cli backfill --max-pages 2

# Premier 以外も全部欲しい
python -m valorant_analyst.cli backfill --all-modes

# レート制限に引っかかるなら間隔を広げる
python -m valorant_analyst.cli backfill --sleep-seconds 3.0
```

> 古いシーズンの試合は Riot 側から消えていることがあり、その場合 404 で自動スキップします。

### Premier ロスター（メンバー）で絞る

「公式戦じゃないけどロスターが揃っている試合」（スクリム等）を切り出したい時は
`roster-*` コマンドが使えます。`PREMIER_TEAM_NAME` がセットされていれば、
`PREMIER_ROSTER` を空のままでも **API から自動でロスターを取ってきて**フィルタに使います。

```bash
# DuckDB から「自分とよく一緒に出ている puuid」上位を表示
python -m valorant_analyst.cli roster-discover

# ロスター 4 人以上が同じチームで揃った試合を一覧
python -m valorant_analyst.cli roster-matches

# ingest 時にもフィルタしたい場合
python -m valorant_analyst.cli ingest --from-archive --roster-only
```

#### ロスター履歴の自動同期（メンバー入れ替え対応）

`team-backfill` を実行すると、最後に **ロスター履歴の同期** が自動で走ります。
履歴は `data/roster_history.json` に蓄積され、新メンバーは自動で追加され、
チームを抜けたメンバーは `is_current=false` に倒されつつ **履歴には残ります**。
これにより、新加入直後でも追加コマンドなしで分析対象に入り、過去の選手も
ロスターフィルタや Web ダッシュボードのロスターから消えません。

```bash
# 通常フロー: チーム公式戦の取得と同時にロスター履歴も自動更新
python -m valorant_analyst.cli team-backfill
python -m valorant_analyst.cli ingest --from-archive

# 単独で同期だけ走らせたい場合（DB スキャンも併用して過去メンバーを回収）
python -m valorant_analyst.cli roster-sync --scan-db
```

ロスター解決の優先順位（`roster-matches` / `ingest --roster-only` 共通）:

1. `PREMIER_ROSTER`（`.env` の手動オーバーライド）
2. `data/roster_history.json` の **過去 + 現役の union**
3. Premier API の現メンバー（履歴がまだ空のときのフォールバック）

`--roster-source` で明示指定もできます:

```bash
# 現役だけで絞りたい
python -m valorant_analyst.cli roster-matches --roster-source=current

# 履歴にあるメンバー全員で絞りたい（既定の auto と同等、履歴がある場合）
python -m valorant_analyst.cli roster-matches --roster-source=history

# .env の PREMIER_ROSTER だけを使う（API/履歴を一切見ない）
python -m valorant_analyst.cli roster-matches --roster-source=env
```

`PREMIER_ROSTER` を手動で固定したい時（古いロスター含めて分析したい等）:

```env
PREMIER_ROSTER=Alice#JP1,Bob#JP1,Charlie#JP1,Dave#JP1,Eve#JP1
ROSTER_MIN_PRESENT=4
```

raw PUUID 文字列（`#` を含まない）と Riot ID（`Name#Tag`）を混ぜても OK です。

### よく使うオプション

```bash
# Premier 以外も全部取り込みたい
python -m valorant_analyst.cli ingest --all-modes

# DuckDB を捨てて、アーカイブから全試合を再構築
rm db/valorant.duckdb
python -m valorant_analyst.cli ingest --from-archive

# 任意：今 DuckDB にあるデータから Markdown サマリーを書き出す
python -m valorant_analyst.cli report
```

サンプル出力（`status`）:

```text
DuckDB: db\valorant.duckdb
  matches rows:        14
  match_players rows:  140
  latest match: id=... map=Ascent mode=Premier queue=premier game_start=...
  distinct maps: 5
```

---

## 生成されるファイル

| パス                                  | 内容                                                              |
| ------------------------------------- | ----------------------------------------------------------------- |
| `data/raw/latest_matches.json`        | 直近 fetch のバンドル（API レスポンスそのまま）                   |
| `data/raw/matches/{match_id}.json`    | **試合単位の永続アーカイブ**（再構築の元データ）                  |
| `data/roster_history.json`            | チーム別のロスター履歴（過去 + 現役の union、`roster-sync` で更新）|
| `db/valorant.duckdb`                  | `matches` と `match_players` を持つ DuckDB                        |
| `reports/latest_report.md`            | `report` コマンドで生成（任意）                                   |

DuckDB の中身は標準の duckdb CLI で確認できます。

```bash
duckdb db/valorant.duckdb "SELECT COUNT(*) FROM matches;"
duckdb db/valorant.duckdb "SELECT * FROM match_players ORDER BY match_id LIMIT 10;"
```

---

## テスト・Lint

```bash
pytest
ruff check .
mypy src                # 任意
```

カバーしている主な観点:

- `upsert_dataframe` が初回でテーブル作成 → 2 回目で既存キーをスキップ
- 単一キー / 複合キー（`match_players` 用の `(match_id, puuid)`）両対応
- 入力内の重複キーを 1 行に畳む
- per-match アーカイブの書き出し / 復元 / 壊れたファイルのスキップ
- Premier フィルタが `queue` / `mode` のいずれからでも判定できる
- 正規化が空ペイロード・キー欠損・型ゆらぎに耐える

---

## 設計メモ

### なぜ per-match アーカイブと DuckDB を両方持つのか

- **DuckDB**: クエリしやすい、集計が速い、列スキーマが固定。日々の差分追加先。
- **`data/raw/matches/{match_id}.json`**: スキーマ変更や正規化バグから回復するための「生のソース」。
  DuckDB を消しても `ingest --from-archive` で全件再構築できます。

### upsert の戦略

DuckDB に PRIMARY KEY を強制せず、`NOT EXISTS` ベースで挿入しています。
理由は、HenrikDev 側のスキーマが将来増えても既存テーブルを壊さずに済ませたいからです。
キー衝突は `match_id`（matches）/ `(match_id, puuid)`（match_players）で判定します。

### Premier フィルタ

`metadata.queue` または `metadata.mode` を小文字化して `"premier"` を含むかどうかで判定しています。
HenrikDev のフィールド名がブレても拾えるよう、複数フィールドを見ます。
全モードを取り込みたい時は `--all-modes` を付けてください。

---

## Web ダッシュボード（Phase 2: フロント実装済み）

vlr.gg 風のチームダッシュボードを **FastAPI + Next.js** で構築しています。

```text
DuckDB ──► FastAPI (/api/teams/{name}/{tag}) ──► Next.js App Router (/team/[name]/[tag])
```

### バックエンド (FastAPI)

```bash
.venv\Scripts\activate
valorant-analyst-server
# または
python -m valorant_analyst.server.app
```

デフォルトで `http://127.0.0.1:8000` で起動します（reload 有効）。
動作確認:

```bash
curl http://127.0.0.1:8000/api/health
curl "http://127.0.0.1:8000/api/teams/<TEAM_NAME>/<TEAM_TAG>"
```

OpenAPI ドキュメントは `http://127.0.0.1:8000/docs` で確認できます。

#### 自動同期（バックグラウンドスケジューラ）

サーバ起動時に **既定 15 分ごとに `team-sync`（= `team-backfill` + `ingest --from-archive`）が自動実行**されます。これによりダッシュボードを開きっぱなしにしておけば、新しい Premier 試合が Henrik 側に上がり次第 DuckDB に取り込まれて反映されます。

- 手動で `POST /api/sync` を叩いた場合と**同じパイプライン・同じロック**を共有するので、ボタン同期と自動同期は重複しません（実行中なら片方は skip）。
- 状態は `GET /api/sync` で取得でき、`last_trigger` で `manual` / `scheduled` を区別できます。フロントの SyncButton に小さな `auto` / `manual` バッジが出ます。

設定 (`.env`):

```env
SYNC_AUTO_ENABLED=1                 # 0 で無効化
SYNC_AUTO_INTERVAL_MINUTES=15       # 何分間隔か
SYNC_AUTO_INITIAL_DELAY_SECONDS=30  # 起動直後の初回実行を遅らせる秒数
```

`HENRIK_API_KEY` / `PREMIER_TEAM_NAME` / `PREMIER_TEAM_TAG` のいずれかが空だと自動的に無効化され、起動ログに警告が出ます。**`UVICORN_WORKERS=1` 前提**（複数ワーカーだとプロセスごとに重複起動するので注意）。

#### Railway へデプロイする場合（Volume 必須）

サーバが書き込む永続データは **すべて `/app/db/` 配下** にまとまっています:

| パス                       | 内容                                              |
| -------------------------- | ------------------------------------------------- |
| `db/valorant.duckdb`       | 試合データの DuckDB                               |
| `db/raw/matches/*.json`    | 試合ごとの生 JSON アーカイブ（再構築の元データ）  |
| `db/strategy/*.json`       | Strategy タブのマップ別構成                       |
| `db/strategy/*.notes.json` | Strategy タブのマップ別ノート                     |
| `db/notes/*.md`            | チーム概要ノート                                  |
| `db/bios/*.md`             | プレイヤー bio                                    |
| `db/vods.json`             | VOD URL マッピング                                |
| `db/roster_history.json`   | ロスター履歴                                      |

**Railway では Settings → Volumes に次の Volume を 1 つ追加してください**:

```text
Mount path: /app/db
Size:       1 GB（用途的には 100 MB でも十分）
```

これだけで上記すべてが永続化され、デプロイをまたいでデータが保持されます。Volume を未設定のままだと、コンテナ再起動 / 再ビルドのたびに DuckDB と上のすべての JSON / Markdown がリセットされる点に注意してください。

旧バージョンで `data/strategy/` などに保存されていたファイルは、サーバ起動時に `db/` 配下へ自動マイグレーションされます（idempotent な一回限りの処理）。

提供エンドポイント:

| メソッド | パス | 用途 |
| --- | --- | --- |
| GET | `/api/health` | DuckDB の存在確認 |
| GET | `/api/teams/{name}/{tag}` | チーム概要：成績・直近試合・マップ別勝率・ロスターをまとめて返す（Overview タブ） |
| GET | `/api/teams/{name}/{tag}/matches` | チームの全試合一覧（Matches タブ） |
| GET | `/api/teams/{name}/{tag}/stats` | プレイヤー別 ACS/ADR/K-D-A/+/− + チームのエージェント使用率（Stats タブ） |
| GET | `/api/matches/{match_id}` | 単一試合の詳細（両チーム / ラウンド毎の結果 / プレイヤー stats + ACS / ADR / +/-）|
| GET | `/api/players/{puuid}` | プレイヤー個人ページ：所属チーム履歴 / エージェント別 / マップ別 / 直近試合 |

`/api/teams/{name}/{tag}` のレスポンス（抜粋）:

```json
{
  "name": "...",
  "tag": "...",
  "record": { "games": 23, "wins": 6, "losses": 17, "winrate_pct": 26.1 },
  "recent_matches": [
    { "match_id": "...", "map_name": "Breeze",
      "our_team": { "team": "Red", "rounds_won": 7, "rounds_lost": 13, "has_won": false },
      "opponent": { "name": "...", "tag": "...", "rounds_won": 13, "rounds_lost": 7 } }
  ],
  "map_winrates": [{ "map_name": "Split", "games": 4, "wins": 2, "winrate_pct": 50.0 }],
  "roster": [{ "name": "...", "games": 23, "agent_main": "Yoru", "kd_ratio": 1.01 }]
}
```

### フロントエンド (Next.js)

`web/` に Next.js 16 (App Router) + TypeScript + Tailwind v4 で構築しています。

```bash
cd web
cp .env.example .env.local
# .env.local の DEFAULT_TEAM_NAME / DEFAULT_TEAM_TAG を埋める
npm install         # 初回のみ
npm run dev
```

`http://localhost:3000` を開くと、`.env.local` で指定したチームへのリンクが出るので、そこから vlr.gg 風のダッシュボードに飛べます。Next.js は `NEXT_PUBLIC_API_BASE_URL`（既定 `http://127.0.0.1:8000`）に対して SSR で API を叩くため、**先に FastAPI を起動しておく**必要があります。

ルーティング:

| パス | 内容 |
| --- | --- |
| `/` | 設定済みの Premier チームへのリンク |
| `/team/[name]/[tag]` | **Overview** タブ: 4 タイル / Recent Matches / Map Winrates / Roster |
| `/team/[name]/[tag]/matches` | **Matches** タブ: チームが戦った全試合一覧 |
| `/team/[name]/[tag]/stats` | **Stats** タブ: プレイヤー別詳細スタッツ + エージェント使用率 |
| `/match/[id]` | vlr.gg 風の試合詳細：マップバナー・スコアヘッダ・ラウンドタイムライン・両チームのスコアボード（ACS / ADR / +/- / K/D） |
| `/player/[puuid]` | 個人ページ：サマリー / Recent Matches / Team History / Map Stats / Agent Stats |

チームページの 3 タブは `team/[name]/[tag]/layout.tsx` でチームヘッダ + タブナビを共通化、各タブは下位 `page.tsx` です。`Tabs` (`web/src/components/Tabs.tsx`) は `usePathname` で active を自動判定するクライアントコンポーネントです。

主な実装ファイル:

| パス | 役割 |
| --- | --- |
| `web/src/lib/api.ts` | FastAPI の TypeScript 型 + fetch ヘルパ（`fetchTeam` / `fetchMatch` / `fetchHealth`）。Pydantic スキーマと 1:1 |
| `web/src/lib/format.ts` | スコア・%・日付・duration などの整形 |
| `web/src/lib/agents.ts` | エージェント名 → アイコン URL（`media.valorant-api.com`）/ ロール色 |
| `web/src/lib/maps.ts` | マップ名 → splash 画像 URL |
| `web/src/components/{Header,Card,Pill,AgentBadge,RoundTimeline,Scoreboard,Tabs}.tsx` | 共通 UI（`Tabs` は `usePathname` で active を判定） |
| `web/src/app/team/[name]/[tag]/layout.tsx` | チームヘッダ + 3 タブナビ（Overview / Matches / Stats）。`fetchTeam(..., 1)` で record だけ軽く引く |
| `web/src/app/team/[name]/[tag]/page.tsx` | Overview タブ本体（SSR） |
| `web/src/app/team/[name]/[tag]/matches/page.tsx` | Matches タブ（全試合一覧） |
| `web/src/app/team/[name]/[tag]/stats/page.tsx` | Stats タブ（プレイヤー詳細 + エージェント使用率） |
| `web/src/app/player/[puuid]/page.tsx` | 個人ページ本体（SSR） |
| `web/src/app/match/[id]/page.tsx` | 試合詳細ページ（SSR） |
| `web/src/app/{team,match,player}/[...]/{not-found,error}.tsx` | 404 / 例外時の表示 |
| `web/src/app/globals.css` | Tailwind v4 の `@theme` でダーク基調のセマンティックカラーを定義 |

API スキーマを変えた場合は `web/src/lib/api.ts` の TypeScript 型も合わせて更新してください（型生成は今のところ手動運用）。

> Node.js が未インストールの場合は `winget install OpenJS.NodeJS.LTS` でインストールしてからシェルを開き直してください。

---

## 今後の拡張余地

データ基盤が安定してから別レイヤで足す想定の項目です。

- LLM SQL エージェント（`POST /api/agent/query` を生やす）
- 試合詳細ページ（ラウンドごとの推移、攻守別）
- First Blood / Multi-kill / 経済（エコ・フォース）指標
- 複数 Premier シーズンの横断比較
- 認証付きデプロイ

---

## 注意点

- HenrikDev API はサードパーティ運用のためレスポンス構造が変わることがあります。`processing/normalize.py` は `.get()` ベースで欠損に強く書いていますが、新しいフィールドを使いたい時はここを更新してください。
- 本リポジトリは **データ基盤の MVP** であり、最初から完璧な分析機能は搭載していません。「取得 → アーカイブ → 差分 ingest → DuckDB」が確実に動くことを優先しています。
