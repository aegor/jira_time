#!/usr/bin/env python3

import telebot
import subprocess
import os
import threading
import datetime
from config import xls_file


# local vars
#OUR_CHAT = -238585802
OUR_CHAT = 237514032
#TOKEN = '399435685:AAHuKxVlc6CtlnOKT_1FkzptPEp5SmtaWlc'
TOKEN = '348310951:AAGlBa068nqUPb1HeaFta7Q8ZLb1yjyKZuU'  # this is the test chat
bot = telebot.TeleBot(TOKEN)

bot.send_chat_action(OUR_CHAT, 'typing')
update_db = 'python3 update_db.py'
get_report = "python3 update_db.py -t y"
pr = subprocess.Popen(get_report.split(), stdout=subprocess.PIPE)
output, error = pr.communicate()
TODAY = datetime.date.today()
bot.send_message(OUR_CHAT, '{0}'.format(TODAY)) # todo print date

# load report from local storage with today
doc = open(xls_file.format(TODAY), 'rb')
bot.send_document(OUR_CHAT, doc)
