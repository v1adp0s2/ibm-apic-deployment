#!/bin/bash
################################################################################
# Environment Variable Substitution for YAML Files
################################################################################
# This script processes YAML files and replaces ${VAR_NAME} placeholders with
# actual environment variable values.
#
# Usage:
#   ./envsubst-yaml.sh <input.yaml> [output.yaml]
#   cat input.yaml | ./envsubst-yaml.sh > output.yaml
#
# If output file is not specified, writes to stdout.
# If input file is not specified, reads from stdin.
################################################################################

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

# Function to perform environment variable substitution
# Supports:
#   ${VAR}           - simple substitution
#   ${VAR:-default}  - with default value
#   ${VAR:?message}  - with error if unset
envsubst_safe() {
    local content="$1"
    local line_num=0
    local errors=0

    # Process line by line to preserve YAML structure
    while IFS= read -r line; do
        ((line_num++))

        # Find all ${VAR} patterns in the line
        local processed_line="$line"

        # Match ${VAR}, ${VAR:-default}, ${VAR:?error}
        while [[ "$processed_line" =~ \$\{([A-Z_][A-Z0-9_]*)(:-([^}]*))?\} ]] || \
              [[ "$processed_line" =~ \$\{([A-Z_][A-Z0-9_]*)(:?([^}]*))?\} ]]; do

            local full_match="${BASH_REMATCH[0]}"
            local var_name="${BASH_REMATCH[1]}"
            local operator="${BASH_REMATCH[2]}"
            local value="${BASH_REMATCH[3]}"

            # Check if variable is set
            if [[ -n "${!var_name:-}" ]]; then
                # Variable is set, use its value
                processed_line="${processed_line//${full_match}/${!var_name}}"
            elif [[ "$operator" == ":-"* ]]; then
                # Use default value
                processed_line="${processed_line//${full_match}/${value}}"
                log_warn "Line $line_num: Using default value for \${$var_name}: '$value'"
            elif [[ "$operator" == ":?"* ]]; then
                # Error if unset
                log_error "Line $line_num: Required variable \$$var_name is not set: ${value:-variable is required}"
                ((errors++))
                processed_line="${processed_line//${full_match}/MISSING_${var_name}}"
            else
                # No default, leave empty or warn
                log_warn "Line $line_num: Variable \$$var_name is not set, replacing with empty string"
                processed_line="${processed_line//${full_match}/}"
            fi
        done

        echo "$processed_line"
    done <<< "$content"

    return $errors
}

# Main script
main() {
    local input_file="${1:-}"
    local output_file="${2:-}"

    # Read input
    local content
    if [[ -n "$input_file" && -f "$input_file" ]]; then
        log_info "Reading from file: $input_file"
        content=$(<"$input_file")
    else
        if [[ -n "$input_file" ]]; then
            log_error "Input file not found: $input_file"
            exit 1
        fi
        # Read from stdin
        content=$(cat)
    fi

    # Process content
    local processed_content
    processed_content=$(envsubst_safe "$content")
    local exit_code=$?

    # Write output
    if [[ -n "$output_file" ]]; then
        echo "$processed_content" > "$output_file"
        log_info "Written to: $output_file"
    else
        echo "$processed_content"
    fi

    if [[ $exit_code -ne 0 ]]; then
        log_error "Substitution completed with $exit_code errors"
        exit 1
    fi

    return 0
}

# Help message
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    cat << 'EOF'
Environment Variable Substitution for YAML Files

Usage:
  envsubst-yaml.sh <input.yaml> [output.yaml]
  cat input.yaml | envsubst-yaml.sh > output.yaml

Syntax:
  ${VAR}           - Replace with value of $VAR (empty if unset)
  ${VAR:-default}  - Replace with $VAR or 'default' if unset
  ${VAR:?message}  - Replace with $VAR or error with 'message' if unset

Examples:
  # Process single file
  ./envsubst-yaml.sh template.yaml output.yaml

  # Process with config
  source config.env
  ./envsubst-yaml.sh template.yaml output.yaml

  # Process all YAML files
  find . -name "*.yaml.template" | while read f; do
    ./envsubst-yaml.sh "$f" "${f%.template}"
  done

EOF
    exit 0
fi

main "$@"
