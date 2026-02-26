# Score Viewer (PWA)

PDFの楽譜を縦連結で表示するオフライン対応PWAです。

## ファイル構成

- `index.html` UI本体
- `app.js` PDF読み込み・レンダリング・オートスクロール・IndexedDBライブラリ
- `sw.js` Service Worker（precache + runtime cache）
- `manifest.json` PWAマニフェスト
- `style.css` 最低限のUIスタイル
- `vendor/pdfjs/` pdf.js配置先

## 重要: pdf.js同梱について

このリポジトリにはネットワーク制限環境のため `pdfjs-dist` 本体を同梱できていません。以下をローカルに配置してください。

- `vendor/pdfjs/pdf.mjs`
- `vendor/pdfjs/pdf.worker.mjs`

取得元例（オンライン環境で実施）:

```bash
curl -L https://cdn.jsdelivr.net/npm/pdfjs-dist@4.5.136/build/pdf.mjs -o vendor/pdfjs/pdf.mjs
curl -L https://cdn.jsdelivr.net/npm/pdfjs-dist@4.5.136/build/pdf.worker.mjs -o vendor/pdfjs/pdf.worker.mjs
```

## 起動方法

### 「指定されたパスが見つかりません」が出るとき

これは多くの場合、**保存していない**のではなく、`cd` したパスが間違っている状態です。

まず、エクスプローラーで `score-viwer` フォルダを開いて、アドレスバーをクリックし、表示されたフルパス（例: `C:\Users\<あなた>\Downloads\score-viwer`）をコピーしてください。

そのパスを使ってコマンドプロンプトで次を実行します。

```bat
cd /d "ここにコピーしたフルパス"
dir
```

`dir` の結果に **`index.html` が見えれば正しい場所**です。

### Windows（最短）

```bat
cd /d "ここにコピーしたフルパス"
start_server.bat
```

### 手動起動（共通）

```bash
python -m http.server 8000 --bind 127.0.0.1
```

ブラウザで `http://127.0.0.1:8000` を開きます。


### それでも「存在しない」と言われるとき（そもそも未配置の可能性）

`cd` が正しくても `dir` に `index.html` が出ない場合は、**このプロジェクト自体がPCにまだ置かれていない**可能性があります。

確認手順（Windows）:

```bat
where /r C:\ score-viwer 2>nul
```

- 何も出ない: `score-viwer` フォルダがPC上に存在しません（未ダウンロード/未展開）。
- 出たパスを使って、次を実行してください。

```bat
cd /d "見つかったパス"
dir
start_server.bat
```

`dir` で次のファイルが見えれば正解です。

- `index.html`
- `app.js`
- `README.md`


## 使い方

1. `PDFを開く` で端末ローカルのPDFを選択（MVP方式）。
2. 必要なら `ライブラリ保存` で IndexedDB に保存（拡張方式）。
3. `ライブラリ` から再読み込み。オフライン時も利用可能。
4. Start/Pause/Reset でオートスクロール。
5. 速度は `px/ms` スライダー、または BPM + 1拍px から反映。
6. 画面の余白をタップすると操作UI表示/非表示。

## iPad / Android でのオフライン確認手順

1. 同一LAN上の端末から開発PCの `http://<PCのIP>:8000` を開く。
2. 一度オンラインでページ表示し、Service Worker登録完了を待つ。
3. ホーム画面へ追加（iPad: 共有→ホーム画面、Android: メニュー→ホーム画面）。
4. 一度アプリを閉じる。
5. 端末を機内モードにしてホーム画面アイコンから起動。
6. 既に保存済みPDFがライブラリから開けることを確認。

## 実装上の注意点

- Safari(iOS)はService WorkerやIndexedDB容量制限が厳しく、長期間未使用時に削除される場合があります。
- IndexedDB保存容量は端末空き容量・ブラウザ実装に依存。大きいPDFを大量保存する場合は容量監視が必要。
- Service Workerキャッシュ更新は `CACHE_NAME` のバージョン更新で行います。
- オフライン完全運用には、`vendor/pdfjs` を必ず同梱してください。


## 開かないときのチェック（Windows）

1. `dir` で `index.html` があるか確認。
2. URLは `http://127.0.0.1:8000` を直接入力。
3. 8000番が使えないなら `python -m http.server 8010 --bind 127.0.0.1` を実行。
4. 初回起動時のWindowsファイアウォール許可を「許可」にする。
