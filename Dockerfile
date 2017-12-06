FROM ubuntu:14.04

RUN apt-get update && apt-get upgrade -y && apt-get install -y -q \
        aptitude \
        python3-pip

RUN aptitude install -y libreoffice libreoffice-script-provider-python uno-libs3 python3-uno python3

RUN pip3 install unotools pytelegrambotapi==3.2.0

WORKDIR /opt/pmo

# copy source of program and db
COPY pmo_time ./pmo_time

# configure cron to create and send weekly report
RUN echo '0 7 * * 1 /opt/pmo/pmo_time/bot.py' >> /var/spool/cron/crontabs/root
RUN echo '0 1 * * * /opt/pmo/pmo_time/update_db.py' >> /var/spool/cron/crontabs/root
RUN locale-gen en_US.UTF-8; locale-gen ru_RU.UTF-8;  export LANGUAGE=en_US.UTF-8; export LANG=en_US.UTF-8; export LC_ALL=en_US.UTF-8; DEBIAN_FRONTEND=noninteractive dpkg-reconfigure locales

ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
# this command must be initialized
ENTRYPOINT soffice --accept='socket,host=localhost,port=2002;urp;StarOffice.Service' --headless & /bin/bash
