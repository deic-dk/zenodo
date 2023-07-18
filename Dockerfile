#
# Zenodo development docker build
#
FROM python:2.7
MAINTAINER Zenodo <info@zenodo.org>

ARG TERM=linux
ARG DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN bash -c "debconf-set-selections <<< \"postfix postfix/mailname string sciencedata.dk\""
RUN bash -c "debconf-set-selections <<< \"postfix postfix/main_mailer_type string 'Internet Site'\""

# See https://github.com/zenodo/zenodo/issues/2123#issuecomment-1050851252
# if problems with node versions arise

RUN apt-get update \
    && apt-get -qy upgrade --fix-missing --no-install-recommends \
    && apt-get -qy install --fix-missing --no-install-recommends \
        apt-utils curl libcairo2-dev fonts-dejavu libfreetype6-dev \
        uwsgi-plugin-python vim rsyslog postfix\
    # Got things working with new nodejs version.
    # Another approach is https://github.com/zenodo/zenodo/issues/2123
    # Node.js
    && curl -sL https://deb.nodesource.com/setup_6.x | bash - \
    && apt-get -qy install --fix-missing --no-install-recommends \
        nodejs npm sudo \
    # Slim down image
    && apt-get clean autoclean \
    && apt-get autoremove -y \
    && rm -rf /var/lib/{apt,dpkg}/ \
    && rm -rf /usr/share/man/* /usr/share/groff/* /usr/share/info/* \
    && find /usr/share/doc -depth -type f ! -name copyright -delete


# Basic Python tools
RUN pip install --upgrade pip setuptools ipython wheel uwsgi pipdeptree

USER root


# NPM
COPY ./scripts/setup-npm.sh /tmp
RUN export npm_config_user=root; /tmp/setup-npm.sh

#
# Zenodo specific
#

# Create instance/static folder
ENV INVENIO_INSTANCE_PATH /usr/local/var/instance
RUN mkdir -p ${INVENIO_INSTANCE_PATH}
WORKDIR /tmp

# Copy and install requirements. Faster build utilizing the Docker cache.
COPY requirements*.txt /tmp/
RUN mkdir -p /usr/local/src/ \
    && mkdir -p /code/zenodo \
    && pip install -r requirements.txt --src /usr/local/src

# Copy source code
COPY . /code/zenodo
WORKDIR /code/zenodo

# Install Zenodo
RUN pip install -e .[postgresql,elasticsearch2,all] \
    && python -O -m compileall .

# Install npm dependencies and build assets.
#RUN npm install npm@6.14.17 -g
#RUN npm install strip-ansi --save
RUN zenodo npm --pinned-file /code/zenodo/package.pinned.json
# Replace "git" with "git+https" protocol for git dependencies
RUN sed -i 's/git\:\/\/github\.com/git+https\:\/\/github\.com/g' /code/zenodo/package.pinned.json && \
sed -i 's|git://github.com/|https://github.com/|' ${INVENIO_INSTANCE_PATH}/static/package.json

RUN git config --global url."https://".insteadOf git://

RUN cd ${INVENIO_INSTANCE_PATH}/static \
    && npm install
RUN cd /code/zenodo \
    && zenodo collect -v && zenodo assets build

RUN sed -i.bak -e 's/^%admin/#%admin/' /etc/sudoers && \
    sed -i.bak -e 's/^%sudo/#%sudo/' /etc/sudoers && \
    adduser --uid 80 --disabled-password --gecos '' www && \
    chown -R www:www /code ${INVENIO_INSTANCE_PATH}

# Include /usr/local/bin in path.
RUN echo "export PATH=${PATH}:/usr/local/bin" >> /home/www/.bashrc && \
echo "export VIRTUAL_ENV=/usr/local" >> /home/www/.bashrc

RUN sed -i '/imklog/s/^/#/' /etc/rsyslog.conf
    
RUN echo "www:secret" | chpasswd
RUN echo "www ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/www && chmod 0440 /etc/sudoers.d/www

RUN mkdir -p /usr/local/var/data && \
    chown www:www /usr/local/var/data -R && \
    mkdir -p /usr/local/var/run && \
    chown www:www /usr/local/var/run -R && \
    mkdir -p /var/log/zenodo && \
    chown www:www /var/log/zenodo -R

RUN sed -i "s|'force_https': True|'force_https': False|" /usr/local/lib/python2.7/site-packages/invenio_app/config.py

USER www
#VOLUME ["/code/zenodo"]
#ENTRYPOINT ["/docker-entrypoint.sh"]
ENTRYPOINT ["/code/zenodo/docker/docker-entrypoint.sh"]
#CMD ["zenodo", "run", "-h", "0.0.0.0"]

