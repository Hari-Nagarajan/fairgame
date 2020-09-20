import logging

log = logging.getLogger("Foo")
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(levelname)s: "%(asctime)s - %(message)s'))

log.addHandler(handler)
