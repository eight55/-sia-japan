# SIA v0.3 — 日本株・クラウド版

## Androidだけで公開する手順
1. このZIPを展開し、`generate.py`, `template.html`, `requirements.txt`, `README.md` をGitHubの `sia-japan` リポジトリの**ルート**にアップロード（GitHub Web画面の Add file → Upload files → Commit changes）。
2. `.github/workflows/publish.yml` はAndroidのChromeでGitHubリポジトリを開き、Add file → Create new file からファイル名に `.github/workflows/publish.yml` を入力して、ZIP内の同名ファイルの内容を貼り付け、Commit changes。ZIPをそのままリポジトリに1ファイルとしてアップロードするだけでは動作しません。
3. リポジトリ Settings → Pages → Build and deployment → Source を **GitHub Actions** に設定。
4. Actions → Update SIA → Run workflow → Run workflow。初回は数分かかることがあります。
5. 成功すると `https://<GitHubユーザー名>.github.io/sia-japan/` にアクセスできます。Android Chromeのメニューから「ホーム画面に追加」。

## 自動更新
GitHub Actionsが平日17:30 JST（UTC 08:30）を目安に起動します。遅延・スキップや株価提供側の更新遅延があり得ます。取得失敗時はその回の公開は失敗し、以前の公開ページが残ることがあります。表示の取得時刻・銘柄ごとの取引日を確認してください。必要ならActionsから手動実行できます。

## データ・制限
- Yahoo Finance由来の無料の日足データを非公式 `yfinance` で取得。取得時点の調整後終値であり、リアルタイム株価ではありません。利用規約・公開再配信条件を確認してください。Public GitHub Pagesでの公開前にデータ利用許諾の確認が必要です。許諾が不明なら、実データ入りページの公開は行わないでください。
- 初期監視リスト15銘柄から各期間のTOP5を表示。全東証銘柄のランキングではありません。
- RSI、MACD、移動平均、出来高倍率、ATRを計算。ランキングは透明な単純ルール。生成AI・将来価格予測・PER/PBR・決算分析は未実装。
- 参考戦略水準はATRの固定算式による例示で、投資助言ではありません。
- APIキー・パスワード・楽天証券の認証情報はリポジトリに保存しないでください。
- GitHub Pagesの公開ページは誰でも閲覧可能です。個人専用・非公開運用には認証付きホスティング等への変更が必要です。
