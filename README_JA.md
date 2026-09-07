# Harness for Codex

[English](README.md) | [한국어](README_KO.md) | **日本語**

[revfactory/harness](https://github.com/revfactory/harness) のコミット [`cceac68`](https://github.com/revfactory/harness/commit/cceac68ea1d0ad198ef4b7b906cd238375836387) を基にした、独立した Codex 向け移行版です。プロジェクト専用のエージェントとスキルを作成し、親エージェントが独立した作業の並列実行と結果の統合を担当します。

## プラグインとしてインストール（推奨）

ターミナルで次の2つのコマンドを実行します。リポジトリの手動クローンや Python インストーラーの実行は不要です。

```bash
codex plugin marketplace add https://github.com/revfactory/codex-harness.git
codex plugin add codex-harness@codex-harness
```

ハーネスを適用するプロジェクトを **新しい Codex セッション**で開き、次を入力します。

```text
$harness このプロジェクトに合うハーネスを構成して。独立した作業はサブエージェントで並列に進めて。
```

プラグインは `harness` スキル、参照資料、補助スクリプトを提供します。依頼に応じて、プロジェクトに適したエージェントとスキルを生成します。基本エージェント5個とプロジェクト設定を導入する場合は、下記のプロジェクトインストーラーを使用してください。

コマンドの構文は Codex CLI **0.153.4** で確認しました。マーケットプレイスを追加した後、CLI の `/plugins` から **Codex Harness → Harness for Codex → Install** を選択してもインストールできます。その後、新しいセッションを開始します。デスクトップアプリ、ローカルリポジトリからのインストール、トラブルシューティングは [Quickstart](docs/quickstart.md#install-as-a-plugin-recommended) を参照してください。[公式プラグインガイド](https://learn.chatgpt.com/docs/plugins)。

## ローカルリポジトリで開発する

リポジトリを取得します。

```bash
git clone https://github.com/revfactory/codex-harness.git
cd codex-harness
```

このディレクトリを信頼するローカルプロジェクトとして、新しい Codex セッションで開いてください。

```text
$harness このプロジェクトに合うハーネスを構成して。独立した作業はサブエージェントで並列に進めて。
```

## 別のプロジェクトへのインストール（任意）

基本チーム全体のインストールには Python 3.11 以上が必要です。このリポジトリのルートで実行します。

```bash
python3 scripts/install.py --target /absolute/path/to/project --dry-run
python3 scripts/install.py --target /absolute/path/to/project
python3 scripts/validate.py --project /absolute/path/to/project
```

プラグインのインストール自体は、プロジェクトの `.codex/agents/`、`.codex/config.toml`、`AGENTS.md` ポインターを作成しません。上記インストーラーがこれらを導入します。作成したエージェントが表示されない場合は、新しいスレッドを開始します。

詳細は [English README](README.md)、[한국어 README](README_KO.md)、[Quickstart](docs/quickstart.md) を参照してください。静的検証と実際の Codex での並列動作確認は別の手順です。

[Apache License 2.0](LICENSE)。原著作は revfactory/harness の貢献者によります。
