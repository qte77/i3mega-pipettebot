#!/usr/bin/env bats
# Coverage for `make dev_diagram` (issue #130): a dry-run smoke test
# (no real npm/diagramforge required) plus a shellcheck pass on the
# recipe's expanded shell body.

setup() {
    REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
}

@test "make -n dev_diagram prints the expected commands without executing them" {
    run make -C "$REPO_ROOT" -n dev_diagram
    [ "$status" -eq 0 ]
    [[ "$output" == *"diagramforge"* ]]
    [[ "$output" == *"npm --prefix diagramforge run dev"* ]]
}

@test "dev_diagram recipe body passes shellcheck" {
    command -v shellcheck >/dev/null 2>&1 || skip "shellcheck not installed"
    run make -C "$REPO_ROOT" -n dev_diagram
    [ "$status" -eq 0 ]
    script="$BATS_TEST_TMPDIR/dev_diagram.sh"
    {
        echo "#!/usr/bin/env bash"
        echo "$output"
    } > "$script"
    run shellcheck -s bash "$script"
    [ "$status" -eq 0 ]
}
