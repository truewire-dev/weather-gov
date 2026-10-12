#!/bin/sh
# Python user program against weather-gov #23. Expect exactly two pyright errors:
# line 9 (stationType, as get_profiler's doc says, is no list_stations keyword) and line 14 ('xds').
# After the doc fix, line 9 is the only one to delete; same_host must stay clean.
set -e
cd "$(dirname "$0")"
pyright user.py
