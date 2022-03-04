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

# Include /usr/local/bin in path.
RUN echo "export PATH=${PATH}:/usr/local/bin >> ~/.bashrc"

# Basic Python tools
RUN pip install --upgrade pip setuptools ipython wheel uwsgi pipdeptree

USER root

echo "export VIRTUAL_ENV=/usr/local" >> /home/zenodo/.bashrc

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
RUN npm install npm@latest -g
RUN zenodo npm --pinned-file /code/zenodo/package.pinned.json \
    && cd ${INVENIO_INSTANCE_PATH}/static \
    && npm install \
    && cd /code/zenodo \
    && zenodo collect -v && zenodo assets build

#USER root

RUN sed -i.bak -e 's/^%admin/#%admin/' /etc/sudoers && \
    sed -i.bak -e 's/^%sudo/#%sudo/' /etc/sudoers && \
    adduser --uid 1000 --disabled-password --gecos '' zenodo && \
    chown -R zenodo:zenodo /code ${INVENIO_INSTANCE_PATH}

RUN echo "zenodo:secret" | chpasswd
RUN echo "zenodo ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/zenodo && chmod 0440 /etc/sudoers.d/zenodo

RUN mkdir -p /usr/local/var/data && \
    chown zenodo:zenodo /usr/local/var/data -R && \
    mkdir -p /usr/local/var/run && \
    chown zenodo:zenodo /usr/local/var/run -R && \
    mkdir -p /var/log/zenodo && \
    chown zenodo:zenodo /var/log/zenodo -R

#COPY ./docker/docker-entrypoint.sh /

RUN sed -i "s|'force_https': True|'force_https': False|" /usr/local/lib/python2.7/site-packages/invenio_app/config.py

USER zenodo
VOLUME ["/code/zenodo"]
#ENTRYPOINT ["/docker-entrypoint.sh"]
ENTRYPOINT ["/code/zenodo/docker/docker-entrypoint.sh"]
CMD ["zenodo", "run", "-h", "0.0.0.0"]