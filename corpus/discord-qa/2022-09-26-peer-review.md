# push_swapのレビュー項目（Simple version)で以下の記述がありますが、ARG=""の中に数字が何も入っていないのはおかしいのではないでしょう

**Source**: 42 Tokyo Discord, 2022-09-26  
**Tags**: peer-review, evaluation

## Q

こんばんは。
push_swapのレビュー項目（Simple version)で以下の記述がありますが、ARG=""の中に数字が何も入っていないのはおかしいのではないでしょうか？ひとつ前の項目から考えて、ARG="3 2 1"のように3つほど数字があるのが正しいと思います。
お手数ですがご確認お願いします。

```
- Run "$>ARG=""; ./push_swap
$ARG | ./checker_OS $ARG". Check that the checker program displays
"OK" and that the size of the list of instructions from push_swap
is between 0 AND 3. Otherwise the test fails.
```

## A

(@nop9166, staff): こんばんは。
`Run "$>ARG=""`　の部分が正しく表示されていないですね。
正しくは、`"$>ARG="<Between 0 and 3 randomly values chosen>"` なので修正します。
