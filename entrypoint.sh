#!/bin/sh

soffice --accept='socket,host=localhost,port=2002;urp;StarOffice.Service' --headless & 
/usr/local/bin/mantra "0 7 * * 1" /opt/pmo/pmo_time/bot.py >> /var/log/cron.log &
/usr/local/bin/mantra "0 1 * * *" /opt/pmo/pmo_time/update_db.py >> /var/log/cron.log &

tail -f /var/log/cron.log & wait $!
