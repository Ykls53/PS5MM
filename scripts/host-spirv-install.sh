#!/usr/bin/env bash
# SPIRV-Tools is what glslang's optimizer needs; the system only ships it in a
# dev package. Install it and report what is now present.
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
echo "==== before ===="
ls /usr/lib/x86_64-linux-gnu/libSPIRV-Tools* 2>/dev/null || echo "(none)"
apt-get install -y -qq spirv-tools libspirv-tools-dev > /tmp/apt-spirv.log 2>&1
echo "apt exit=$?"
echo "==== after ===="
ls /usr/lib/x86_64-linux-gnu/libSPIRV-Tools* 2>/dev/null || echo "(still none)"
tail -3 /tmp/apt-spirv.log
