import telebot
import subprocess
import os
import threading

# local vars
OUR_CHAT = -238585802
TOKEN = '399435685:AAHuKxVlc6CtlnOKT_1FkzptPEp5SmtaWlc'

def light(text):
    colors = {
        'HEADER': '\033[95m',
        'OKBLUE': '\033[94m',
        'OKGREEN': '\033[92m',
        'WARNING': '\033[93m',
        'FAIL': '\033[91m',
        # 'ENDC': '\033[0m',
        # 'BOLD': '\033[1m',
        # 'UNDERLINE': '\033[4m',
    }
    from random import randint
    t = list(colors.keys())
    return str(colors[t[randint(0, len(t)-1)]] + str(text) + '\033[0m')

bot = telebot.TeleBot(TOKEN)



def compare_chat(id):
    def compare(msg):
        return msg.chat.id == id
    return compare    

@bot.message_handler(func=compare_chat(OUR_CHAT), commands=['makereport'])
def handler(msg):
    
    update_db = 'python3 update_db.py'
    open_office = "soffice --accept='socket,host=localhost,port=2002;urp;StarOffice.Service'"
    get_report = "python3 update_db.py -t y"
    #subprocess.call(open_office.split())
    thread = threading.Thread(target=subprocess.call, args=((open_office.split(),),))
    thread.start()
    pr = subprocess.Popen(get_report.split(), stdout=subprocess.PIPE)
    output, error = pr.communicate()
    print(light(msg))


if __name__ == "__main__":
    bot.polling(none_stop=True)