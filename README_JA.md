# Harness for Codex

[English](README.md) | [한국어](README_KO.md) | **日本語**

[revfactory/harness](https://github.com/revfactory/harness) のコミット [`cceac68`](https://github.com/revfactory/harness/commit/cceac68ea1d0ad198ef4b7b906cd238375836387) を基にした、独立した Codex 向け移行版です。プロジェクト専用のエージェントとスキルを作成し、親エージェントが独立した作業の並列実行と結果の統合を担当します。

リポジトリを取得します。

```bash
git clone https://github.com/revfactory/codex-harness.git
cd codex-harness
```

このディレクトリを信頼するローカルプロジェクトとして、新しい Codex セッションで開いてください。

```text
$harness このプロジェクトに合うハーネスを構成して。独立した作業はサブエージェントで並列に進めて。
```

別のプロジェクトへのインストールには Python 3.11 以上が必要です。このリポジトリのルートで実行します。

```bash
python3 scripts/install.py --target /absolute/path/to/project --dry-run
python3 scripts/install.py --target /absolute/path/to/project
python3 scripts/validate.py --project /absolute/path/to/project
```

プラグインはスキルを配布します。プロジェクトのエージェントと設定も必要な場合は、上記インストーラーを使用してください。作成したエージェントが表示されない場合は、新しいスレッドを開始します。

詳細は [English README](README.md)、[한국어 README](README_KO.md)、[Quickstart](docs/quickstart.md) を参照してください。静的検証と実際の Codex での並列動作確認は別の手順です。

[Apache License 2.0](LICENSE)。原著作は revfactory/harness の貢献者によります。
