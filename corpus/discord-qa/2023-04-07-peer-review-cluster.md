# 手元のレビュー項目のスクリーンショットを見ると、**test2とtest0を比較する**、と書かれているように見えますが、test2とtest1なのでしょうか？

**Source**: 42 Tokyo Discord, 2023-04-07  
**Tags**: peer-review, evaluation

## Q

手元のレビュー項目のスクリーンショットを見ると、**test2とtest0を比較する**、と書かれているように見えますが、test2とtest1なのでしょうか？
"Qualify of the free function"という名前の項目なのですが。

## A

(@nop9166, staff): おっと、"Tests of free" という名前の項目を確認していました。
yokawadaさんがレビューを実施した際、どれほど値がずれていましたか？
それと実施した環境の共有をお願いします。

校舎のiMac(OS Mojave)だと5pageほどずれるので、レビューの項目通りになっています。
```
c1r7s1% gcc -o test0 test0.c && /usr/bin/time -l ./test0 2>&1 | grep "page reclaims"
 193 page reclaims
c1r7s1% gcc -o test2 test2.c && /usr/bin/time -l ./test2 2>&1 | grep "page reclaims"
 198 page reclaims
```
