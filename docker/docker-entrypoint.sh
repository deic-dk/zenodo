#!/usr/bin/env bash
#set -e

# Reinstalls zenodo. This is needed if the src is mounted into the container.
if [ ! -d "zenodo.egg-info" ]; then
    # Command will fail but the needed zenodo.egg-info folder is created.
    pip install -e . > /dev/null 2>&1
fi

env > /tmp/env
# These apparently also need a restart after the system has booted...
#sudo service rsyslog start
#sudo service postfix start

# https://docs.docker.com/engine/reference/builder/#entrypoint
exec $@
