# 1. 「ステータス投稿APIの実装」の「Functionality Check」において、mysqlコンテナの中で、mysqlにてクエリを実行する指示があります

**Source**: 42 Tokyo Discord, 2022-05-11  
**Tags**: road-to

## Q

(スタッフ宛) 同じく「Road-to-DMM-Botcamp-Go」のレビュー項目について、ミス(?)の報告です。
1. 「ステータス投稿APIの実装」の「Functionality Check」において、mysqlコンテナの中で、mysqlにてクエリを実行する指示があります。そこでは日本語入力を求められていますが、提供されたリソースをそのまま用いた場合、コンソール経由で日本語入力を正しく行えず、テストを正常に実行できないため、コマンドの例示として不適切だと思います。(もちろん、生徒がmysqlコンテナで日本語入力対応をすべきであるのであれば別ですが、subjectにはその点について明記されていませんでした)
2. 「ユニットテストの追加」の「Implementation Check」において、`app/handler`の中でテストを行うように指示がありますが、「はい(Yes)」を選択する要件として「`dao`や`handler`でテストが実行された場合」とされています。`handler`ディレクトリの中で`dao`の中のテストは実行できないため、要件、あるいは指示のいずれかが不適切だと思います。
3. 「media機能の実装」の「Implementation Check」において、「`アカウント情報更新APIの実装：POST ​/accounts​/update\_credentials`」のように`update\_credentials`のところにバックスラッシュが残っています。
4. 「media機能の実装」の「Implementation Check」において、不要な「`v1/`」がパスに含まれているものがあります。
5. Ratingsのフラグ選択にて、グループ課題ではないのに「Incomplete group」が表示されています。

## A

(@nop9039, staff): こんにちは。
報告ありがとうございます。

> 1. 「ステータス投稿APIの実装」の「Functionality Check」において、mysqlコンテナの中で、mysqlにてクエリを実行する指示があります。そこでは日本語入力を求められていますが、提供されたリソースをそのまま用いた場合、コンソール経由で日本語入力を正しく行えず、テストを正常に実行できないため、コマンドの例示として不適切だと思います。(もちろん、生徒がmysqlコンテナで日本語入力対応をすべきであるのであれば別ですが、subjectにはその点について明記されていませんでした)
テスト内容を日本語から英語に変更しました。

> 2. 「ユニットテストの追加」の「Implementation Check」において、app/handlerの中でテストを行うように指示がありますが、「はい(Yes)」を選択する要件として「daoやhandlerでテストが実行された場合」とされています。handlerディレクトリの中でdaoの中のテストは実行できないため、要件、あるいは指示のいずれかが不適切だと思います。
`「daoやhandlerでテストが実行された場合」` の部分を `「daoやhandleのテストが実行された場合」` 　に修正しました。

> 3. 「media機能の実装」の「Implementation Check」において、「アカウント情報更新APIの実装：POST ​/accounts​/update\_credentials」のようにupdate\_credentialsのところにバックスラッシュが残っています。
`\` を削除しました。

> 4. 「media機能の実装」の「Implementation Check」において、不要な「v1/」がパスに含まれているものがあります。
`v1/` の部分を削除しました。

> 5. Ratingsのフラグ選択にて、グループ課題ではないのに「Incomplete group」が表示されています。
「Incomplete group」のフラグを削除しました。
