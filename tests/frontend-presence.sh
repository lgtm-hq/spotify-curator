#!/usr/bin/env bash
# Verify presence detection without installing or executing a frontend.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="${ROOT}/scripts/ci/frontend-presence.sh"
TEST_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/frontend-presence.XXXXXX")"
trap 'rm -rf "$TEST_ROOT"' EXIT

assert_presence() {
	local directory="$1" expected="$2" actual
	actual="$(cd "$directory" && bash "$SCRIPT")"
	if [[ "$actual" != "present=${expected}" ]]; then
		printf 'Expected present=%s, got %s\n' "$expected" "$actual" >&2
		exit 1
	fi
}

# No frontend on main: do not call the reusable with a nonexistent workdir.
assert_presence "$TEST_ROOT" false

# A directory is sufficient: a broken/missing manifest must still reach CI
# and fail there, rather than being hidden as an absent frontend.
mkdir "$TEST_ROOT/frontend"
assert_presence "$TEST_ROOT" true
printf '{"private":true}\n' >"$TEST_ROOT/frontend/package.json"
assert_presence "$TEST_ROOT" true

# A file named frontend is not a usable working directory.
rm -r "$TEST_ROOT/frontend"
printf 'not a directory\n' >"$TEST_ROOT/frontend"
assert_presence "$TEST_ROOT" false

# Whitespace in the checkout path must not affect detection.
mkdir -p "$TEST_ROOT/checkout with spaces/frontend"
assert_presence "$TEST_ROOT/checkout with spaces" true

printf '5/5 frontend-presence cases passed\n'
