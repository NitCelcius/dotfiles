#!/usr/bin/env bash
# Claude Code statusline (p10k / powerline, 2行)
#   L1: 📁folder > branch > 📝+add -del                 … この会話/repo
#   L2: 🧠ctx > ⏰5h > 7d(必要時) > 🔥cost(+$/h) > ♻cache(必要時) > 🤖model
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

FG_TEXT=255; FG_ADD=77; FG_DEL=203          # 文字色（白 / +緑 / -赤）
BG_FOLDER=24; BG_BRANCH=31; BG_DIFF=238; BG_MODEL=54; BG_PR=25
BG_GREEN=22; BG_YELLOW=58; BG_RED=52; BG_PURPLE=57; BG_GRAY=240

FIVE_HOUR_WINDOW_SEC=$((5 * 60 * 60))
SEVEN_DAY_WINDOW_SEC=$((7 * 24 * 60 * 60))
SEVEN_DAY_LOW_REMAINING_PCT=20
CACHE_WARN_SEC=$((30 * 60))
CACHE_DANGER_SEC=$((5 * 60))

# ===== 汎用ヘルパー =====
round_int()      { awk -v x="$1" 'BEGIN{printf "%d", x + 0.5}'; }
remaining_pct() { awk -v u="$1" 'BEGIN{printf "%d", (100 - u) + 0.5}'; }

normalize_epoch() {
  local value="$1"
  [ -z "$value" ] && return
  if [[ "$value" =~ ^[0-9]+$ ]]; then
    [ "${#value}" -ge 13 ] && value=$(( value / 1000 ))
    printf '%s' "$value"
    return
  fi

  local parsed=""
  parsed=$(date -d "$value" +%s 2>/dev/null)
  if [ -z "$parsed" ]; then
    parsed=$(date -j -f '%Y-%m-%dT%H:%M:%S%z' "$value" +%s 2>/dev/null)
  fi
  [ -n "$parsed" ] && printf '%s' "$parsed"
}

format_epoch_hm() {
  local epoch="$1"
  [ -z "$epoch" ] && return
  date -d "@$epoch" +%H:%M 2>/dev/null || date -r "$epoch" +%H:%M 2>/dev/null
}

format_branch() {
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

quota_exhausted() {
  local used="$1"
  [ -n "$used" ] && awk -v u="$used" 'BEGIN{exit !(u >= 100)}'
}

# $1=quota使用% $2=resets_at(epoch) $3=window秒
# 今までの平均消費速度を窓末まで外挿した projected usage で色を決める。
# <=100% 緑 / >100% 黄 / >=150% 赤。枠を使い切った後は pace の対象外として灰。
quota_pace_bg() {
  local used="$1" reset_epoch="$2" window_sec="$3"
  [ -z "$used" ] && { echo "$BG_GRAY"; return; }

  quota_exhausted "$used" && { echo "$BG_GRAY"; return; }
  [ -z "$reset_epoch" ] && { echo "$BG_GREEN"; return; }

  local now_epoch remaining_sec elapsed_sec
  now_epoch=$(date +%s)
  remaining_sec=$(( reset_epoch - now_epoch ))
  elapsed_sec=$(( window_sec - remaining_sec ))
  [ "$elapsed_sec" -lt 0 ] && elapsed_sec=0
  [ "$elapsed_sec" -gt "$window_sec" ] && elapsed_sec="$window_sec"

  # 開始直後でも既に usage があれば、意図どおり強い外挿を行う。
  if [ "$elapsed_sec" -le 0 ]; then
    awk -v u="$used" -v g="$BG_GREEN" -v r="$BG_RED" 'BEGIN{if (u > 0) print r; else print g}'
    return
  fi

  awk -v u="$used" -v elapsed="$elapsed_sec" -v window="$window_sec" \
      -v g="$BG_GREEN" -v y="$BG_YELLOW" -v r="$BG_RED" 'BEGIN{
    projected = u * window / elapsed;
    if (projected >= 150) print r;
    else if (projected > 100) print y;
    else print g;
  }'
}

# powerline セグメント描画
emit() {  # $1=行バッファ名 $2=直前bg名 $3=text $4=fg $5=bg
  local -n _buf="$1"; local -n _prev_bg="$2"
  local text="$3" fg="$4" bg="$5"
  if [ -n "$_prev_bg" ]; then
    if [ "$_prev_bg" = "$bg" ]; then
      _buf+="${ESC}[38;5;250;48;5;${bg}m${GLYPH_ARROW_SOFT}"
    else
      _buf+="${ESC}[38;5;${_prev_bg};48;5;${bg}m${GLYPH_ARROW}"
    fi
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
context_window_size=$(printf '%s' "$input"  | jq -r '.context_window.context_window_size // empty')
context_tokens_exact=$(printf '%s' "$input" | jq -r '
  (.context_window.current_usage // empty)
  | ((.input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0))
  | select(. > 0)')

five_hour_used_percent=$(printf '%s' "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
five_hour_resets_raw=$(printf '%s' "$input"    | jq -r '.rate_limits.five_hour.resets_at // empty')
seven_day_used_percent=$(printf '%s' "$input"  | jq -r '.rate_limits.seven_day.used_percentage // empty')
seven_day_resets_raw=$(printf '%s' "$input"     | jq -r '.rate_limits.seven_day.resets_at // empty')

prompt_cache_warm=$(printf '%s' "$input"       | jq -r '.prompt_cache.warm | if . == null then empty else tostring end')
prompt_cache_observed=$(printf '%s' "$input"   | jq -r '.prompt_cache.caching_observed | if . == null then empty else tostring end')
prompt_cache_expires_raw=$(printf '%s' "$input"| jq -r '.prompt_cache.expires_at // empty')

five_hour_reset_epoch=$(normalize_epoch "$five_hour_resets_raw")
seven_day_reset_epoch=$(normalize_epoch "$seven_day_resets_raw")
prompt_cache_expires_epoch=$(normalize_epoch "$prompt_cache_expires_raw")
now_epoch=$(date +%s)

# 作業ツリーの変更行（git diff --numstat HEAD: staged+unstaged, 未追跡除く）
lines_added=0; lines_removed=0
diff_summary=$(git -C "$current_dir" diff --numstat HEAD 2>/dev/null | awk '{a+=$1; d+=$2} END{printf "%d %d", a+0, d+0}')
[ -n "$diff_summary" ] && read -r lines_added lines_removed <<< "$diff_summary"

# ccusage: 現在の金額 burn rate と、5h 残時間/金額のフォールバック
burn_cost_per_hour=""; block_remaining_min=""; block_cost_usd=""
ccusage_raw=$(ccusage blocks --active --json --offline 2>/dev/null)
[ -z "$ccusage_raw" ] && ccusage_raw=$(pnpx ccusage blocks --active --json --offline 2>/dev/null)
if [ -n "$ccusage_raw" ]; then
  ccusage_json="{${ccusage_raw#*\{}"
  ccusage_parsed=$(printf '%s' "$ccusage_json" | jq -r '
    (.blocks[0] // empty)
    | "\(.burnRate.costPerHour // 0) \(.projection.remainingMinutes // 0) \(.costUSD // 0)"
  ' 2>/dev/null)
  read -r burn_cost_per_hour block_remaining_min block_cost_usd <<< "$ccusage_parsed"
fi

# 5h 残り時間（rate_limits 優先 / 無ければ ccusage window）
session_remaining_min=""
if [ -n "$five_hour_reset_epoch" ]; then
  session_remaining_min=$(( (five_hour_reset_epoch - now_epoch) / 60 ))
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

# GitHub PR number
pr_text=""; pr_bg=$BG_PR
pr_number=$(gh --timeout 2s -C "$current_dir" pr view --json number -q '.number' 2>/dev/null)
[ -n "$pr_number" ] && pr_text="#${pr_number}"

# 変更行（+緑 -赤）
diff_text=""; diff_bg=$BG_DIFF
if [ "$lines_added" -gt 0 ] || [ "$lines_removed" -gt 0 ]; then
  diff_text="📝 ${ESC}[38;5;${FG_ADD}m+${lines_added}${ESC}[38;5;${FG_DEL}m -${lines_removed}${ESC}[38;5;${FG_TEXT}m"
fi

# context（トークン k [+ %]）
# 窓幅が来ていれば % と色（残量警告）まで出す。来ていなければ「何に対する割合か」が
# 決まらないので、%を伏せてトークン数だけ・色は緑固定にする（見かけの警告を出さない）。
context_text=""; context_bg=$BG_GREEN
if [ -n "$context_window_size" ] && [ -n "$context_used_percent" ]; then
  context_used_int=$(round_int "$context_used_percent")
  context_tokens="$context_tokens_exact"
  [ -z "$context_tokens" ] && context_tokens=$(awk -v p="$context_used_percent" -v limit="$context_window_size" 'BEGIN{printf "%d", p/100*limit}')
  context_tokens_k=$(awk -v t="$context_tokens" 'BEGIN{printf "%d", t/1000 + 0.5}')
  context_bg=$(context_fill_bg "$context_used_int")
  context_text="🧠 ${context_tokens_k}k ${context_used_int}%"
elif [ -n "$context_tokens_exact" ]; then
  context_tokens_k=$(awk -v t="$context_tokens_exact" 'BEGIN{printf "%d", t/1000 + 0.5}')
  context_text="🧠 ${context_tokens_k}k"
fi

# 5h セッション（残時間 + 残%、常時表示できる範囲で表示）
session_text=""
session_bg=$(quota_pace_bg "$five_hour_used_percent" "$five_hour_reset_epoch" "$FIVE_HOUR_WINDOW_SEC")
if [ -n "$session_remaining_min" ] || [ -n "$five_hour_used_percent" ]; then
  session_text="⏰"
  [ -n "$session_remaining_min" ] && session_text="$session_text $((session_remaining_min/60))h$((session_remaining_min%60))m"
  [ -n "$five_hour_used_percent" ] && session_text="$session_text $(remaining_pct "$five_hour_used_percent")%"
fi

# 7d quota（ペース超過、または残り20%以下のときだけ出す）
seven_day_text=""
seven_day_bg=$(quota_pace_bg "$seven_day_used_percent" "$seven_day_reset_epoch" "$SEVEN_DAY_WINDOW_SEC")
if [ -n "$seven_day_used_percent" ]; then
  seven_day_remaining=$(remaining_pct "$seven_day_used_percent")
  if [ "$seven_day_bg" != "$BG_GREEN" ] || [ "$seven_day_remaining" -le "$SEVEN_DAY_LOW_REMAINING_PCT" ]; then
    seven_day_text="7d ${seven_day_remaining}%"
  fi
fi

# cost（累積額 + 現在の金額 burn rate）
# burn rate は整数 $/h に丸め、0/h になる程度なら表示しない。
# quota を使い切って extra usage に入ったら、quota 側を灰にして cost 側を黄にする。
extra_usage_active=false
if quota_exhausted "$five_hour_used_percent" || quota_exhausted "$seven_day_used_percent"; then
  extra_usage_active=true
fi

burn_text=""; burn_bg=$BG_GREEN
[ "$extra_usage_active" = true ] && burn_bg=$BG_YELLOW
[ -z "$session_cost_usd" ] && session_cost_usd="$block_cost_usd"
if [ -n "$session_cost_usd" ] || [ -n "$burn_cost_per_hour" ]; then
  session_cost_text=$(awk -v x="${session_cost_usd:-0}" 'BEGIN{printf "%.1f", x}')
  burn_text="🔥 \$${session_cost_text}"

  if [ -n "$burn_cost_per_hour" ]; then
    burn_rate_int=$(round_int "$burn_cost_per_hour")
    [ "$burn_rate_int" -ge 1 ] && burn_text="${burn_text}(+${burn_rate_int}/h)"
  fi
fi

# prompt cache TTL
# >30m は非表示 / 30m〜5m 黄 / <=5m 赤 / cold は灰
cache_text=""; cache_bg=$BG_GRAY
if [ "$prompt_cache_observed" = "true" ]; then
  if [ "$prompt_cache_warm" = "true" ] && [ -n "$prompt_cache_expires_epoch" ]; then
    cache_remaining_sec=$(( prompt_cache_expires_epoch - now_epoch ))
    if [ "$cache_remaining_sec" -le 0 ]; then
      cache_text="♻️ cold"
      cache_bg=$BG_GRAY
    elif [ "$cache_remaining_sec" -le "$CACHE_DANGER_SEC" ]; then
      cache_text="♻️ $(format_epoch_hm "$prompt_cache_expires_epoch")"
      cache_bg=$BG_RED
    elif [ "$cache_remaining_sec" -le "$CACHE_WARN_SEC" ]; then
      cache_text="♻️ $(format_epoch_hm "$prompt_cache_expires_epoch")"
      cache_bg=$BG_YELLOW
    fi
  elif [ "$prompt_cache_warm" = "false" ]; then
    cache_text="♻️ cold"
    cache_bg=$BG_GRAY
  fi
fi

# model
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
[ -n "$branch_name" ] && emit line1 line1_bg "$branch_text" "$FG_TEXT" "$branch_bg"
[ -n "$pr_text" ]     && emit line1 line1_bg "$pr_text"     "$FG_TEXT" "$pr_bg"
[ -n "$diff_text" ]   && emit line1 line1_bg "$diff_text"   "$FG_TEXT" "$diff_bg"
close_line line1 line1_bg

line2=""; line2_bg=""
[ -n "$context_text" ]   && emit line2 line2_bg "$context_text"   "$FG_TEXT" "$context_bg"
[ -n "$session_text" ]   && emit line2 line2_bg "$session_text"   "$FG_TEXT" "$session_bg"
[ -n "$seven_day_text" ] && emit line2 line2_bg "$seven_day_text" "$FG_TEXT" "$seven_day_bg"
[ -n "$burn_text" ]      && emit line2 line2_bg "$burn_text"      "$FG_TEXT" "$burn_bg"
[ -n "$cache_text" ]     && emit line2 line2_bg "$cache_text"     "$FG_TEXT" "$cache_bg"
emit line2 line2_bg "$model_text" "$FG_TEXT" "$model_bg"
close_line line2 line2_bg

printf '%s\n%s' "$line1" "$line2"
