# J-Wave TOKIO HOT 100 - Apple Music Playlist Automation

J-Wave TOKIO HOT 100 のランキングを毎週自動取得し、Apple Music の年間プレイリストに追加するツール。

GitHub Actions で毎週月曜 0:00 (JST) に自動実行される。

## 仕組み

1. J-Wave TOKIO HOT 100 チャートページをスクレイピング（100曲）
2. Apple Music カタログで各曲を検索し、カタログIDを取得
3. 年間プレイリスト（例: "J-Wave TOKIO HOT 100 2026"）に未追加の曲を追加
4. 検索結果を `data/song_cache.json` にキャッシュ（次回以降の検索を省略）

## 前提条件

- [Apple Developer Program](https://developer.apple.com/programs/) に加入済み（$99/年）
- Apple Music サブスクリプションが有効な Apple ID

## セットアップ

### 1. MusicKit Key の作成

1. [Apple Developer](https://developer.apple.com/account) にログイン
2. **Certificates, Identifiers & Profiles** → **Keys** → 「+」をクリック
3. **MusicKit** にチェック → 名前を入力（例: "Hot100"）→ **Continue** → **Register**
4. `.p8` ファイルをダウンロード（**1回しかダウンロードできない**ので保管すること）
5. 画面に表示される **Key ID**（10文字）をメモ
6. [Membership](https://developer.apple.com/account) ページで **Team ID** をメモ

### 2. GitHub リポジトリの作成とシークレット設定

1. このコードを GitHub リポジトリにプッシュ
2. **Settings** → **Secrets and variables** → **Actions** で以下を追加:

| Secret 名 | 値 |
|-----------|-----|
| `APPLE_MUSIC_TEAM_ID` | Apple Developer の Team ID |
| `APPLE_MUSIC_KEY_ID` | MusicKit Key の Key ID |
| `APPLE_MUSIC_PRIVATE_KEY` | `.p8` ファイルの中身をそのまま貼り付け |
| `APPLE_MUSIC_USER_TOKEN` | 次のステップで取得 |

### 3. Music User Token の取得

プレイリスト操作にはユーザー認証が必要。初回に1回だけ行う。

```bash
# 依存パッケージをインストール
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Developer Token を生成
python -c "
import jwt, time
token = jwt.encode(
    {'iss': 'YOUR_TEAM_ID', 'iat': int(time.time()), 'exp': int(time.time()) + 3600},
    open('path/to/AuthKey.p8').read(),
    algorithm='ES256',
    headers={'kid': 'YOUR_KEY_ID'}
)
print(token)
"
```

1. ローカルサーバーを起動: `python -m http.server 8000`
2. ブラウザで `http://localhost:8000/tools/get_music_user_token.html` を開く
3. 生成した Developer Token を貼り付け
4. 「Authorize Apple Music」をクリック → Apple ID でサインイン
5. 表示された Music User Token をコピー
6. GitHub Secrets の `APPLE_MUSIC_USER_TOKEN` に設定

### 4. 動作テスト

```bash
# 環境変数を設定
export APPLE_MUSIC_TEAM_ID="..."
export APPLE_MUSIC_KEY_ID="..."
export APPLE_MUSIC_PRIVATE_KEY="$(cat path/to/AuthKey.p8)"
export APPLE_MUSIC_USER_TOKEN="..."

# 実行
python src/main.py
```

または GitHub Actions の **Actions** タブ → **Weekly J-Wave HOT 100 Playlist** → **Run workflow** で手動実行。

## 自動実行

GitHub Actions のスケジュールにより毎週月曜 0:00 (JST) に自動実行される。
設定変更は `.github/workflows/weekly-playlist.yml` の `cron` を編集。

## キャッシュ (`data/song_cache.json`)

```json
{
  "songs": {
    "xg|hypnotize": "1780123456",
    "アーティスト名|曲名": null
  },
  "playlists": {
    "2026": {
      "id": "p.XXXXXXXXX",
      "added_songs": ["1780123456"]
    }
  }
}
```

- `songs`: 曲の Apple Music ID マッピング。`null` は Apple Music に見つからなかった曲
- `playlists`: 年ごとのプレイリスト ID と追加済み曲リスト

`null` エントリを削除すると次回実行時に再検索される。

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| 401 / 403 エラー | Music User Token が期限切れ。`tools/get_music_user_token.html` で再取得 |
| 曲が見つからない | `song_cache.json` の該当エントリ（`null`）を削除して再実行 |
| スクレイピング失敗 | J-Wave のサイト構造が変更された可能性。Issue を作成してください |
| GitHub Actions が動かない | Actions タブでエラーログを確認。Secrets が正しく設定されているか確認 |

## 注意事項

- Music User Token は約6ヶ月で期限切れ → 半年に1回 `tools/get_music_user_token.html` で再取得
- Apple Music API にはプレイリストの曲削除機能がないため、追加のみの運用
- J-Wave の放送は毎週日曜。チャート更新後の月曜 0:00 に取得するタイミング
