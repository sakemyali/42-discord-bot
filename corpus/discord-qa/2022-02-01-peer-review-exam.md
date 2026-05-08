# lsblkコマンドでパーティションの状態を確認したのですが

**Source**: 42 Tokyo Discord, 2022-02-01  
**Tags**: exam

## Q

(スタッフ宛) 
こんばんは。本日b2bのレビューを行なった際
lsblkコマンドでパーティションの状態を確認したのですが
その際出力された状態が課題pdf 5pの　You must create at least 2 encrypted partitions using LVM. Below is an example of the expected partitioning: 
の下に記載された例図のパーティション状態と異なっており、（bonusを行おうとしたが 途中でやめてmandatoryのみを行なったとのこと）私は課題pdfに記載されている例図通りのパーティション分割を行う必要があるものだと、解釈していたのですが、レビュイー側の言い分では、少なくとも２つの暗号化パーティションを作成する必要があり、例図と
同じにする必要はない。とのことで、意見が食い違ってしまったのですが、これはどちらが正しかったのでしょうか？今後のb2bのレビューの際の判断材料にもしたいので、何卒ご意見伺えればと思います。

## A

(@tg_lazuli, staff): こんにちは。
課題の例図はただ一つの例であり、完全に合わせる必要ありません。
```
You must create at least 2 encrypted partitions using LVM.
```
この要件を満たせば問題ありません。
