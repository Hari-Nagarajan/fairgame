from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import scrypt
import getpass
import os

def encrypt(pt, password):
  BUFFER_SIZE = 1024 * 1024

  inFile = "../amazon_config.json"
  outFile = "../amazon_config.enc"

  ptIn = open(inFile, 'rb')
  ctOut = open(outFile, 'wb')

  salt = get_random_bytes(32)
  key = scrypt(password, salt, key_len=32, N=2**17, r=8, p=1)
  ctOut.write(salt)

  cipher = AES.new(key, AES.MODE_GCM)
  ctOut.write(cipher.nonce)

  dataIn = ptIn.read(BUFFER_SIZE)
  while len(dataIn) != 0:
    ct = cipher.encrypt(dataIn)
    ctOut.write(ct)
    dataIn = ptIn.read(BUFFER_SIZE)

  tag = cipher.digest()
  ctOut.write(tag)

  ptIn.close()
  ctOut.close()

def decrypt(ct, password):
    BUFFER_SIZE = 1024 * 1024

    inFile = "../amazon_config.enc"

    ctIn = open(inFile, 'rb')

    salt = ctIn.read(32)
    key = scrypt(password, salt, key_len=32, N=2**17, r=8, p=1)

    nonce = ctIn.read(16)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

    size = os.path.getsize("../amazon_config.enc")
    ctSize = size - 32 - 16 - 16

    for _ in range(int(ctSize / BUFFER_SIZE)):
      ctData = ctIn.read(BUFFER_SIZE)
      ptData = cipher.decrypt(ctData)

    ctData = ctIn.read(int(ctSize % BUFFER_SIZE))
    ptData = cipher.decrypt(ctData)
    return ptData


def main():

  password = getpass.getpass(prompt='Password: ')

  if not os.path.isfile('../amazon_config.enc'):
    ptFile = open('../amazon_config.json', 'rb')
    data = ptFile.read()
    ct = encrypt(data, password)
    print(ct)

  ctFile = open('../amazon_config.enc', 'rb')
  data = ctFile.read()
  pt = decrypt(data, password)
  print(pt)

main()