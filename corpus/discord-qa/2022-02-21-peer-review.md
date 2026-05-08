# - subject.pdf には `use cc` とあるが、レビュイーの提出した Makefile では`clang` でコンパイルしている

**Source**: 42 Tokyo Discord, 2022-02-21  
**Tags**: peer-review, evaluation

## Q

(スタッフ宛) ft_printf のレビューについての質問です。
- subject.pdf には `use cc` とあるが、レビュイーの提出した Makefile では`clang` でコンパイルしている
- レビュイーの提出した Makefileには `clean fclean re` のルールはあるが機能していない
```
c1r14s2% make re
/Applications/Xcode.app/Contents/Developer/usr/bin/make -C clean
make: *** clean: No such file or directory. Stop.
make: *** [clean] Error 2
```
この場合の評価はinvalid compilation ですか？
なぜ質問したかというとsubject.pdfに記載されている`Your Makefile must at least contain the rules $(NAME), all, clean, fclean and re.` からルールがあれば機能しなくてもいいというレビュイーの意見とレビュー項目にはコンパイラ、Makefileについての記載がなかったからです。

## A

(@tg_lazuli, staff): こんにちは。
Makefileの用件が満たしていない場合は、Invalid compilationとなります。
レビュー項目にMakefileの記載がない問題は修正しますので、ご報告ありがとうございます！
