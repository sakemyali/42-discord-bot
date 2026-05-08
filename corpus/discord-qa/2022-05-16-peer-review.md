# go rush 02 の attachments にある sample.fillit の最後に改行がないです。

**Source**: 42 Tokyo Discord, 2022-05-16  
**Tags**: peer-review, evaluation

## Q

こんばんは。
go rush 02 の attachments にある sample.fillit の最後に改行がないです。
```
> cat -e sample.fillit 

....$
##..$
.##.$
....% 
```
PDF の `The description of a Tetriminos must respect the following rules :
Precisely 4 lines of 4 characters, each followed by a new line` 
と整合していないように見受けられます。

私たちのチームは、最後に改行がないファイルを error という扱いにしたのですが、レビュー項目で KO になりますか？

## A

(@tg_lazuli, staff): こんにちは。
ご報告ありがとうございます。
sample.fillitのファイルは間違ってます。
後ほど、最後の行に改行あるように修正します。
