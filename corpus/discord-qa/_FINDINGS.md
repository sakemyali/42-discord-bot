# Discord Q&A — extraction findings

Source: `Q&A/Discord_chat_*.csv` (5342 rows, 1051 question rows, 251 accepted)  
Date range: 2022-01-02 → 2026-05-08  
Verified staff handles: @2destiny, @42staff_01, @alex42net, @footanaka_42staff, @kitamura_shoko, @naganoyu9442, @nop9039, @nop9166, @sataharu, @shotakaki_43114, @tg_lazuli

Staff verification used three independent signals: (1) staff-style language frequency ("対応しました", "修正しました", "42Networkと確認中", etc.), (2) ratio of answers to questions asked (≥98% answers), and (3) actions only staff can perform (modifying intra scores, BH extension, adding allowed functions).

## Summary

- 251 markdown files written under `corpus/discord-qa/`
- Filtering criteria: question must fall in a KEEP bucket, answer must come from verified staff (Mentions-the-asker up to 72h later, OR within 90min of the question), and the answer must be substantive (not just "確認中です").
- Bucket-level summary below; raw drop counters at end.

## Topic index

### ピアレビュー / レビュー (63 docs)
What it answers: edge cases in flag selection, dispute resolution, repeated-reviewer handling, point/score corrections, defense logistics.

- [スロットを開けたところ、同じ方のレビューが続けて入りました。](2022-01-19-peer-review.md)
- [レビュー項目にないとき、上記のコマンドを実行してsegvやabortが起きたとして、Clashフラグをたてるべきでしょうか？](2022-01-21-peer-review-review-flag.md)
- [納得していないのに勝手に点数を低く付けられてしまったのですが](2022-02-03-peer-review-score.md)

Status: clarifies `corpus/intra/Intra Meta ピアレビューについて.md`, `corpus/intra/Intra Meta 【レビューキャンペーン】ルーブリック.md`, `corpus/intra/the_art_of_peer_evaluation.en.md`.

### BlackHole / Freeze / AGU (20 docs)
What it answers: 校舎 use during AGU, BH-extension semantics, level-up vs project-clear gating, AGU↔Freeze interaction.

- [メンション失礼致します。AGUの取得期間中の校舎利用に関する認識についてお伺いしたいです。「できるもの」「できるがすべきでないもの」「できな…](2022-01-15-agu-cluster.md)
- [TIG日付を設定したら、](2023-01-18-agu.md)
- [give upからのretryで新規のリポジトリつくってもだめですか？](2023-02-21-blackhole.md)

Status: extends `corpus/intra/15.md` (BlackHole) and AGU/Freeze rules; many of these are *new* edge cases not in the static corpus.

### Exam / 試験 (30 docs)
What it answers: which attempt counts toward XP, retake mechanics, exam-mode subjects, .cpp auto-grader behaviour.

- [lsblkコマンドでパーティションの状態を確認したのですが](2022-02-01-peer-review-exam.md)
- [Go piscine rush 02 pdf](2022-05-13-score-piscine.md)
- [昨日アナウンスメントされたPiscine Examの運営ボランティア（ ）について質問です。](2022-08-09-piscine-exam-https.md)

Status: clarifies `corpus/intra/Intra Meta 試験規則.md`.

### Discord ルール (6 docs)
What it answers: where to post bug reports, who to mention, escalation patterns.

- [これは、あくまで予想なので合ってるかどうかはわかりませんが、dmmが土日祝休みだから厳しいんじゃないですかね？](2022-11-14-dmm.md)
- [intra-verifyについての質問・提案です。](2023-02-16-blackhole.md)
- [以下のテキストチャンネルが削除またはプライベート化されたようなのですが、](2023-02-22-https-discord-com.md)

Status: extends `corpus/intra/42 Tokyo Discordの利用ポリシー.md`.

### Piscine (24 docs)
What it answers: C↔Go Piscine differences, 42cursus transition, achievement bonuses.

- [校舎にいるのですが、ピシン生がスピーカーをオンにするのはtigではないのでしょうか？](2022-02-18-piscine-cluster.md)
- [Go Piscine 01の課題PDFについて質問(?)です。](2022-04-25-piscine-pdf-ex01.md)
- [Go Picsine 05について質問です。](2022-04-26-picsine-make-append.md)

Status: extends Piscine and Reloaded notes; primarily *new* operational detail.

### Norminette (4 docs)
What it answers: norm exceptions, 42header per file type, post-merge norm errors.

- [go pisicne](2022-04-26-peer-review.md)
- [fdfのレビューにおいてレビュワー側がワカモレでnorminette(ver. 3.3.2)を実行したところ、下記エラーが出ました。](2022-11-30-peer-review-norminette-2.md)
- [norminette が runtime error になるときの対症療法としては、error の原因と言われている箇所の直前を括弧でくくっ…](2024-05-14-norminette.md)

Status: clarifies `corpus/intra/Intra Meta [Norminette] 42Headerのメアドを設定する方法.md`.

### Common Core / 42cursus (4 docs)
What it answers: registration conflicts (libft vs libft-0X), curriculum state machine, achievement counters, score/percent updates.

- [3ヶ月ほど前に、ft_communication_v2 の課題に登録してからずっと以下のような画面のままレビューを受けることができません。](2022-10-11-peer-review-registration.md)
- [libasm に登録できなくなっているのですが、表示される](2025-12-23-common-core-registration.md)
- [Hi, Anthony. Happy New Yer.](2026-01-04-anthony-happy-new.md)

Status: operational *new* detail on registration and course state machine.

### Cluster / iMac / 校舎 (78 docs)
What it answers: 学生証 issuance, building access, iMac assignment.

- [本日学生証受け取り予定でしたが電車遅延のため申し訳ないのですが間に合いません](2022-01-18-intra-card.md)
- [校舎に置くための本を六本木グランドタワー23階宛に配達してもらっても大丈夫でしょうか？](2022-03-23-cluster.md)
- [六本木オフィスに入るための学生証はどちらから発行できますでしょうか？](2022-03-27-intra-card.md)

Status: extends campus-rule notes (`corpus/intra/Intra Meta キャンパス全体ルール.md`, etc.).

### Intra / Intranet (7 docs)
What it answers: intranet UI/state quirks, vogsphere git semantics, password rules.

- [先日購入した下記アイテムが反映されず困っております。(フォーム回答してからある程度の日数待つ必要ありますかね？)](2022-10-29-blackhole.md)
- [イントラネームsatushiさんに42boulderingロールを付与していただけますか？](2023-02-20-satushi-bouldering-satushi.md)
- [イベント楽しみでしたが、遠方でしたので、キャンセルさせていただきます。](2023-02-27-question.md)

Status: operational fixes/clarifications around the intranet (mostly *new*).

### Goinfre / Docker / Guacamole (6 docs)
What it answers: VM disk-space, Docker engine version, Guacamole environment.

- [guacamoleでレビューする際、環境変数を変更/削除してからプログラムを実行しても問題ないでしょうか？](2022-01-21-peer-review-guacamole.md)
- [Inceptionの要件について質問です。](2022-08-30-docker-common-core.md)
- [sgoinfreっていつ使えるようになりますか？](2023-06-05-goinfre.md)

Status: *new* operational detail not in the static corpus.

### 退学 / 在籍 / 申請 (1 docs)
What it answers: student-status changes, reinstatement.

- [こちらのイベントの参加特典「42Tokyoの継続在籍」について、これは「BHにかかわらず継続して在籍できる」という意味でしょうか?](2024-06-14-withdrawal-blackhole.md)

Status: extends `corpus/intra/Intra Meta 退学の申請方法.md`.

### Bocal / Pedago / Staff (3 docs)
What it answers: operational follow-ups for individual cases.

- [Is there any staff today? We are waiting in front of bocal to get the …](2024-05-25-bocal.md)
- [トラセンを旧過程にて進めています。レビューにおいては、ボーカルに旧課程使用の故、事前連絡が必要とのことですが、以下の点を質問させてください。](2025-05-22-peer-review-matchmaking.md)
- [1. とらせんの場合、チームが５名と日程調整の難易度が上がっており、かつ、社会人もメンバーにいるために、対面レビューはボーカルの閉まる週末と…](2025-05-22-peer-review-cluster.md)

Status: *new* operational detail.

### Reloaded / Road to (4 docs)
What it answers: Reloaded-specific clarifications and Road-to-X programs.

- [Road to Mercari module 02 の問題文( についてですが,](2022-05-15-peer-review.md)
- [road to mercariでgoのバージョン1.16の指定はなくして最新版にした方がいいと思うのですが、いかがでしょうか？](2022-09-15-road-mercari-road-to-mercari.md)
- [road to のレビューマッチング条件について、ご対応を検討頂けると幸いです。](2023-11-01-peer-review-matchmaking.md)

Status: *new* operational detail.

### Slack / 42born2code (1 docs)
What it answers: interaction with the global 42 Slack.

- [42urdulizでも18時にイベントについて言及があるので、18時開催のように思います。](2022-06-13-registration-slack.md)

Status: *new* operational detail.

## Skipped

- 433 — bucket: unbucketed
- 222 — no staff answer
- 42 — answer too short
- 28 — bucket: project (drop)
- 25 — all answers are holding-pattern
- 20 — manual skip-list
- 10 — drift: answer references specific time slot
- 5 — PII in all staff answers
- 4 — pii: question
- 2 — drift: answer references @kkohki (≠asker @kouki485)
- 1 — filler-only answer
- 1 — drift: project mismatch (Q=['term3d'] A=['cpp04'])
- 1 — drift: answer references @ksuzuki (≠asker @kota_s)
- 1 — drift: answer references @shopでTシャツを購入した皆 (≠asker @mfunyu)
- 1 — drift: project mismatch (Q=['ft_transcendence', 'transcendence'] A=['cpp09', 'ft_containers'])
- 1 — drift: answer references @raosmona (≠asker @razak_osmonaliev)
- 1 — drift: answer references @hinakaza (≠asker @kebin_rn)
- 1 — drift: answer references @ttsubo (≠asker @cacapon)
- 1 — drift: answer references @tasugiya (≠asker @.cre5t)

## Open questions for the user

- **Senior-student answers excluded**: kept only verified-staff replies. Some senior students (snara, yokawada, nfukuma) regularly post correct, well-sourced answers. They were excluded conservatively. If you want their answers folded in, say so and I'll re-run with an extended allowlist.
- **Stale operational facts**: a few BH/AGU answers from 2022 may have been superseded by 2024+ rule revisions. The bot may now answer with outdated rule clauses. Spot-check the BH/AGU bucket if students rely on it.
- **Ambiguous redactions**: messages mentioning specific intra logins (not real names) were kept — they're already entities in the graph and carry no real-world identity by themselves.