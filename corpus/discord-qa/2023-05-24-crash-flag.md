# cpp08のex02（Mutated abomination）について、質問です。

**Source**: 42 Tokyo Discord, 2023-05-24  
**Tags**: peer-review, evaluation

## Q

cpp08のex02（Mutated abomination）について、質問です。
Evaluationの項目では||MutantStack is inherited from std::stack||と書いてあったのですが、これは適切な評価項目でしょうか？（細かい表現は覚えていないので曖昧です）

これが正しくないかもしれないと思う理由は下記です。
||STLのcontainerを継承をすべきでないと考える一番大きな理由は、STLのcontainerのデストラクタはvirtualで宣言されていないことです。例えば、下記のようなコードを実行した場合に、crashしてしまいます。このような機能追加などを行いたい場合には、通常はadaptorsなどのようにcompositionパターンを用いるのが適切ではないでしょうか。||

```
#include <iostream>
#include <stack>

template <typename T>
class MyStack: public std::stack<T> {
public:
 virtual ~MyStack() {
 std::cout << "~MyStack()" << std::endl;
 }
};

int main() {
 std::stack<int> *s = new MyStack<int>();
 s->push(1);
 delete s ; // This will cause memory leak and lead to crash
 return 0;
}
```

ちなみに、課題文には下記のように指示がありました。
> Write a MutantStack class. It will be implemented in terms of a std::stack.
> It will offer all its member functions, plus an additional feature: iterators.
||もし実装を簡単にするために継承を想定しているのであれば、通常は継承は適切ではないが、この課題では継承を使うように、という指示を課題に追記していただくのが良いではないでしょうか。||

## A

(@nop9166, staff): こんにちは。
報告ありがとうございます！
もう一度確認してみてください。
