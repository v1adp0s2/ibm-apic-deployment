#!/usr/bin/env bash
# Returns the root directory of the git repository containing this script.
# Works regardless of where the repo is cloned.
cd "$(dirname "${BASH_SOURCE[0]}")" && git rev-parse --show-toplevel
