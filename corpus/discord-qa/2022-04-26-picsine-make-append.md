# Go Picsine 05について質問です。

**Source**: 42 Tokyo Discord, 2022-04-26  
**Tags**: piscine

## Q

(スタッフ宛) 
Go Picsine 05について質問です。

組み込み関数make, appendのどちらかまたは両方を使用しない場合
実装が困難であるような課題があるように思われ、
またPDFにもそれらの関数の使用を示唆する文面がありますが、
課題の`Allowed builtin functions`はすべて`None`になっています。

この状況の解釈として、以下のどれが正しいでしょうか？

(1) `Allowed builtin functions: None`なら、課題を問わずmakeもappendも使用禁止
(2) `make`, `append`は`Allowed builtin functions`とみなさない(=Go Piscine 05に限らず常に使用可能)。
(3) Go Piscine 05でのみ、`make`と`append`を使用可能(課題で禁止されている場合を除く)。
(4) 上記以外。

## A

(@tg_lazuli, staff): こんにちは。
ご報告ありがとうございます。
Go Piscine Go 05の課題の `Allowed builtin functions` をmakeとappendを許可するように変更しました。
