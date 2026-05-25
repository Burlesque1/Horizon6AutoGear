<div align="center">

# 🏎️ Horizon6AutoGear

[English](README.md) | [中文](README.zh-CN.md) | **日本語**

Forza Horizon 5/6 及び Forza Motorsport 用インテリジェント運転アシスタント。

~60Hz でゲームの UDP テレメトリを受信し、トルクカーブに基づいて最適シフトポイントを計算、AI ドライビングコーチシステムを提供します。

</div>

---

## 📸 プレビュー

<img src=".github/assets/hero.jpg" alt="Forza Horizon 6" width="100%" />

<table>
  <tr>
    <td align="center"><b>🖥️ Web ダッシュボード</b></td>
    <td align="center"><b>📊 トルク分析</b></td>
  </tr>
  <tr>
    <td><img src=".github/assets/dashboard.png" alt="Web ダッシュボード" width="400" /></td>
    <td><img src=".github/assets/torque-analysis.png" alt="トルク分析" width="400" /></td>
  </tr>
  <tr>
    <td align="center"><b>🧠 AI コーチ HUD</b></td>
    <td align="center"><b>🗺️ トラックマップ</b></td>
  </tr>
  <tr>
    <td><img src=".github/assets/coach-hud.png" alt="AI コーチ HUD" width="400" /></td>
    <td><img src=".github/assets/track-map.png" alt="トラックマップ" width="400" /></td>
  </tr>
</table>

## ✨ 機能

- ⚡ **自動シフト** — 各ギアのトルクデータを収集し、ギアチェンジ前後のトルクが等しくなる最適シフト回転数を分析、リアルタイムでシフトを実行
- 🖥️ **Web GUI ダッシュボード** — pywebview ベースのインターフェース。Canvas 描画のリアルタイムトルクチャート、トラックマップ、テレメトリダッシュボード（Phantom テーマ）
- 🧠 **AI ドライビングコーチ (MVP)** — 走行ライン偏差、ブレーキタイミング、タイヤグリップ指標のビジュアルコーチングオーバーレイ
- 🎥 **セッション録画・再生** — UDP テレメトリセッションを録画し、オフライン分析のために再生
- 🔗 **リモートデバッグ** — デュアルマシン構成：ゲーム PC のエージェントがテレメトリを転送、開発機で GUI と分析を実行
- 🌐 **多言語 UI** — 英語・中国語インターフェース

## 🚀 クイックスタート

### インストール

```bash
pip install -e .
```

Python >= 3.8 が必要です。Windows では `pywin32` が自動的にインストールされます。

### 起動

```bash
# Web GUI を起動（メイン）
horizon6-autogear

# またはモジュール経由
python -m horizon6_autogear.gui
```

### 🎮 ゲーム設定

1. Forza で **設定 > HUD** を開き、**Data Out** を有効化
2. **Data Out IP** を自分の PC の IP に設定（同一 PC の場合は `127.0.0.1`）
3. **Data Out Port** を `54321` に設定（デフォルト、`FORZA_UDP_PORT` 環境変数で変更可能）
4. **Data Out Packet Format** を `FH6` に設定（Forza Horizon 5 の場合は `FH5`）
5. Horizon6AutoGear を起動し、**Collect** をクリックしてトルクデータの記録を開始

## 🔄 使い方

1. 📡 **Collect（収集）** — 全ギアを通して走行。各ギアの回転数、速度、トルク、タイヤスリップを記録
2. 📈 **Analyze（分析）** — 収集したトルクカーブから最適シフトポイントを計算
3. 🏁 **Run（実行）** — テレメトリ更新レートでリアルタイム自動シフトを開始

シフト設定は車両ごとに自動保存（ordinal + performance + drivetrain で識別）、車両切り替え時に自動読み込みされます。

## 🏗️ アーキテクチャ

```
Forza ゲーム (UDP) ➜ ForzaDataPacket (パーサー) ➜ Forza (エンジン)
                            |                          |
                            v                          v
                   コーチ HUD オーバーレイ       gear_helper (シフトロジック)
                                                     |
                                                     v
                                              keyboard (Win32 / macOS 入力)
```

### パッケージ構成

```
src/horizon6_autogear/
├── core/           # Forza エンジン、CarInfo モデル、データパケットパーサー、録画/再生
├── shifting/       # シフトアルゴリズム (gear_helper.py)、キーボード入力 (Win32 + macOS)
├── config/         # 定数：UDP 設定、キーバインド、タイミング、UI 色、i18n
├── gui/            # チャートウィジェット、HUD オーバーレイ
├── gui.py          # pywebview Web GUI（メイン UI）
└── utils/          # ソケットヘルパー、設定 I/O、プロット、ログ
```

### シフトアルゴリズム

最適シフトポイントは、現在のギアのトルクと次のギアのトルクが等しくなる回転数です。数学的導出は [`docs/SHIFT_ALGORITHM.md`](docs/SHIFT_ALGORITHM.md) を参照してください。

## 🛠️ 開発

### テスト

```bash
pytest                       # 全テストを実行
pytest tests/test_forza.py   # 個別ファイル
pytest --cov                 # カバレッジ付き
```

### リント

```bash
ruff check .
```

### 開発用依存パッケージ

```bash
pip install -e ".[dev]"   # pytest, ruff, pytest-cov
pip install -e ".[all]"   # 開発用 + pyinstaller
```

### 📦 パッケージング (Windows)

```bash
pip install pyinstaller
# 同梱の spec ファイルを使用
pyinstaller package/gui.spec
```

## ⚙️ 環境変数

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `FORZA_UDP_IP` | `0.0.0.0` | テレメトリ受信用 IP |
| `FORZA_UDP_PORT` | `54321` | テレメトリデータ UDP ポート |

## 🗺️ AI ドライビングコーチ ロードマップ

- ✅ **フェーズ 1：コーチ HUD (MVP)** — 走行ライン、ブレーキタイミング、タイヤグリップのビジュアルオーバーレイ。*現在*
- 🔜 **フェーズ 2：リファレンスプロファイル** — AI ラップの記録、速度差 / ギア提案 / ブレーキポイントプレビュー
- 🔜 **フェーズ 3：セミオート** — ViGEmBus 仮想コントローラー、オートブレーキ + オートシフト
- 🔜 **フェーズ 4：フルオート** — 自律運転（ステアリング + スロットル + ブレーキ + ギア）PID 制御

## 📚 ドキュメント

- [シフトアルゴリズム](docs/SHIFT_ALGORITHM.md) — 最適シフトポイントの数学的導出
- [UDP データ仕様](docs/FORZA_UDP_DATA_SPEC.md) — Forza テレメトリパケットフォーマットリファレンス
- [Web GUI デザイン](docs/web-gui-design.md) — フロントエンドアーキテクチャとテーマシステム

## 📄 ライセンス

[MIT](LICENSE) &copy; 2025-2026 Burlesque1
