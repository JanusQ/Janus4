#!/usr/bin/env bash
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export JAVA_OPTS='-Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8'
export SBT_OPTS='-Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8'

source ~/anaconda3/etc/profile.d/conda.sh
source ~/firesim/env.sh

if [ -n "${JAVA_HOME:-}" ]; then
  export PATH="$JAVA_HOME/bin:$PATH"
fi
