FROM ubuntu:16.04

RUN apt-get update && apt-get install -y -q \
        aptitude \
        python3-pip \
        libreoffice \ 
        libreoffice-script-provider-python \
        uno-libs3 \
        python3-uno \
        python3 \
        locales \
        curl

RUN pip3 install unotools pytelegrambotapi==3.2.0

ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh && \
curl -o /usr/local/bin/mantra -L https://github.com/pugnascotia/mantra/releases/download/0.0.1/mantra && \
chmod +x /usr/local/bin/mantra && \
mkfifo --mode 0666 /var/log/cron.log && \
locale-gen en_US.UTF-8 && \
locale-gen ru_RU.UTF-8 && \
DEBIAN_FRONTEND=noninteractive dpkg-reconfigure locales

# copy application source and db

COPY pmo_time /opt/pmo/pmo_time

WORKDIR /opt/pmo


ENV DOCS_DIR /opt/Docs/
# this command must be initialized

RUN mkdir /opt/Docs
VOLUME /opt/Docs


ENTRYPOINT ["/entrypoint.sh"]
