#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/../.."
: "${PAPERCLIP_RUN_SCRATCH_DIR:?Set PAPERCLIP_RUN_SCRATCH_DIR to a directory under /home/truewire/work/scratch/TRU-995}"
probe_dir=$(mktemp -d "$PAPERCLIP_RUN_SCRATCH_DIR/consumer.XXXXXX")
packages/typescript/node_modules/.bin/tsc \
  --strict --target ES2022 --module NodeNext --moduleResolution NodeNext \
  --skipLibCheck --typeRoots packages/typescript/node_modules/@types \
  --rootDir . --outDir "$probe_dir" --noEmitOnError reviews/TRU-995/consumer.mts
printf '{"type":"module"}\n' > "$probe_dir/package.json"
ln -s "$PWD/packages/typescript/node_modules" "$probe_dir/node_modules"
node "$probe_dir/reviews/TRU-995/consumer.mjs"
