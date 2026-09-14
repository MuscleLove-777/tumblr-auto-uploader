# Tumblr動画自動投稿

本番の動画正本は`../000_Tumblr_movie`です。直下と全サブフォルダを再帰走査し、
同一バイトのコピーだけSHA-256でまとめます。別の承認台帳は使いません。

## 現行の自動実行

Windowsタスクが`dispatch_local.py`を1日3回起動します。未投稿の動画を最優先し、
全種類を一巡するまで同じ動画を再利用しません。選ばれた1本だけを短時間の
GitHub Release資産としてGitHub Actionsへ渡し、Tumblr投稿後に資産を削除します。
Tumblr認証情報は従来どおりGitHub Secretsにだけ置き、ローカルへ複製しません。

```powershell
& 'C:\Users\atsus\AppData\Local\Python\pythoncore-3.14-64\python.exe' dispatch_local.py --dry-run
& 'C:\Users\atsus\AppData\Local\Python\pythoncore-3.14-64\python.exe' upload.py --media-audit
& 'C:\Users\atsus\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m unittest -v test_dispatch_local.py test_pool_loader_contract.py test_runtime_contract.py
```

`upload.yml`の旧Google Drive定期実行は廃止し、ローカル選択からの
`workflow_dispatch`だけをライブ投稿経路にします。

Windowsタスク`MuscleLove_Tumblr_LocalDispatch`は02:00・14:00・20:00 JSTに実行します。
登録スクリプトは初回境界を必ず未来時刻に置き、復旧時の即時重複投稿を防ぎます。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install_scheduled_task.ps1
```
