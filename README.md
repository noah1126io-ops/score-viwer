# Windows最小構成: RTMPose / MMPose で弓道動画の姿勢推定

このプロジェクトは、**Windows + conda** を前提に、
**単一人物の弓道動画 1 本**を入力として次を行う最小構成です。

- フレームごとの 2D キーポイント推定
- 可視化動画の書き出し
- キーポイントの CSV / JSON 保存
- 基本指標の算出とグラフ化
  - 左右肩の高さ差
  - 肩-肘-手首角度（左右）
  - 手首高さ時系列（左右）
  - 胴体の傾き

---

## 1. 前提環境（Windows）

- Windows 10/11
- Anaconda / Miniconda
- NVIDIA GPU があれば GPU 版 PyTorch、なければ CPU 版で可

> 最初は CPU でも動きます（速度は遅め）。

---

## 2. conda 環境作成

### 2-1. 新規環境

```bat
conda create -n kyudo-rtmpose python=3.10 -y
conda activate kyudo-rtmpose
```

### 2-2. PyTorch インストール

#### GPU (CUDA 12.1) 例

```bat
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

#### CPU のみ例

```bat
pip install torch torchvision torchaudio
```

### 2-3. MMPose 周辺

```bat
pip install -U pip openmim
mim install "mmengine>=0.10.0"
mim install "mmcv>=2.0.1,<2.2.0"
mim install "mmdet>=3.1.0"
mim install "mmpose>=1.3.0"
pip install opencv-python pandas matplotlib numpy tqdm
```

### 2-4. Spyder で実行したい場合

```bat
conda install spyder -y
```

Spyder 起動:

```bat
spyder
```

Spyder の Python インタプリタを `kyudo-rtmpose` 環境に合わせてください。

---

## 3. ファイル構成

```text
score-viwer/
  README.md
  requirements.txt
  run_pose_video.py
  analyze_pose_csv.py
  input/
    kyudo_sample.mp4
  outputs/
    run_YYYYmmdd_HHMMSS/
      vis_video.mp4
      keypoints.csv
      keypoints.json
      metrics.csv
      plots/
        shoulder_height_diff.png
        elbow_wrist_angles.png
        wrist_height_timeseries.png
        torso_tilt.png
```

`outputs/` はスクリプト実行時に自動作成されます。

---

## 4. 実行手順（最小）

1. `input/kyudo_sample.mp4` を置く
2. キーポイント推定 + 可視化動画 + CSV/JSON 出力
3. 指標グラフ化

```bat
python run_pose_video.py --input input/kyudo_sample.mp4
python analyze_pose_csv.py --csv outputs\run_YYYYmmdd_HHMMSS\keypoints.csv
```

※2つ目のコマンドは、1つ目で作られた実際のフォルダ名に置き換えてください。

---

## 5. run_pose_video.py の役割

- `MMPoseInferencer` を使って各フレーム推定
- 単一人物を選択（スコア最大）
- 次を保存
  - 可視化動画 `vis_video.mp4`
  - キーポイント `keypoints.csv`, `keypoints.json`
  - 指標 `metrics.csv`

キーポイントは COCO 17 点の名前で保存します。

---

## 6. analyze_pose_csv.py の役割

`keypoints.csv` から以下を再計算・可視化します。

- 左右肩の高さ差
- 肩-肘-手首角度（左右）
- 左右手首高さ
- 胴体傾き

出力先は `.../plots/` です。

---

## 7. Spyder での実行例

### run_pose_video.py

Spyder の `Run > Configuration per file` で引数を:

```text
--input input/kyudo_sample.mp4
```

### analyze_pose_csv.py

```text
--csv outputs/run_20260422_120000/keypoints.csv
```

---

## 8. 最初の改善候補（次フェーズ）

1. **弓道用の関節定義追加**
   - 手の内、弓手/馬手に意味づけした独自特徴量を追加
2. **時系列平滑化**
   - Savitzky-Golay / Kalman で角度ノイズ低減
3. **欠損補間**
   - 低信頼フレームの補間（線形/スプライン）
4. **区間自動分割**
   - 射法八節に近いイベント区切り（会・離れなど）
5. **CLI と設定ファイル分離**
   - `config.yaml` 化して実験管理しやすくする
6. **複数動画バッチ処理**
   - フォルダ一括処理 + 集計レポート

---

## 9. トラブルシュート

- `ModuleNotFoundError: mmpose`:
  - `conda activate kyudo-rtmpose` を確認
- `MMCV` 周りのエラー:
  - `mmcv` / `mmdet` / `mmpose` のバージョン整合を取り直す
- 可視化動画が生成されない:
  - OpenCV の codec 問題の可能性。`mp4v` で失敗する場合 `XVID` を試す

