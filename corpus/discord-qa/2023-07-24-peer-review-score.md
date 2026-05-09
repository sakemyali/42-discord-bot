# cpp04のレビューで質問です。

**Source**: 42 Tokyo Discord, 2023-07-24  
**Tags**: peer-review, evaluation

## Q

さん
いつもありがとうございます。
cpp04のレビューで質問です。
オンライン学生同士のレビューをしたところ、レビュイーの提出したhppファイル内のclass定義に不使用の変数の宣言が存在したため、レビュワーである当方のMac（Darwin）およびワカモレ上では、
./Character.hpp:24:6: error: private field 'count' is not used [-Werror,-Wunused-private-field]
のエラーが出ました。

しかし一方で、レビュイーのWSL環境（Ubuntu）や、レビュワーの42VM環境（Ubuntu）では、コンパイラの違いからエラーとならずに正常にビルドされます。レビュイーは自身の環境において開発時にエラーが出なかったために気付かなかったようです。

この場合、評価ではどのように採点すべきでしょうか？
・42VMで問題ないのでOKとする
・ワカモレでエラーが出るのでKOとする（invalid compilationフラグ）
・それ以外

余談：
レビュイー提出のMakefileのコンパイラ指定はc++となっており、これはpdfの指定と合致しているのですが、Darwinではclang++が、Linuxではg++が呼ばれるために今回のように挙動が異なる場合が出てきてしまいます。MacとLinux環境で挙動を合わせるならばc++ではなくclang++を指定するようにした方がよいと個人的には思っています。

## A

(@nop9166, staff): こんにちは。
42VMで問題ないのでOKとします。
