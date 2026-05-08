# Go piscine rush 01

**Source**: 42 Tokyo Discord, 2022-05-06  
**Tags**: piscine

## Q

bonsoir, 
Go piscine rush 01 
 `Allowed packages : None`　とありますが、
command line arguments を扱うには `os` (または `flag` )が必要と思われます。

また、invalid arguments に以下は含みますか？
```
正方形でない ".2." "..."
'B'を置く余地がない "33" ".."
```

## A

(@nop9039, staff): こんばんは。
報告ありがとうございます。
`os` パッケージを `Allowed packages` に追加したのでご確認ください。
