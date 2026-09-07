# Tumblr動画自動投稿

本番の動画正本は`../000_Tumblr_movie`です。直下と全サブフォルダを再帰走査し、
同一バイトのコピーだけSHA-256でまとめます。別の承認台帳は使いません。

## 現行の自動実行

Windowsタスクが`dispatch_local.py`を1日3回起動します。未投稿の動画を最優先し、
全種類を一巡するまで同じ動画を再利用しません。選ばれた1本だけを短時間の
GitHub Release資産としてGitHub Actionsへ渡し、Tumblr投稿後に資産を削除します。
Tumblr認証情報は従来どおりGitHub Secretsにだけ置き、ローカルへ複製しません。

```powershell
py -3 dispatch_local.py --dry-run
py -3 upload.py --media-audit
py -3 -m unittest -v test_dispatch_local.py test_pool_loader_contract.py
```

`upload.yml`の旧Google Drive定期実行は廃止し、ローカル選択からの
`workflow_dispatch`だけをライブ投稿経路にします。
