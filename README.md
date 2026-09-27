# Tumblr動画自動投稿

定期投稿はGitHub Actions上で完結します。PCの起動・スリープ・Windowsタスクに依存しません。

## 現行の自動実行

`upload.yml`を02:00・14:00・20:00 JSTに定期実行します（GitHub側の実行遅延はあり）。
既存の公開Drive素材フォルダをgdown 6で列挙し、未投稿優先・既投稿なら最も古い素材から
1本だけ取得して投稿します。取得失敗時は最大3候補、投稿前の失敗は最大3試行。
認証情報とフォルダ設定はGitHub Secretsで保持し、値をログやPCに出しません。
素材なし・投稿失敗を成功扱いにせず、投稿結果不明の通信エラーは同じrunで再送しません。

`uploader-watchdog.yml`は毎日21:23 JSTに独立して起動します。
公開クラウドUploader 5リポジトリを監査し、Tumblr workflowが無効なら有効化します。
24時間以上投稿がなく、直近24時間にpublisher実行も進行中runもなければ1枠だけ補います。
定期設定が消えた場合もdaily dispatchで継続し、監査に異常を残します。
他の5リポジトリ（非公開1件を含む）は、それぞれの`uploader-watchdog.yml`で
毎日21:43 JSTに自己監査し、承認済みpublisherが無効なら自動で有効化します。
他リポジトリへの書込み権限や新しい認証情報は必要ありません。
BAN等で意図的に止めた媒体は監査対象に含めません。
毎日の実監査結果をコミットし、リポジトリ無活動によるschedule無効化も防ぎます。

`cloud_publisher.yml`は定期workflowの復旧用正本です。
ローカル素材の追加投稿用`dispatch_local.py`は残していますが、定期実行の必須経路ではありません。
旧Windows登録スクリプトを使って定期実行を重複させないでください。

```powershell
& 'C:\Users\atsus\AppData\Local\Python\pythoncore-3.14-64\python.exe' dispatch_local.py --dry-run
& 'C:\Users\atsus\AppData\Local\Python\pythoncore-3.14-64\python.exe' upload.py --media-audit
& 'C:\Users\atsus\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m unittest -v test_dispatch_local.py test_pool_loader_contract.py test_runtime_contract.py test_cloud_runtime.py
```

本番確認はGitHub Actionsの成功だけでなく、同じrun_idのposted_logにpost_idがあることを確認します。
