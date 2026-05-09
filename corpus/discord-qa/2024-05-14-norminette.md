# norminette が runtime error になるときの対症療法としては、error の原因と言われている箇所の直前を括弧でくくったりすると解決するこ

**Source**: 42 Tokyo Discord, 2024-05-14  
**Tags**: norminette

## Q

norminette が runtime error になるときの対症療法としては、error の原因と言われている箇所の直前を括弧でくくったりすると解決することがあります。
```cpp
constructor().func(1, 2); // error
(constructor().func)(1, 2); // ok?
```

## A

(@nop9166, staff): こんにちは。
確認するので少々お待ちを。
