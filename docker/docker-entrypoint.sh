#!/usr/bin/env bash
#set -e

# Reinstalls zenodo. This is needed if the src is mounted into the container.
if [ ! -d "zenodo.egg-info" ]; then
    # Command will fail but the needed zenodo.egg-info folder is created.
    pip install -e . > /dev/null 2>&1
fi

# These apparently also need a restart after the system has booted...
#sudo service rsyslog start
#sudo service postfix start

# This is needed to be able to send mail via mailhotel.i2.dk
sudo sed -i 's|SECLEVEL=2|SECLEVEL=1|' /etc/ssl/openssl.cnf
sudo sed -i 's|preferred_auths = \[AUTH_CRAM_MD5, AUTH_PLAIN, AUTH_LOGIN\]|preferred_auths = [AUTH_PLAIN, AUTH_LOGIN]|' /usr/lib/python2.7/smtplib.py /usr/local/lib/python2.7/smtplib.py

sudo rm -f /tmp/uwsgi.log

# https://docs.docker.com/engine/reference/builder/#entrypoint
exec $@
