#!/bin/sh
set -eu

chown boda:boda /app/data
exec runuser -u boda -- "$@"
