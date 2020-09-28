from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import scrypt
from base64 import b64encode, b64decode
import getpass
import json
import os

def encrypt(pt, password):
  salt = get_random_bytes(32)
  key = scrypt(password, salt, key_len=32, N=2**20, r=8, p=1)
  nonce = get_random_bytes(12)
  cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
  ct, tag = cipher.encrypt_and_digest(pt)
  json_k = [ 'nonce', 'salt', 'ct', 'tag' ]
  json_v = [ b64encode(x).decode('utf-8') for x in (nonce, salt, ct, tag) ]
  result = json.dumps(dict(zip(json_k, json_v)))

  return result

def decrypt(ct, password):
  try:
    b64Ct = json.loads(ct)
    json_k = [ 'nonce', 'salt', 'ct', 'tag' ]
    json_v = {k:b64decode(b64Ct[k]) for k in json_k}

    key = scrypt(password, json_v['salt'], key_len=32, N=2**17, r=8, p=1)
    cipher = AES.new(key, AES.MODE_GCM, nonce=json_v['nonce'])
    ptData = cipher.decrypt_and_verify(json_v['ct'], json_v['tag'])

    return ptData
  except (KeyError, ValueError):
    print("Incorrect Password.")
    exit(0)

def main():

  password = getpass.getpass(prompt='Password: ')

  if not os.path.isfile('../amazon_config.enc'):
    ptFile = open('../amazon_config.json', 'rb')
    data = ptFile.read()
    ct = encrypt(data, password)

    ctFile = open('../amazon_config.enc', 'w')
    ctFile.write(ct)
    ctFile.close()

  ctFile = open('../amazon_config.enc', 'r')
  data = ctFile.read()
  pt = decrypt(data, password)
  print(pt)

main()