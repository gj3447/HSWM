#!/bin/zsh
# prom_search_hswm 공개 발행 — SYMPOSIUM(작업처, private)에서 편집 후 이걸로 공개 미러.
#
# 왜: SYMPOSIUM 모노레포는 private(비공개 내용 다수)이라 통째 공개 불가.
#     이 폴더만 공개 repo gj3447/HSWM(~/CD/HSWM/prom_search_hswm)로 미러링해 유명세 노출.
# 단일 작업처 = SYMPOSIUM/HSWM/prom_search_hswm. 공개본은 이 스크립트의 산출물(편집 금지).
#
# 사용: ./publish.sh "커밋 메시지"   (메시지 생략 시 자동 stamp)
#
# 흐름: (1) SYMPOSIUM 사본을 공개 repo로 rsync (cruft 제외)
#       (2) 공개 repo에서 add/commit/push (PUBLIC — 시크릿 없음 재확인)
set -e
SYM=${0:A:h}                                   # SYMPOSIUM/HSWM/prom_search_hswm
PUB=$HOME/CD/HSWM/prom_search_hswm             # 공개 repo 내 미러 경로
MSG=${1:-"chore(research): prom_search_hswm 공개 미러 동기화"}

if [ ! -d "$HOME/CD/HSWM/.git" ]; then echo "ERROR: ~/CD/HSWM 공개 repo 없음" >&2; exit 1; fi

# 시크릿 가드 — 흔한 키 패턴이 섞이면 중단 (publish.sh 자신=패턴 담아서 제외)
SECRET_RE='(sk-[A-Za-z0-9]{20}|AKIA[0-9A-Z]{16}|-----BEGIN[A-Z ]*PRIVATE KEY|password[[:space:]]*=[[:space:]]*['"'"'"][^'"'"'"]+)'
HITS=$(grep -rIlE "$SECRET_RE" "$SYM" --exclude-dir=__pycache__ --exclude='*.log' --exclude='publish.sh' 2>/dev/null || true)
if [ -n "$HITS" ]; then
  echo "ERROR: 시크릿 의심 패턴 발견 — 발행 중단:" >&2; echo "$HITS" >&2; exit 2
fi

# 미러 역행 가드 (2026-07-23 신설) — 공개 미러에만 있는 파일이 있으면 아래 --delete 가 그것들을 지운다.
# 실제 사고 직전까지 감: 공개 repo 쪽 agent 워크트리(GIT/hswm_*)가 직접 커밋하면서
# B2.1 router evidence·shadow-gate 코드/테스트·judgments 등 37 파일이 미러에만 존재했다.
if [ -d "$PUB" ]; then
  FIND_FILES='find . -type f -not -path "*/__pycache__/*" -not -path "./.pytest_cache/*"'
  ONLY_IN_PUB=$(diff <(cd "$PUB" && eval "$FIND_FILES" | sort) <(cd "$SYM" && eval "$FIND_FILES" | sort) | grep '^<' || true)
  if [ -n "$ONLY_IN_PUB" ] && [ "$2" != "--force" ]; then
    echo "ERROR: 공개 미러에만 있는 파일 발견 — rsync --delete 가 이것들을 지운다. 발행 중단:" >&2
    echo "$ONLY_IN_PUB" >&2
    echo "먼저 작업처로 백포트해라:" >&2
    echo "  rsync -a --exclude=__pycache__ --exclude=.pytest_cache \"$PUB/\" \"$SYM/\"" >&2
    echo "(정말 삭제가 의도라면: ./publish.sh \"메시지\" --force)" >&2
    exit 3
  fi
fi

echo "[publish] rsync $SYM → $PUB" >&2
rsync -a --delete --exclude='__pycache__' --exclude='*.log' --exclude='.DS_Store' "$SYM/" "$PUB/"

cd "$HOME/CD/HSWM"
git pull --no-edit origin main >/dev/null 2>&1 || true
git add prom_search_hswm/
if git diff --cached --quiet; then echo "[publish] 변경 없음 — skip" >&2; exit 0; fi
git commit --no-verify -m "$MSG

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" >&2
git push --no-verify origin main 2>&1 | tail -3
echo "[publish] 공개 HEAD=$(git rev-parse --short HEAD) — https://github.com/gj3447/HSWM/tree/main/prom_search_hswm" >&2
