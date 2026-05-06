# Intra Meta 校舎の外からgitリポジトリにアクセスする方法（オンライン学生専用）

### 設定方法

以下の設定を`.ssh/config`

の中に追記する。（XXXの値は、ご自身の環境に合わせて置き換えてください。）

```
Host vogsphere-v2.42tokyo.jp
User git
HostName vogsphere-v2.42tokyo.jp
ProxyCommand ssh -p 4242 -W %h:%p git@vgs-gw.42tokyo.jp
IdentityFile ~/.ssh/XXX
```

デフォルトのssh鍵を活用しない場合、以下の行を上記の設定のすぐ下に追記してください。

```
IdentitiesOnly yes
```

※ Intranetに新たな鍵をアップロードした場合、更新されるまで10ぷんほどお待ちください。
