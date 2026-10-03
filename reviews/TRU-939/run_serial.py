"""Resume the exact-head Rust review without competing with shared build lanes.

Usage: python3 reviews/TRU-939/run_serial.py /home/truewire/work/scratch/TRU-939
The prepared client is archived from 962d665, with only the recorded Cargo overlay.
Exit 75 means no compilation started; retry only when the build lane is available.
"""
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
handles = []
for name in [
    "/home/truewire/verify/lock",
    "/home/truewire/verify/lock-main",
    "/home/truewire/verify/lock-weather-gov",
    "/home/truewire/work/scratch/rust-build.lock",
]:
    handle = open(name, "a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"BLOCKED: {name}; no build started", flush=True)
        sys.exit(75)
    handles.append(handle)

env = {key: value for key, value in os.environ.items()
       if not key.startswith(("CARGO_", "RUSTFLAGS", "RUSTDOCFLAGS", "PYTHON", "VIRTUAL_ENV"))}
env.update(CARGO_BUILD_JOBS="1", RUSTFLAGS="-D warnings",
           TRUEWIRE_BIN=str(root / "venv/bin/truewire"), RUST_TEST_THREADS="1")
env["PATH"] = str(root / "venv/bin") + os.pathsep + env["PATH"]
client = root / "client"

def run(name, command):
    with (root / name).open("w") as log:
        log.write(f"command: {command!r}\nCARGO_BUILD_JOBS=1 RUSTFLAGS=-D warnings RUST_TEST_THREADS=1\n")
        log.flush()
        result = subprocess.run(command, cwd=client, env=env, stdout=log,
                                stderr=subprocess.STDOUT, timeout=1200)
    print(f"{name}: exit {result.returncode}", flush=True)
    return result.returncode

# Published CLI 0.11 uses a positional language, not --language.
code = run("rust-suite.log", [env["TRUEWIRE_BIN"], "test", "rust", "--project", str(client)])
if code:
    sys.exit(code)
test = client / "packages/rust/tests/review_wire.rs"
shutil.copyfile(Path(__file__).with_name("wire.rs"), test)
try:
    code = run("rust-wire.log", ["cargo", "test", "--locked", "--manifest-path",
               str(client / "packages/rust/Cargo.toml"), "--test", "review_wire"])
finally:
    test.unlink()
sys.exit(code)
