import logging

log = logging.getLogger("nvidia-bot")
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(levelname)s: "%(asctime)s - %(message)s'))

file_log_handler = logging.FileHandler('nvidia-bot.log')
file_log_handler.setFormatter(logging.Formatter('%(levelname)s: "%(asctime)s - %(message)s'))
log.addHandler(handler)
log.addHandler(file_log_handler)
