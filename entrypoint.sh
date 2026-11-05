#!/bin/sh
set -e

# Start, release e comandos administrativos possuem ciclos explicitos.
if [ "$#" -eq 0 ]; then
  echo "Nenhum comando informado ao entrypoint." >&2
  exit 64
fi
exec "$@"
