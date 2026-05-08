"""Mine the 42 Tokyo Discord Q&A CSV into curated markdown for LightRAG ingest.

Pipeline:
  1. Load CSV (utf-8-sig BOM, comma-in-date column)
  2. Sort by datetime
  3. For each question (?/？), find candidate answers in the next 90 minutes
     from a different author who either mentions the asker or replies in-window.
     Pick the first verified-staff answer if present; otherwise drop.
  4. Bucket each kept Q&A by topic. Drop "Project" bucket per task spec.
  5. Strip Discord-mention noise, replace staff-role mention with (スタッフ宛),
     drop messages that include personal-identity PII.
  6. Emit one markdown file per kept thread under corpus/discord-qa/.
  7. Write _FINDINGS.md summarising the run.

Run:
  .venv/bin/python scripts/mine_discord_qa.py [--limit N]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Mine ALL Discord_chat_*.csv dumps in Q&A/ — different dumps cover different
# channels (academic Q&A vs facilities/Discord-rules), and the bot benefits
# from both. Dedup is handled by (date, username, content) tuple.
CSV_PATHS = sorted((REPO / "Q&A").glob("Discord_chat_*.csv"))
if not CSV_PATHS:
    raise SystemExit("No Q&A/Discord_chat_*.csv found")
OUT_DIR = REPO / "corpus" / "discord-qa"

# Staff role mention id, surfaced via spec
STAFF_ROLE_ID = "691904024940904460"
STAFF_ROLE_TOKEN = f"<@&{STAFF_ROLE_ID}>"

# Verified staff allowlist (see _FINDINGS.md for evidence). Two dump-channel
# views surface slightly different staff cohorts:
#   - academic Q&A channel: tg_lazuli, alex42net, nop9166, nop9039, 2destiny
#   - facilities / Discord-rules channel: sataharu, footanaka_42staff,
#     naganoyu9442, kitamura_shoko, shotakaki_43114
# Plus 42staff_01, the announcement account, present in both.
STAFF = {
    "tg_lazuli", "alex42net", "nop9166", "nop9039", "2destiny", "42staff_01",
    "sataharu", "footanaka_42staff", "naganoyu9442", "kitamura_shoko",
    "shotakaki_43114",
}

# Outer window — only relevant for the proximity fallback. Staff often reply
# hours or days later, but those late replies are reliable ONLY when the
# Mentions field names the asker.
PROXIMITY_FALLBACK_MIN = 90       # used when Mentions doesn't name the asker
DIRECTED_WINDOW_HRS = 72          # staff Mentions-the-asker is reliable up to here
FAST_FOLLOWUP_MIN = 30            # continuation by same author
MIN_Q_CHARS = 25

# Bucket keyword priority — earlier wins. Project-bucket placed last so it
# only catches Qs that don't fit a higher-value bucket. We drop that bucket.
BUCKETS = [
    ("blackhole-freeze-agu",
     "BlackHole / Freeze / AGU",
     ["blackhole", "black hole", "ブラックホール", "ブラホ", "freeze", "フリーズ",
      "AGU", " agu", "コンペンセ", "compensation", "compensate", "凍結",
      "BHを", "BHが", "BHの", "ブラックホール延長"]),
    ("exam",
     "Exam / 試験",
     ["試験", "exam", "エグザム", "examrank", "exam rank", "auto-grade",
      "オートグレード", "再試験", "リトライ", "retake", "受験"]),
    ("piscine",
     "Piscine",
     ["piscine", "ピシン", "ピッシン", "ピシーン", "reloaded", "リローデッド",
      "achievement bonus", "アチーブメント"]),
    ("norminette",
     "Norminette",
     ["norminette", "ノルミネット", "ノルム", " norm ", "norm規則",
      "42header", "42ヘッダー"]),
    ("cluster-imac",
     "Cluster / iMac / 校舎",
     ["clust", "cluster", "クラスタ", "imac", "校舎", "学生証",
      "intra card", "intracard", "セキュリティカード", "ロッカー", "locker",
      "入館証", "学校", "schoolhouse"]),
    ("intra",
     "Intra / Intranet",
     ["intra ", "intranet", "イントラ", "vogsphere", "deepthought"]),
    ("goinfre-docker",
     "Goinfre / Docker / Guacamole",
     ["goinfre", "ゴインフレ", "docker", "ドッカー", "guacamole", "グァカモレ", "vm "]),
    ("withdraw",
     "退学 / 在籍 / 申請",
     ["退学", "在籍", "離籍", "drop out", "dropout", "停学", "withdraw"]),
    ("bocal-pedago-staff",
     "Bocal / Pedago / Staff",
     ["bocal", "pedago", "ペダゴ", "ボーカル", "Pedago"]),
    ("road-to",
     "Reloaded / Road to",
     ["reloaded", "road to", "リローデ", "ロードトゥ"]),
    ("job",
     "求人 / Job",
     ["求人", " job ", "求職", "就職", "intern", "インターン"]),
    ("slack",
     "Slack / 42born2code",
     ["slack ", " slack", "42born2code", "born2code"]),
    ("common-core",
     "Common Core / 42cursus",
     ["common core", "コモンコア", "42cursus", "cursus", "カーサス",
      "カリキュラム", " libft ", "登録できない", "unregister",
      "registration", "課題に登録"]),
    ("discord-rules",
     "Discord ルール",
     ["#bug-report", "bug-report", "バグレポ", "bug report", "channel ",
      "チャンネル", "ピング", "ping ", "メンション", "discord-rule"]),
    ("peer-review",
     "ピアレビュー / レビュー",
     ["レビュー", "ピアレビ", "evaluation", "evaluator", "evaluated",
      "リビュー", "リビュ", "evalpoint", "eval point", "ルーブリック",
      "フラグ", "flag", "クラッシュ", "crash", "チート", "cheat",
      "incomplete", "empty ", "ディフェンス", "defense", "防衛",
      "点数", "採点", "スコア", "減点", "加点", "得点"]),
    ("project-DROP",
     "Project (drop)",
     ["philosopher", "フィロ", "philo", "minishell", "ミニシェル",
      "ft_print", "printf ", "get_next_line", "gnl", "push_swap",
      "fract-ol", "fractol", "ft_irc", "minirt", "cub3d",
      "netpractice", "transcendence", "inception", "ft_containers",
      "webserv", "born2beroot", "born2be", "so_long", "Makefile",
      "makefile", "make ", "relink"]),
]
DROP_BUCKETS = {"project-DROP"}

# Manual skip-list for cross-thread drift cases that survive the automatic
# filters. Each entry is the generated filename. Keeping a list here means
# re-runs reproduce the curated state.
MANUAL_SKIP = {
    # KIRIN internship BH question; staff answer is about T-shirt color
    # (batch-reply bleed)
    "2024-12-09-internship-blackhole.md",
}

# PII detectors — drop a message entirely if it surfaces personal identity.
PII_RE = [
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # email
    re.compile(r"\b0\d{1,4}-?\d{1,4}-?\d{4}\b"),  # JP phone
    re.compile(r"\b\d{3}-?\d{4}-?\d{4}\b"),  # mobile
]

# Discord ID mention <@!1234567890> or <@1234567890> — strip silently
USER_MENTION_RE = re.compile(r"<@!?(\d+)>")
ROLE_MENTION_RE = re.compile(r"<@&(\d+)>")
URL_RE = re.compile(r"https?://\S+")
WHITESPACE_RE = re.compile(r"[ \t]+")
MULTILINE_RE = re.compile(r"\n{3,}")

ENGLISH_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "for", "is", "are", "and", "or",
    "with", "on", "at", "by", "be", "this", "that", "it", "if", "as",
}

# slug seed map — Japanese topic → short English slug stub used in filenames
SLUG_HINTS = [
    (("AGU", "agu"), "agu"),
    (("BlackHole", "BH ", "BHを", "BHの", "ブラックホール"), "blackhole"),
    (("Freeze", "freeze", "フリーズ"), "freeze"),
    (("レビュー", "ピアレビ", "review", "evaluation"), "peer-review"),
    (("点数", "スコア", "採点", "減点"), "score"),
    (("フラグ", "flag"), "review-flag"),
    (("チート", "cheat"), "cheat"),
    (("クラッシュ", "crash"), "crash-flag"),
    (("試験", "exam", "examrank"), "exam"),
    (("ノルミネット", "norminette", "ノルム", " norm "), "norminette"),
    (("42Header", "42header", "42ヘッダー"), "42header"),
    (("piscine", "ピシン"), "piscine"),
    (("Reloaded", "reloaded"), "reloaded"),
    (("学生証", "intra card", "セキュリティカード"), "intra-card"),
    (("校舎", "クラスター", "cluster"), "cluster"),
    (("docker", "Docker", "ドッカー"), "docker"),
    (("guacamole", "Guacamole"), "guacamole"),
    (("Goinfre", "goinfre"), "goinfre"),
    (("Common Core", "common core", "コモンコア"), "common-core"),
    (("libft",), "libft"),
    (("登録",), "registration"),
    (("Bocal", "bocal"), "bocal"),
    (("退学", "在籍"), "withdrawal"),
    (("インターン", "intern"), "internship"),
    (("Slack", "slack"), "slack"),
    (("bug", "バグ"), "bug-report"),
    (("マッチ", "match"), "matchmaking"),
    (("BH", "BlackHole"), "blackhole"),
]


def parse_date(s: str) -> dt.datetime:
    # CSV uses "YYYY-MM-DD,HH:MM:SS" (comma between date and time)
    s = s.strip().strip('"')
    s = s.replace(",", " ", 1)
    return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def load_rows() -> list[dict]:
    """Load and merge all Discord CSV dumps, deduping on (datetime, user, content)."""
    seen: set[tuple] = set()
    rows = []
    for path in CSV_PATHS:
        with open(path, encoding="utf-8-sig", newline="") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                try:
                    r["_dt"] = parse_date(r["Date"])
                except Exception:
                    continue
                key = (r["_dt"], r["Username"], r["Content"][:120])
                if key in seen:
                    continue
                seen.add(key)
                r["_source_csv"] = path.name
                rows.append(r)
    rows.sort(key=lambda r: r["_dt"])
    return rows


def is_question(content: str) -> bool:
    return "?" in content or "？" in content


def has_pii(text: str) -> bool:
    return any(p.search(text) for p in PII_RE)


def clean_content(text: str) -> str:
    text = USER_MENTION_RE.sub("", text)
    text = ROLE_MENTION_RE.sub(
        lambda m: "(スタッフ宛)" if m.group(1) == STAFF_ROLE_ID else "",
        text,
    )
    text = URL_RE.sub("", text)
    text = WHITESPACE_RE.sub(" ", text)
    text = MULTILINE_RE.sub("\n\n", text)
    return text.strip()


def bucket_of(text: str) -> tuple[str, str]:
    tl = text.lower()
    for slug, label, kws in BUCKETS:
        for kw in kws:
            if kw.lower() in tl:
                return slug, label
    return "unbucketed", "(unbucketed)"


def slug_topic(content: str) -> str:
    """Pick a 1-2 word stub from Japanese content for filename."""
    hits = []
    for triggers, stub in SLUG_HINTS:
        for t in triggers:
            if t in content:
                hits.append(stub)
                break
    seen = set()
    out = []
    for h in hits:
        if h in seen:
            continue
        seen.add(h)
        out.append(h)
        if len(out) >= 2:
            break
    if not out:
        # Fall back to first few ASCII words from content
        words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", content)
        words = [w.lower() for w in words if w.lower() not in ENGLISH_STOPWORDS]
        out = words[:3] if words else ["question"]
    return "-".join(out)[:40]


def find_thread(rows: list[dict], q_idx: int) -> list[dict] | None:
    """Return [Q, asker-followups..., A1, A2] or None if no staff answer.

    Two reliable reply signals — used in priority order:
      1. directed: a staff message whose Mentions field names the asker.
         Reliable up to DIRECTED_WINDOW_HRS later (median delay is ~3h,
         90th-pctile ~37h, so we need a wide window).
      2. proximity: a staff message within PROXIMITY_FALLBACK_MIN of the
         question time, even without an explicit mention. Used only as
         a fallback when no directed reply exists.

    Asker's own follow-ups within FAST_FOLLOWUP_MIN of the prior thread
    message extend the thread (clarifications). Continuation answers by
    the same staff member within FAST_FOLLOWUP_MIN of the first answer
    are folded in as A2.
    """
    q = rows[q_idx]
    qauthor = q["Username"]

    if qauthor in STAFF:
        return None
    qtext_for_len = q["Content"].replace(STAFF_ROLE_TOKEN, "").strip()
    if len(qtext_for_len) < MIN_Q_CHARS:
        return None
    body_lines = [ln for ln in q["Content"].splitlines() if ln.strip()]
    if body_lines and all(ln.lstrip().startswith(">") for ln in body_lines):
        return None

    qtime = q["_dt"]
    directed_deadline = qtime + dt.timedelta(hours=DIRECTED_WINDOW_HRS)
    proximity_deadline = qtime + dt.timedelta(minutes=PROXIMITY_FALLBACK_MIN)

    # Phase 1 — locate the first staff reply.
    primary_idx = None
    primary = None
    for j in range(q_idx + 1, len(rows)):
        m = rows[j]
        if m["_dt"] > directed_deadline:
            break
        if m["Username"] not in STAFF:
            continue
        directed = qauthor in (m.get("Mentions") or "")
        close = m["_dt"] <= proximity_deadline
        if directed or close:
            primary_idx = j
            primary = m
            break

    if primary is None:
        return None

    # Phase 2 — collect asker follow-ups BETWEEN the question and the staff
    # reply (clarifications), provided they're each close to the previous
    # thread message.
    asker_followups: list[dict] = []
    last_thread_ts = qtime
    for j in range(q_idx + 1, primary_idx):
        m = rows[j]
        if m["Username"] != qauthor:
            continue
        if (m["_dt"] - last_thread_ts) <= dt.timedelta(minutes=FAST_FOLLOWUP_MIN):
            asker_followups.append(m)
            last_thread_ts = m["_dt"]

    # Phase 3 — fold a continuation message ONLY if (a) same staff author,
    # (b) within FAST_FOLLOWUP_MIN of primary, AND (c) it doesn't itself
    # @-mention a third party (which would mark it as answering a different
    # question in batch-reply mode).
    staff_answers = [primary]
    last_answer_ts = primary["_dt"]
    for j in range(primary_idx + 1, len(rows)):
        m = rows[j]
        if (m["_dt"] - last_answer_ts) > dt.timedelta(minutes=FAST_FOLLOWUP_MIN):
            break
        if m["Username"] != primary["Username"]:
            if m["Username"] != qauthor:
                break
            continue
        # Continuation must NOT be addressed to anyone else
        m_mentions = (m.get("Mentions") or "").strip()
        if m_mentions and qauthor not in m_mentions:
            break
        staff_answers.append(m)
        last_answer_ts = m["_dt"]

    return [q] + asker_followups + staff_answers


def thread_quality(thread: list[dict], q_bucket_slug: str) -> str | None:
    """Drop low-value threads.

    Filters:
      - no staff answer
      - answer too short (<25 chars stripped)
      - all answers are holding-patterns ("確認中です", "お待ちください")
      - drift: answer talks about a specific time slot (e.g. "09:30〜") but
        the question is about general rules. Specific-time replies are
        almost always operational ("I replaced your 09:30 review") and
        don't generalise.
    """
    answer_msgs = [m for m in thread[1:] if m["Username"] in STAFF]
    if not answer_msgs:
        return "no staff answer"
    joined_a = " ".join(m["Content"] for m in answer_msgs)
    if len(joined_a.replace(" ", "")) < 20:
        return "answer too short"
    if all(
        re.search(r"わかりません|分かりません|現在確認中|確認中です|お待ちください",
                  a["Content"]) and len(a["Content"]) < 80
        for a in answer_msgs
    ):
        return "all answers are holding-pattern"
    # Filler-only answer: "対応しました" / "確認しました" / "報告ありがとうございます" /
    # "本来であれば登録できません" (which we saw cross-attributed) without anything
    # else. These don't carry rule content.
    stripped = re.sub(r"こんにちは。?|こんばんは。?|お疲れさまです。?|"
                      r"お疲れ様です。?|よろしくお願い(?:いたします|します|致します)。?|"
                      r"ご確認ください。?|ご確認下さい。?|報告ありがとうございます[!！。]?|"
                      r"ご報告ありがとうございます[!！。]?|お問い合わせありがとうございます[!！。]?|"
                      r"\s+", "", joined_a)
    FILLER_ONLY = (
        "対応しました", "対応いたしました", "対応致しました", "確認しました",
        "確認いたしました", "本来であれば登録できません", "他の学生に尋ねてみましょう",
        "特にないです", "ご確認ください",
    )
    if stripped in FILLER_ONLY or any(
        stripped == p + suf for p in FILLER_ONLY for suf in ("。", "！", "")
    ):
        return "filler-only answer"

    # Drift signal #1: HH:MM time pattern in answer that ISN'T in the question.
    # When staff says "09:30〜のレビューを差し替えました", they're handling
    # a one-off slot for a specific student — not articulating a rule.
    time_pat = re.compile(r"\b\d{1,2}[:：]\d{2}")
    a_times = set(time_pat.findall(joined_a))
    q_times = set(time_pat.findall(thread[0]["Content"]))
    if a_times - q_times and len(joined_a) < 200:
        return "drift: answer references specific time slot"

    # Drift signal #2: answer mentions a 3rd-party "Xさん" where X is neither
    # the asker nor present in the question text. Common pattern: staff
    # batch-replies and we picked up the reply meant for a different student.
    # Two false-positive guards:
    #   - skip if the answer body is long (>500 chars) — likely a rule
    #     statement that happens to cite a 3rd-party as an example
    #   - skip if the X resembles the asker name (typos / similar handles)
    asker = thread[0]["Username"].lower()
    person_ref = re.compile(r"([a-zA-Z][\w._-]{2,})さん")
    a_refs = set(m.group(1) for m in person_ref.finditer(joined_a))
    q_text_lc = thread[0]["Content"].lower()
    staff_lc = {s.lower() for s in STAFF}
    # Common staff aliases used in conversation (e.g. "nopさん" for nop9166/nop9039)
    staff_aliases = {"nop", "lazuli", "alex", "destiny", "9166", "9039"}
    for ref in a_refs:
        rl = ref.lower()
        if rl == asker:
            continue
        if rl in q_text_lc or asker in rl or rl in asker:
            continue
        # Skip if Xさん is a staff member or a common staff alias
        if rl in staff_lc or rl in staff_aliases:
            continue
        if any(rl.startswith(p) for p in staff_aliases):
            continue
        # Skip near-typos of the asker (shared 4-char prefix or 3-char suffix)
        if len(rl) >= 4 and (rl[:4] == asker[:4] or rl[-3:] == asker[-3:]):
            continue
        if len(joined_a) > 500:
            continue
        return f"drift: answer references @{ref} (≠asker @{thread[0]['Username']})"

    # Drift signal #3: question and answer reference different projects
    # (term3d vs cpp04, etc). Same project + different exercise is permitted.
    PROJECT_NAMES = [
        "philosopher", "minishell", "ft_printf", "get_next_line", "gnl",
        "push_swap", "so_long", "fdf", "fract-ol", "fractol", "pipex",
        "cub3d", "minirt", "ft_irc", "netpractice", "ft_transcendence",
        "transcendence", "inception", "ft_containers", "webserv",
        "born2beroot", "ft_services", "term3d", "ft_communication",
        "ft_self-analysis", "ft_self_analysis", "fillit", "hotrace",
        "ft_ality", "computor", "kfs", "matcha", "matt_daemon",
        "famine", "pestilence", "woody-woodpacker", "ft_helpme",
        "cpp00", "cpp01", "cpp02", "cpp03", "cpp04",
        "cpp05", "cpp06", "cpp07", "cpp08", "cpp09",
        "cpp_00", "cpp_01", "cpp_02", "cpp_03", "cpp_04",
        "cpp_05", "cpp_06", "cpp_07", "cpp_08", "cpp_09",
    ]
    qpl = thread[0]["Content"].lower()
    apl = joined_a.lower()
    qpr = {p for p in PROJECT_NAMES if p in qpl}
    apr = {p for p in PROJECT_NAMES if p in apl}
    if qpr and apr and not (qpr & apr):
        return f"drift: project mismatch (Q={sorted(qpr)} A={sorted(apr)})"

    return None


def thread_to_markdown(thread: list[dict], slug: str, label: str,
                       all_authors: dict[str, int]) -> tuple[str, str, dict]:
    q = thread[0]
    answer_msgs = [m for m in thread[1:] if m["Username"] in STAFF]
    other_msgs = [m for m in thread[1:] if m["Username"] not in STAFF]

    qclean = clean_content(q["Content"])
    if has_pii(q["Content"]):
        return "", "", {"drop_reason": "PII in question"}

    answer_chunks = []
    for a in answer_msgs:
        if has_pii(a["Content"]):
            continue
        ac = clean_content(a["Content"])
        if not ac:
            continue
        answer_chunks.append((a["Username"], ac))
    if not answer_chunks:
        return "", "", {"drop_reason": "PII in all staff answers"}

    qauthor_followups = [
        m for m in thread[1:]
        if m["Username"] == q["Username"] and m["_dt"] > answer_msgs[0]["_dt"]
    ]
    # If asker added a clarification AFTER the first staff answer, fold into Q
    if qauthor_followups:
        for f in qauthor_followups:
            if has_pii(f["Content"]):
                continue
            fc = clean_content(f["Content"])
            if fc:
                qclean += "\n\n" + fc

    # Topic title — first non-empty content line of the question, skipping
    # generic openings ("(スタッフ宛)", "こんにちは。", "お疲れ様です。", "報告です。",
    # "ご質問です。") and `>` quote lines.
    GENERIC_OPENERS = (
        "(スタッフ宛)", "こんにちは", "こんばんは", "おはようございます",
        "お疲れ様", "お疲れさま", "おつかれ", "失礼", "報告です",
        "ご報告", "質問です", "ご質問", "いつもありがとう",
        "いつもお世話", "お世話になっ", "Bonsoir", "bonsoir",
        "ありがとうございます", "ありがとう", "ご返答", "ご回答ありがとう",
        "返信", "Bonjour", "bonjour", "すみません", "すいません",
        "確認しました", "了解", "承知",
    )
    title = "質問"
    fallback_title = None
    for ln in qclean.splitlines():
        ln = ln.strip().lstrip("> ").strip()
        if not ln:
            continue
        matched_opener = next(
            (g for g in GENERIC_OPENERS if ln.startswith(g)), None,
        )
        if matched_opener:
            # Strip opener (and any trailing punctuation), use rest if substantive
            rest = ln[len(matched_opener):]
            rest = rest.lstrip(" 　、。!！？?：:")
            if len(rest) >= 12:
                fallback_title = rest[:80]
            continue
        if len(ln) < 8:
            continue
        title = ln[:80]
        break
    if title == "質問" and fallback_title:
        title = fallback_title

    date = q["_dt"].strftime("%Y-%m-%d")
    fname_slug = slug_topic(q["Content"] + " " + answer_chunks[0][1])
    filename = f"{date}-{fname_slug}.md"

    # Tags from bucket
    tag_map = {
        "peer-review": ["peer-review", "evaluation"],
        "blackhole-freeze-agu": ["blackhole", "freeze", "agu"],
        "exam": ["exam"],
        "norminette": ["norminette"],
        "common-core": ["common-core", "42cursus"],
        "discord-rules": ["discord"],
        "piscine": ["piscine"],
        "cluster-imac": ["cluster", "campus"],
        "intra": ["intra"],
        "goinfre-docker": ["goinfre", "docker"],
        "withdraw": ["withdrawal"],
        "bocal-pedago-staff": ["bocal", "staff"],
        "road-to": ["road-to"],
        "job": ["job", "internship"],
        "slack": ["slack"],
    }
    tags = tag_map.get(slug, [slug])

    # Body
    a_blocks = []
    for user, body in answer_chunks:
        a_blocks.append(f"(@{user}, staff): {body}")
    answer_md = "\n\n---\n\n".join(a_blocks)

    body = (
        f"# {title}\n\n"
        f"**Source**: 42 Tokyo Discord, {date}  \n"
        f"**Tags**: {', '.join(tags)}\n\n"
        f"## Q\n\n{qclean}\n\n"
        f"## A\n\n{answer_md}\n"
    )

    meta = {
        "filename": filename,
        "bucket_slug": slug,
        "bucket_label": label,
        "date": date,
        "asker": q["Username"],
        "answerer": answer_chunks[0][0],
        "answer_chars": sum(len(b) for _, b in answer_chunks),
        "title": title,
    }
    return filename, body, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="Cap docs written (0 = no cap)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Don't write files, just print summary")
    ap.add_argument("--report-only", action="store_true",
                    help="Only write _FINDINGS.md; assume *.md already present")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    rows = load_rows()
    print(f"loaded {len(rows)} rows", file=sys.stderr)

    qrows_idx = [i for i, r in enumerate(rows) if is_question(r["Content"])]
    print(f"questions: {len(qrows_idx)}", file=sys.stderr)

    drops = Counter()
    threads = []
    used_filenames = set()
    bucket_counts = Counter()

    for qi in qrows_idx:
        q = rows[qi]
        slug, label = bucket_of(q["Content"])
        if slug in DROP_BUCKETS:
            drops["bucket: project (drop)"] += 1
            continue
        if slug == "unbucketed":
            drops["bucket: unbucketed"] += 1
            continue
        if has_pii(q["Content"]):
            drops["pii: question"] += 1
            continue
        thread = find_thread(rows, qi)
        if thread is None:
            drops["no staff answer"] += 1
            continue
        why = thread_quality(thread, slug)
        if why:
            drops[why] += 1
            continue
        threads.append((slug, label, thread))

    print(f"after filter: {len(threads)} threads", file=sys.stderr)

    # Build markdown + collect meta
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metas = []
    skipped_pii = 0
    written = 0
    for slug, label, thread in threads:
        filename, body, meta = thread_to_markdown(thread, slug, label, {})
        if "drop_reason" in meta:
            drops[meta["drop_reason"]] += 1
            skipped_pii += 1
            continue
        if filename in MANUAL_SKIP:
            drops["manual skip-list"] += 1
            continue
        # Avoid filename collision (multiple Qs same day, same slug)
        n = 2
        base = filename
        while filename in used_filenames:
            stem = base[:-3]
            filename = f"{stem}-{n}.md"
            n += 1
        used_filenames.add(filename)
        meta["filename"] = filename
        metas.append((slug, label, meta, body))
        bucket_counts[label] += 1
        if not args.dry_run and not args.report_only:
            (OUT_DIR / filename).write_text(body, encoding="utf-8")
            written += 1
            if args.limit and written >= args.limit:
                break
        if not args.quiet:
            print(f"  {filename}  [{label}]", file=sys.stderr)

    # Sample question titles per bucket — for findings
    by_bucket = defaultdict(list)
    for slug, label, meta, body in metas:
        by_bucket[label].append(meta)

    # Write findings
    findings_path = OUT_DIR / "_FINDINGS.md"
    date_min = rows[0]["_dt"].strftime("%Y-%m-%d")
    date_max = rows[-1]["_dt"].strftime("%Y-%m-%d")
    qtotal = len(qrows_idx)
    n_accepted = len(metas)

    bucket_to_corpus_hint = {
        "ピアレビュー / レビュー":
            "clarifies `corpus/intra/Intra Meta ピアレビューについて.md`, "
            "`corpus/intra/Intra Meta 【レビューキャンペーン】ルーブリック.md`, "
            "`corpus/intra/the_art_of_peer_evaluation.en.md`",
        "BlackHole / Freeze / AGU":
            "extends `corpus/intra/15.md` (BlackHole) and AGU/Freeze rules; "
            "many of these are *new* edge cases not in the static corpus",
        "Exam / 試験":
            "clarifies `corpus/intra/Intra Meta 試験規則.md`",
        "Discord ルール":
            "extends `corpus/intra/42 Tokyo Discordの利用ポリシー.md`",
        "Piscine":
            "extends Piscine and Reloaded notes; primarily *new* operational detail",
        "Norminette":
            "clarifies `corpus/intra/Intra Meta [Norminette] 42Headerのメアドを設定する方法.md`",
        "Common Core / 42cursus":
            "operational *new* detail on registration and course state machine",
        "Cluster / iMac / 校舎":
            "extends campus-rule notes (`corpus/intra/Intra Meta キャンパス全体ルール.md`, etc.)",
        "Intra / Intranet":
            "operational fixes/clarifications around the intranet (mostly *new*)",
        "Goinfre / Docker / Guacamole":
            "*new* operational detail not in the static corpus",
        "退学 / 在籍 / 申請":
            "extends `corpus/intra/Intra Meta 退学の申請方法.md`",
        "Bocal / Pedago / Staff":
            "*new* operational detail",
        "Reloaded / Road to":
            "*new* operational detail",
        "求人 / Job":
            "extends `corpus/intra/Intra Meta _ 学生発信の人材紹介および求人のルールについて.md`",
        "Slack / 42born2code":
            "*new* operational detail",
    }

    bucket_descriptions = {
        "ピアレビュー / レビュー":
            "edge cases in flag selection, dispute resolution, repeated-reviewer "
            "handling, point/score corrections, defense logistics",
        "BlackHole / Freeze / AGU":
            "校舎 use during AGU, BH-extension semantics, level-up vs "
            "project-clear gating, AGU↔Freeze interaction",
        "Exam / 試験":
            "which attempt counts toward XP, retake mechanics, exam-mode "
            "subjects, .cpp auto-grader behaviour",
        "Discord ルール":
            "where to post bug reports, who to mention, escalation patterns",
        "Piscine":
            "C↔Go Piscine differences, 42cursus transition, achievement bonuses",
        "Norminette":
            "norm exceptions, 42header per file type, post-merge norm errors",
        "Common Core / 42cursus":
            "registration conflicts (libft vs libft-0X), curriculum state machine, "
            "achievement counters, score/percent updates",
        "Cluster / iMac / 校舎":
            "学生証 issuance, building access, iMac assignment",
        "Intra / Intranet":
            "intranet UI/state quirks, vogsphere git semantics, password rules",
        "Goinfre / Docker / Guacamole":
            "VM disk-space, Docker engine version, Guacamole environment",
        "退学 / 在籍 / 申請":
            "student-status changes, reinstatement",
        "Bocal / Pedago / Staff":
            "operational follow-ups for individual cases",
        "Reloaded / Road to":
            "Reloaded-specific clarifications and Road-to-X programs",
        "求人 / Job":
            "internship rules, code-publication for portfolio",
        "Slack / 42born2code":
            "interaction with the global 42 Slack",
    }

    lines = []
    lines.append("# Discord Q&A — extraction findings\n")
    lines.append(
        f"Source: `Q&A/Discord_chat_*.csv` ({len(rows)} rows, "
        f"{qtotal} question rows, {n_accepted} accepted)  \n"
        f"Date range: {date_min} → {date_max}  \n"
        f"Verified staff handles: " + ", ".join(f"@{u}" for u in sorted(STAFF)) + "\n"
    )
    lines.append("Staff verification used three independent signals: "
                 "(1) staff-style language frequency (\"対応しました\", \"修正しました\", "
                 "\"42Networkと確認中\", etc.), (2) ratio of answers to questions "
                 "asked (≥98% answers), and (3) actions only staff can perform "
                 "(modifying intra scores, BH extension, adding allowed functions).\n")
    lines.append("## Summary\n")
    lines.append(f"- {n_accepted} markdown files written under `corpus/discord-qa/`")
    lines.append(f"- Filtering criteria: question must fall in a KEEP bucket, "
                 f"answer must come from verified staff (Mentions-the-asker "
                 f"up to {DIRECTED_WINDOW_HRS}h later, OR within "
                 f"{PROXIMITY_FALLBACK_MIN}min of the question), and the "
                 f"answer must be substantive (not just \"確認中です\").")
    lines.append("- Bucket-level summary below; raw drop counters at end.\n")
    lines.append("## Topic index\n")

    bucket_order = [
        "ピアレビュー / レビュー",
        "BlackHole / Freeze / AGU",
        "Exam / 試験",
        "Discord ルール",
        "Piscine",
        "Norminette",
        "Common Core / 42cursus",
        "Cluster / iMac / 校舎",
        "Intra / Intranet",
        "Goinfre / Docker / Guacamole",
        "退学 / 在籍 / 申請",
        "Bocal / Pedago / Staff",
        "Reloaded / Road to",
        "求人 / Job",
        "Slack / 42born2code",
    ]
    for label in bucket_order:
        items = by_bucket.get(label, [])
        if not items:
            continue
        lines.append(f"### {label} ({len(items)} docs)")
        if label in bucket_descriptions:
            lines.append(f"What it answers: {bucket_descriptions[label]}.\n")
        # 3 sample titles
        sample = items[:3]
        for s in sample:
            t = s.get("title") or s["filename"][:-3].replace("-", " ")
            # markdown link text safety: strip square brackets
            t = t.replace("[", "(").replace("]", ")")
            if len(t) > 70:
                t = t[:70] + "…"
            lines.append(f"- [{t}]({s['filename']})")
        if label in bucket_to_corpus_hint:
            lines.append(f"\nStatus: {bucket_to_corpus_hint[label]}.\n")
    lines.append("## Skipped\n")
    for reason, n in drops.most_common():
        lines.append(f"- {n} — {reason}")
    lines.append("")
    lines.append("## Open questions for the user\n")
    lines.append("- **Senior-student answers excluded**: kept only verified-staff replies. "
                 "Some senior students (snara, yokawada, nfukuma) regularly post correct, "
                 "well-sourced answers. They were excluded conservatively. If you want "
                 "their answers folded in, say so and I'll re-run with an extended allowlist.")
    lines.append("- **Stale operational facts**: a few BH/AGU answers from 2022 may have "
                 "been superseded by 2024+ rule revisions. The bot may now answer with "
                 "outdated rule clauses. Spot-check the BH/AGU bucket if students rely on it.")
    lines.append("- **Ambiguous redactions**: messages mentioning specific intra logins "
                 "(not real names) were kept — they're already entities in the graph and "
                 "carry no real-world identity by themselves.")
    if not args.dry_run:
        findings_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {findings_path}", file=sys.stderr)
    print(f"docs written: {written}", file=sys.stderr)
    print(f"drops: {dict(drops)}", file=sys.stderr)


if __name__ == "__main__":
    main()
