# s/goinfreの容量がいっぱいになってきているようです？（恐らく）

**Source**: 42 Tokyo Discord, 2025-11-05  
**Tags**: goinfre, docker

## Q

s/goinfreの容量がいっぱいになってきているようです？（恐らく）
作業には今のこところ問題ないのですが、お耳にだけ入れさせてください。自分のせいでしたらすいません。

c6r3s14% df
/dev/mapper/ubuntu--vg-ubuntu--lv--goinfre 243042616 165129260 65521324 72% /goinfre
sgoinfre.42tokyo.jp:/srv/nfs4/sgoinfre 5367133184 5248641024 118492160 98% /sgoinfre

## A

(@alex42net, staff): ご報告ありがとうございます。
`/sgoinfre`が逼迫していましたので、ゴミ箱に入れられたデータおよびBHになった学生のデータを削除いたしました。
`c6r1`については、NW機器の電源ケーブルが抜けていると思われます。後ほど復旧に行きます。
