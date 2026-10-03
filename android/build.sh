#!/usr/bin/env bash
#
# Builds the offline APK.
#
# Nothing is downloaded: the Android SDK and a Gradle distribution that are
# already on this machine are used through the environment variables below, and
# the Gradle dependency cache is mounted read-only so the build cannot write
# into the other project's toolchain.
#
#   ./build.sh            debug APK (installable straight away)
#   ./build.sh release    unsigned release APK
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
TOOLCHAIN="$ROOT/../Financial Overview/.toolchain"

# --- toolchain, all of it already present -------------------------------------
export ANDROID_HOME="$TOOLCHAIN/sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export JAVA_HOME="${JAVA_HOME:-$(/usr/libexec/java_home -v 17 2>/dev/null || /usr/libexec/java_home -v 19)}"
GRADLE="$TOOLCHAIN/gradle/gradle-8.11.1/bin/gradle"

# Writes go here, inside this project.
export GRADLE_USER_HOME="$HERE/.gradle-home"
# The dependency cache from the prepared toolchain is copied here once, not
# mounted read-only: GRADLE_RO_DEP_CACHE breaks the build, because Gradle's
# artifact transforms write their output beside the cached jars and a read-only
# cache fails with "Transform output ... must be a part of the input artifact".
SEED="$HERE/.gradle-home/caches/modules-2"
# The check is for the filled cache, not the directory: a failed build creates
# an empty modules-2, and testing for the directory alone would then skip the
# copy for ever.
if [ ! -d "$SEED/files-2.1" ]; then
  echo "seeding dependency cache (once, ~107 MB)…"
  mkdir -p "$SEED"
  cp -R "$TOOLCHAIN/gradle-home/caches/modules-2/." "$SEED/"
fi
# The debug keystore is generated on first build and kept in the project.
export ANDROID_USER_HOME="$HERE/.android"

# --- the web app, copied in fresh so the APK cannot go stale ------------------
ASSETS="$HERE/app/src/main/assets"
rm -rf "$ASSETS"
mkdir -p "$ASSETS/data/images"
cp "$ROOT/index.html" "$ASSETS/index.html"
cp "$ROOT/data/questions.js" "$ASSETS/data/questions.js"
cp "$ROOT"/data/images/*.jpg "$ASSETS/data/images/"
echo "assets: $(find "$ASSETS" -type f | wc -l | tr -d ' ') files, $(du -sh "$ASSETS" | cut -f1)"

# --- build --------------------------------------------------------------------
TASK="assembleDebug"
[ "${1:-debug}" = "release" ] && TASK="assembleRelease"

cd "$HERE"
"$GRADLE" --offline --no-daemon --console=plain "$TASK"

APK="$(find "$HERE/app/build/outputs/apk" -name '*.apk' | head -1)"
OUT="$ROOT/einbuergerungstest.apk"
[ "${1:-debug}" = "release" ] && OUT="$ROOT/einbuergerungstest-release-unsigned.apk"
cp "$APK" "$OUT"
echo
echo "APK: $OUT ($(du -h "$OUT" | cut -f1))"
