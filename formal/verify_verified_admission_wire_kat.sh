#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cli=${1:-"$script_dir/.lake/build/bin/HSWMAdmissionKernelCli"}

# The checked-in text fixtures have their normal terminal newline; the wire
# deliberately does not. Remove only line terminators before replay/comparison.
accepted_request=$(tr -d '\r\n' < "$script_dir/testdata/verified_admission_wire_accepted.request.json")
accepted_expected=$(tr -d '\r\n' < "$script_dir/testdata/verified_admission_wire_accepted.response.json")
accepted_actual=$(printf '%s' "$accepted_request" | "$cli")
test "$accepted_actual" = "$accepted_expected"

rejected_request=$(tr -d '\r\n' < "$script_dir/testdata/verified_admission_wire_conditions_rejected.request.json")
rejected_expected=$(tr -d '\r\n' < "$script_dir/testdata/verified_admission_wire_conditions_rejected.response.json")
rejected_actual=$(printf '%s' "$rejected_request" | "$cli")
test "$rejected_actual" = "$rejected_expected"

malformed_request=$(tr -d '\r\n' < "$script_dir/testdata/verified_admission_wire_rejected.request.json")
malformed_expected=$(tr -d '\r\n' < "$script_dir/testdata/verified_admission_wire_rejected.stderr.txt")
rejected_stderr=$(mktemp)
trap 'rm -f "$rejected_stderr"' EXIT
if printf '%s' "$malformed_request" | "$cli" >/dev/null 2>"$rejected_stderr"; then
  exit 1
fi
test "$(tr -d '\r\n' < "$rejected_stderr")" = "$malformed_expected"
