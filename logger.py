import logging
from datetime import date
import os

mylvl = logging.DEBUG
log_file = 'report_%s.txt' % (date.today().strftime('%Y_%m_%d'))

logger = logging.getLogger('proxy_db')
logger.setLevel(mylvl)
formatter = logging.Formatter(fmt='%(asctime)s [%(name)s] %(levelname)-4s [%(filename)s:%(funcName)s:%(lineno)d] %(message)s', datefmt='%d-%m-%Y:%H:%M:%S')

#stdouthandler = logging.StreamHandler()
#stdouthandler.setLevel(mylvl)
#stdouthandler.setFormatter(formatter)
#logger.addHandler(stdouthandler)

handler = logging.FileHandler(log_file)
handler.setLevel(mylvl)
handler.setFormatter(formatter)
logger.addHandler(handler)
