import base64
from Crypto.Cipher import AES
import string
import random
import os
import stat
import json

fileDir = '/var/lib/manmon'


class Auth():
    def __init__(self):
        with open('/var/lib/manmon/.constants', 'r') as f:
            config = json.load(f)
            self.__x = config['x']
            self.__y = config['y']
            self.__xout = config['xout']
            self.__xin = config['xin']
            self.__uploadhost = config['upload_host']

    def getUploadHostname(self):
        return self.__uploadhost

    def getKeyToSend(self, hostgroupkey=False):
        dec = AES.new(self.__x, AES.MODE_CBC, self.__y)
        k = ""
        if hostgroupkey:
            f = open(fileDir + "/.manmonhg", "r")
            k = f.read().strip()
            f.close()
        else:
            f = open(fileDir + "/.manmonh", "r")
            k = f.read().strip()
            f.close()

        d = dec.decrypt(base64.b64decode(k))
        chars = string.ascii_letters + string.digits + string.punctuation
        iv = ''.join((random.choice(chars)) for x in range(16))
        cipher = AES.new(self.__xout, AES.MODE_CFB, iv, segment_size=128)

        return base64.b64encode(iv.encode()+cipher.encrypt(d))

    def saveKey(self, bkey):
        s = base64.b64decode(bkey)
        cipher = AES.new(self.__xin, AES.MODE_CFB, s[:16], segment_size=128)
        d = ((cipher.decrypt(s[16:])).decode("UTF-8"))
        enc = AES.new(self.__x, AES.MODE_CBC, self.__y)
        ss = base64.b64encode(enc.encrypt(d))
        f = open(fileDir + "/.manmonh", "wb")
        f.write(ss)
        f.close()
        os.chmod(fileDir + "/.manmonh", stat.S_IWUSR | stat.S_IRUSR)

    def saveHostGroupKey(self, bkey):
        s = base64.b64decode(bkey)
        cipher = AES.new(self.__xin, AES.MODE_CFB, s[:16], segment_size=128)
        d = ((cipher.decrypt(s[16:])).decode("UTF-8"))
        enc = AES.new(self.__x, AES.MODE_CBC, self.__y)
        ss = base64.b64encode(enc.encrypt(d))
        f = open(fileDir + "/.manmonhg", "wb")
        f.write(ss)
        f.close()


