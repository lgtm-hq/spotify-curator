#!/usr/bin/env bash
# Run frontend CI whenever the workdir exists, even if its manifest is broken.
set -euo pipefail

if [[ -d frontend ]]; then
	echo 'present=true'
else
	echo 'present=false'
fi
