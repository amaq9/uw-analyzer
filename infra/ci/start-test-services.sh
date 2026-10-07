#!/usr/bin/env bash
# Starts the S3-compatible object store and the ClamAV virus scanner used by the upload tests,
# then waits until both answer. Used by CI; also works locally (see docs/runbooks/local-development.md).
# Images are pinned by digest so a CI run is reproducible.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows must not rewrite container paths

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
S3_IMAGE="chrislusf/seaweedfs@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d"
CLAMAV_IMAGE="clamav/clamav@sha256:ebec5bc138401b36ae987caa1a3fa3c3b2a21ed3d51f0bfa5852825e663e67b0"

docker rm -f uw-test-s3 uw-test-clamav >/dev/null 2>&1 || true

docker run -d --name uw-test-s3 -p 8333:8333 \
  -v "$ROOT/infra/s3-dev-config.json:/etc/seaweedfs/s3.json:ro" \
  "$S3_IMAGE" \
  server -s3 -s3.port=8333 -s3.config=/etc/seaweedfs/s3.json -dir=/data -ip.bind=0.0.0.0 >/dev/null

docker run -d --name uw-test-clamav -p 3310:3310 "$CLAMAV_IMAGE" >/dev/null

echo "Waiting for object storage..."
for _ in $(seq 1 60); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8333/ || true)"
  [ "$code" != "000" ] && break
  sleep 2
done
[ "$code" != "000" ] || { echo "object storage did not start"; docker logs uw-test-s3 | tail -20; exit 1; }

echo "Waiting for the virus scanner (can take a minute while signatures load)..."
for _ in $(seq 1 100); do
  reply="$(python3 - <<'PY' 2>/dev/null || true
import socket
try:
    s = socket.create_connection(("localhost", 3310), 3)
    s.sendall(b"zPING\0")
    print(s.recv(16).strip(b"\0").decode())
except OSError:
    pass
PY
)"
  [ "$reply" = "PONG" ] && break
  sleep 3
done
[ "$reply" = "PONG" ] || { echo "virus scanner did not start"; docker logs uw-test-clamav | tail -20; exit 1; }

echo "Both services are ready."
