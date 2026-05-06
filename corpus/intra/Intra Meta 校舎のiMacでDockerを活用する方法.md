# Intra Meta 校舎のiMacでDockerを活用する方法

### 1. Managed Software CenterからDockerをインストールする

ホームで3.5GB以上の容量を空けること。

Managed Software Centerを立ち上げること。

Dockerをインストールすること。

### 2. Dockerを設定する

Dockerを立ち上げること。

```
「Docker Desktop starting...」メッセージが永遠にロードされる場合、まずホームの容量を3.5GB以上空けます。その後に、Managed Software CenterからDockerを削除し、再インストールを実施してください。
```

右上のSettingsアイコンを選択すること。

以下のコマンドを実施し、Dockerが活用するイメージの保管場所を作成すること。

`$> mkdir /goinfre/あなたのログイン名/Docker`

ResourcesタブのAdvanced項目を開き、一番下のDisk image locationを

`/goinfre/あなたのログイン名/Docker`

に変更すること。

### 3. Dockerをテストする

- 以下のドキュメントをもとにDocker Composeを活用できるか確認すること。

https://docs.docker.com/compose/gettingstarted/

確認が完了した後のDocker Desktopは以下のような表示になります。
