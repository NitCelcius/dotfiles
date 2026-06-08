#!/usr/bin/env bash
# Claude Code statusline (p10k / powerline, 2行)
#   L1: 📁folder > branch > 📝+add -del        … この会話/repo
#   L2: 🪟ctx(k %) ⏰5h(残時間 %) > 🔥k/min $sess > 🧠cache > 🤖model  … 使用量
#
# めちゃくちゃ vibe に作ったので品質はあまり保証できない
# 構成: PREPARE で表示値・色をすべて算出 → RENDER で emit を一括。

export LC_ALL=C.UTF-8   # ロケール未設定だと $'\uXXXX' がリテラル "" のまま出力されるため明示

input=$(cat)

# ===== 定数 =====
ESC=$'\033'
GLYPH_ARROW=$'\ue0b0'        # 実線セパレータ
GLYPH_ARROW_SOFT=$'\ue0b1'   # 細セパレータ（同色隣接時）
GLYPH_BRANCH=$'\ue0a0'       # branch アイコン
CONTEXT_WINDOW_LIMIT=200000  # context window の量をハードコード

FG_TEXT=255; FG_ADD=77; FG_DEL=203          # 文字色（白 / +緑 / -赤）
BG_FOLDER=24; BG_BRANCH=31; BG_DIFF=238; BG_MODEL=54
BG_GREEN=22; BG_YELLOW=58; BG_RED=52; BG_PURPLE=57; BG_GRAY=240

# ===== 汎用ヘルパー =====
round_int()    { awk -v x="$1" 'BEGIN{printf "%d", x + 0.5}'; }
remaining_pct() { awk -v u="$1" 'BEGIN{printf "%d", (100 - u) + 0.5}'; }

format_branch() {  # A/B → A(3字)/B(15字…) ／ スラッシュ無しは 20字…
  local name="$1"
  if [[ "$name" == */* ]]; then
    local head="${name%%/*}" tail="${name#*/}"
    [ "${#tail}" -gt 20 ] && tail="${tail:0:20}…"
    printf '%s/%s' "${head:0:3}" "$tail"
  else
    [ "${#name}" -gt 25 ] && name="${name:0:25}…"
    printf '%s' "$name"
  fi
}

# 色判定（しきい値ノブはここに集約）
context_fill_bg() {  # $1=使用% $2=推定トークン  … 80%↑(auto-compact)紫 / 70%↑赤 / 50%↑黄 / 緑
  if   [ "$1" -ge 80 ]; then echo "$BG_PURPLE"
  elif [ "$1" -ge 70 ]; then echo "$BG_RED"
  elif [ "$1" -ge 50 ]; then echo "$BG_YELLOW"
  else echo "$BG_GREEN"; fi
}
cache_share_bg() {  # $1=read share%  … 90↑緑 / 75↑黄 / 赤
  if   [ "$1" -ge 90 ]; then echo "$BG_GREEN"
  elif [ "$1" -ge 75 ]; then echo "$BG_YELLOW"
  else echo "$BG_RED"; fi
}
burn_rate_bg() {  # $1=tokens/min  … 5000↑赤 / 2000↑黄 / 緑
  if   [ "$1" -ge 5000 ]; then echo "$BG_RED"
  elif [ "$1" -ge 2000 ]; then echo "$BG_YELLOW"
  else echo "$BG_GREEN"; fi
}
session_pace_bg() {  # $1=quota使用% $2=残り分  … 等分ペースの何倍消費したか
  local used="$1" remaining_min="$2"
  [ -z "$used" ] && { echo "$BG_GRAY"; return; }
  [ "$(round_int "$used")" -ge 100 ] && { echo "$BG_GRAY"; return; }   # 100%消費=課金開始→灰
  [ -z "$remaining_min" ] && { echo "$BG_GREEN"; return; }
  awk -v u="$used" -v rmin="$remaining_min" -v g="$BG_GREEN" -v y="$BG_YELLOW" -v r="$BG_RED" 'BEGIN{
    elapsed = 300 - rmin; if (elapsed < 0) elapsed = 0;
    expected = elapsed / 300 * 100;            # 等分なら今これだけ使っているはず
    if (elapsed < 5 || expected < 1) { print g }   # 序盤は緑
    else { ratio = u / expected; if (ratio >= 4) print r; else if (ratio >= 2) print y; else print g }
  }'
}

# powerline セグメント描画
emit() {  # $1=行バッファ名 $2=直前bg名 $3=text $4=fg $5=bg
  local -n _buf="$1"; local -n _prev_bg="$2"
  local text="$3" fg="$4" bg="$5"
  if [ -n "$_prev_bg" ]; then
    if [ "$_prev_bg" = "$bg" ]; then _buf+="${ESC}[38;5;250;48;5;${bg}m${GLYPH_ARROW_SOFT}"
    else _buf+="${ESC}[38;5;${_prev_bg};48;5;${bg}m${GLYPH_ARROW}"; fi
  fi
  _buf+="${ESC}[38;5;${fg};48;5;${bg}m ${text} "
  _prev_bg="$bg"
}
close_line() {  # $1=行バッファ名 $2=直前bg名
  local -n _buf="$1"; local -n _prev_bg="$2"
  [ -n "$_prev_bg" ] && _buf+="${ESC}[0m${ESC}[38;5;${_prev_bg}m${GLYPH_ARROW}${ESC}[0m"
}

# ============================================================
# PREPARE: stdin から生値を取得
# ============================================================
model_name=$(printf '%s' "$input"          | jq -r '.model.display_name // "?"')
current_dir=$(printf '%s' "$input"          | jq -r '.workspace.current_dir // .cwd // "."')
session_cost_usd=$(printf '%s' "$input"     | jq -r '.cost.total_cost_usd // empty')
context_used_percent=$(printf '%s' "$input" | jq -r '.context_window.used_percentage // empty')
quota_used_percent=$(printf '%s' "$input"   | jq -r '.rate_limits.five_hour.used_percentage // empty')
quota_resets_at=$(printf '%s' "$input"      | jq -r '.rate_limits.five_hour.resets_at // empty')

# 作業ツリーの変更行（git diff --numstat HEAD: staged+unstaged, 未追跡除く）
lines_added=0; lines_removed=0
diff_summary=$(git -C "$current_dir" diff --numstat HEAD 2>/dev/null | awk '{a+=$1; d+=$2} END{printf "%d %d", a+0, d+0}')
[ -n "$diff_summary" ] && read -r lines_added lines_removed <<< "$diff_summary"

# ccusage: burn / 残時間 / block cost / cache トークン
burn_tokens_per_min=""; block_remaining_min=""; block_cost_usd=""
cache_creation_tokens=0; cache_read_tokens=0
ccusage_raw=$(ccusage blocks --active --json --offline 2>/dev/null)
[ -z "$ccusage_raw" ] && ccusage_raw=$(pnpx ccusage blocks --active --json --offline 2>/dev/null)
if [ -n "$ccusage_raw" ]; then
  ccusage_json="{${ccusage_raw#*\{}"   # 進捗ログを捨てて { から JSON 化
  ccusage_parsed=$(printf '%s' "$ccusage_json" | jq -r '
    (.blocks[0] // empty)
    | "\(.burnRate.tokensPerMinuteForIndicator // 0) \(.projection.remainingMinutes // 0) \(.costUSD // 0) \(.tokenCounts.cacheCreationInputTokens // 0) \(.tokenCounts.cacheReadInputTokens // 0)"
  ' 2>/dev/null)
  read -r burn_tokens_per_min block_remaining_min block_cost_usd cache_creation_tokens cache_read_tokens <<< "$ccusage_parsed"
fi

# 5h 残り時間（resets_at 優先 / 無ければ ccusage window）
session_remaining_min=""; now_epoch=$(date +%s)
if [ -n "$quota_resets_at" ]; then
  reset_epoch="$quota_resets_at"
  [[ "$reset_epoch" =~ ^[0-9]{13,}$ ]] && reset_epoch=$(( reset_epoch / 1000 ))   # ms→s
  if [[ "$reset_epoch" =~ ^[0-9]+$ ]]; then
    session_remaining_min=$(( (reset_epoch - now_epoch) / 60 ))
  else
    parsed_epoch=$(date -d "$quota_resets_at" +%s 2>/dev/null)
    [ -n "$parsed_epoch" ] && session_remaining_min=$(( (parsed_epoch - now_epoch) / 60 ))
  fi
fi
[ -z "$session_remaining_min" ] && [ -n "$block_remaining_min" ] && session_remaining_min="${block_remaining_min%%.*}"
[ -n "$session_remaining_min" ] && [ "$session_remaining_min" -lt 0 ] && session_remaining_min=0

# ============================================================
# PREPARE: 各セグメントの表示テキストと背景色を確定
# ============================================================
# folder / branch
folder_name=$(basename "$current_dir")
[ "${#folder_name}" -gt 10 ] && folder_name="${folder_name:0:10}…"
folder_text="📁 $folder_name"; folder_bg=$BG_FOLDER

branch_name=$(git -C "$current_dir" branch --show-current 2>/dev/null)
[ -z "$branch_name" ] && branch_name=$(git -C "$current_dir" rev-parse --short HEAD 2>/dev/null)
[ -n "$branch_name" ] && branch_name=$(format_branch "$branch_name")
branch_text="$GLYPH_BRANCH $branch_name"; branch_bg=$BG_BRANCH

# 変更行（+緑 -赤）
diff_text=""; diff_bg=$BG_DIFF
if [ "$lines_added" -gt 0 ] || [ "$lines_removed" -gt 0 ]; then
  diff_text="📝 ${ESC}[38;5;${FG_ADD}m+${lines_added}${ESC}[38;5;${FG_DEL}m -${lines_removed}${ESC}[38;5;${FG_TEXT}m"
fi

# context（推定トークン k + %）
context_text=""; context_bg=$BG_GREEN
if [ -n "$context_used_percent" ]; then
  context_used_int=$(round_int "$context_used_percent")
  context_tokens=$(awk -v p="$context_used_percent" -v limit="$CONTEXT_WINDOW_LIMIT" 'BEGIN{printf "%d", p/100*limit}')
  context_tokens_k=$(awk -v t="$context_tokens" 'BEGIN{printf "%d", t/1000 + 0.5}')
  context_bg=$(context_fill_bg "$context_used_int")
  context_text="🧠 ${context_tokens_k}k ${context_used_int}%"
fi

# 5h セッション（残時間 + 残%、色は消費ペース）
session_text=""; session_bg=$(session_pace_bg "$quota_used_percent" "$session_remaining_min")
if [ -n "$session_remaining_min" ] || [ -n "$quota_used_percent" ]; then
  session_text="⏰"
  [ -n "$session_remaining_min" ] && session_text="$session_text $((session_remaining_min/60))h$((session_remaining_min%60))m"
  [ -n "$quota_used_percent" ]    && session_text="$session_text $(remaining_pct "$quota_used_percent")%"
fi

# burn（k/min + セッション金額）
burn_text=""; burn_bg=$BG_GRAY
if [ -n "$burn_tokens_per_min" ] || [ -n "$session_cost_usd" ]; then
  burn_rate_text=""
  if [ -n "$burn_tokens_per_min" ]; then
    burn_bg=$(burn_rate_bg "$(round_int "$burn_tokens_per_min")")
    burn_rate_text="$(awk -v x="$burn_tokens_per_min" 'BEGIN{printf "%.1f", x/1000}')k/min "
  fi
  [ -z "$session_cost_usd" ] && session_cost_usd="$block_cost_usd"
  session_cost_text="$(awk -v x="${session_cost_usd:-0}" 'BEGIN{printf "%.2f", x}')"
  burn_text="🔥 ${burn_rate_text}\$${session_cost_text}"
fi

# cache read share
cache_read_share_percent=""; cache_bg=$BG_GREEN
cache_total_tokens=$(( ${cache_read_tokens:-0} + ${cache_creation_tokens:-0} ))
if [ "$cache_total_tokens" -gt 0 ]; then
  cache_read_share_percent=$(awk -v r="${cache_read_tokens:-0}" -v t="$cache_total_tokens" 'BEGIN{printf "%d", (r/t*100)+0.5}')
  cache_bg=$(cache_share_bg "$cache_read_share_percent")
  cache_text="♻️ ${cache_read_share_percent}%"
fi

# model（先頭3字）
case "$model_name" in
  *Opus*)   model_family="Opus"   ;;
  *Sonnet*) model_family="Sonnet" ;;
  *Haiku*)  model_family="Haiku"  ;;
  *)        model_family="${model_name##* }" ;;   # 不明時は最後の単語
esac
model_text="🤖 ${model_family}"; model_bg=$BG_MODEL
# ============================================================
# RENDER: 値を並べるだけ（構造はここを読めば分かる）
# ============================================================
line1=""; line1_bg=""
emit line1 line1_bg "$folder_text" "$FG_TEXT" "$folder_bg"
[ -n "$branch_name" ]               && emit line1 line1_bg "$branch_text"  "$FG_TEXT" "$branch_bg"
[ -n "$diff_text" ]                 && emit line1 line1_bg "$diff_text"    "$FG_TEXT" "$diff_bg"
close_line line1 line1_bg

line2=""; line2_bg=""
[ -n "$context_text" ]              && emit line2 line1_bg "$context_text" "$FG_TEXT" "$context_bg"
[ -n "$session_text" ]              && emit line2 line2_bg "$session_text" "$FG_TEXT" "$session_bg"
[ -n "$burn_text" ]                 && emit line2 line2_bg "$burn_text"    "$FG_TEXT" "$burn_bg"
[ -n "$cache_read_share_percent" ]  && emit line2 line2_bg "$cache_text"   "$FG_TEXT" "$cache_bg"
emit line2 line2_bg "$model_text" "$FG_TEXT" "$model_bg"
close_line line2 line2_bg

printf '%s\n%s' "$line1" "$line2"
