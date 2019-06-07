from os import walk, remove
from os.path import isfile
import logging
import requests
from manmon.auth import Auth
from random import randint
from time import sleep
from datetime import datetime
import threading
import json
import socket
import sys

logging.basicConfig(filename='/var/lib/manmon/uploader.log',level=logging.DEBUG,format='%(asctime)-15s %(levelname)s %(message)s')

uploadFileDir = "/var/lib/manmon/pkg-uploads"
checksumFileDir = "/var/lib/manmon/pkg-checksums"
connectTimeOut=5
readTimeout=15

class DataUploader():
    def __init__(self):
        self.session = requests.session()
        self.sessionInitialized = False
        self.id = None
        self.key = None
        self.auth = Auth()

    def executePost(self, uri, filepath, headers={'content-type':'application/json'}):
        if not self.sessionInitialized:
            if isfile('/var/lib/manmon/.manmonh') and isfile('/var/lib/manmon/.manmonid'):
                self.key = self.auth.getKeyToSend()
                f = open("/var/lib/manmon/.manmonid", "r")
                self.id = f.read().strip()
                f.close()
                self.sessionInitialized = True
            elif isfile('/var/lib/manmon/.manmonhg'):
                hgkey = self.auth.getKeyToSend(hostgroupkey=True)
                hostname = socket.gethostname()
                if isfile("/var/lib/manmon/manmon-hostname"):
                    f = open("/var/lib/manmon/manmon-hostname","r")
                    hostname = f.read().strip()
                    f.close()
                response = self.session.post(self.auth.getUploadHostname()+"/manmon-uploader/auth-with-hostgroup-key", hostname, headers=headers, cert=('/var/lib/manmon/.manmon_crt', '/var/lib/manmon/.manmon_key'), verify='/var/lib/manmon/.manmon_ca',auth=('hg',hgkey), timeout=(connectTimeOut,readTimeout))
                if response.status_code == 200:
                    logging.info("Authenticated with hostgroup key and got host key")
                    respobj = json.loads(response.text.strip())
                    self.auth.saveKey(respobj["key"])
                    f = open("/var/lib/manmon/.manmonid","w")
                    f.write(respobj["id"])
                    f.close()
                    self.id = respobj["id"]
                    self.key = self.auth.getKeyToSend()
                    self.sessionInitialized = True
                    return self.session.post(self.auth.getUploadHostname()+uri,  open(filepath, 'rb'), headers={'content-type':'application/x-gzip'}, cert=('/var/lib/manmon/.manmon_crt', '/var/lib/manmon/.manmon_key'), verify='/var/lib/manmon/.manmon_ca',auth=(self.id,self.key), timeout=(connectTimeOut,readTimeout))
                else:
                    logging.error("Error authenticating with hostgroup key")
            else:
                logging.error("No authentication infomation")

        if self.sessionInitialized:
            return self.session.post(self.auth.getUploadHostname()+uri, open(filepath, 'rb'), headers={'content-type':'application/x-gzip'}, cert=('/var/lib/manmon/.manmon_crt', '/var/lib/manmon/.manmon_key'), verify='/var/lib/manmon/.manmon_ca',auth=(self.id,self.key), timeout=(connectTimeOut,readTimeout))

uploader=DataUploader()


class MonitoringUploader(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.dataTypes=["data_min", "data_5min", "data_15min", "data_hour", "data_day", "data_week", "data_month"]

    def run(self):
        while True:
            if int(datetime.utcnow().strftime('%S')) == 3:
                sleep(randint(0,3000)/1000)
                self.uploadMonitoringData()
                sleep(2)
            sleep(0.1)

    def uploadFile(self, fullpath, dataType):
        if not fullpath.endswith(".notready"):
            uri = "/manmon-uploader/upload?datatype=" + dataType
            response = uploader.executePost(uri, fullpath)
            if response.status_code == 200:
                logging.debug("Uploaded " + fullpath)
                remove(fullpath)
            elif response.status_code == 406:
                logging.error("Invalid data - removed " + fullpath)
                remove(fullpath)
            else:
                logging.error("Error uploading " + fullpath)

    def uploadFirstFiles(self):
        for dataType in self.dataTypes:
            for (dirpath, dirnames, filenames) in walk("/var/lib/manmon/uploads/" + dataType):
                sortedFilenames = []
                for filename in filenames:
                    sortedFilenames.append(filename)
                sortedFilenames.sort(reverse=True)
                isFirstFileInDir = True
                for filename in sortedFilenames:
                    if isFirstFileInDir:
                        fullpath = "/var/lib/manmon/uploads/" + dataType + "/" + filename
                        self.uploadFile(fullpath, dataType)
                        isFirstFileInDir = False
                        sleep(0.1)


    def uploadOlderFiles(self):
        for dataType in self.dataTypes:
            for (dirpath, dirnames, filenames) in walk("/var/lib/manmon/uploads/" + dataType):
                sortedFilenames = []
                for filename in filenames:
                    sortedFilenames.append(filename)
                sortedFilenames.sort(reverse=True)
                for filename in sortedFilenames:
                    fullpath = "/var/lib/manmon/uploads/" + dataType + "/" + filename
                    self.uploadFile(fullpath, dataType)
                    sleep(0.1)

    def uploadMonitoringData(self):
        try:
            self.uploadFirstFiles()
            self.uploadOlderFiles()
        except requests.exceptions.RequestException as e:
            ex_type, ex_value, ex_traceback = sys.exc_info()
            if str(ex_value) == "('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))":
                logging.info("Reconnecting")
                try:
                    sleep(1)
                    self.uploadFirstFiles()
                    self.uploadOlderFiles()
                except requests.exceptions.RequestException as ee:
                    logging.error("Exception even after reconnecting: "+str(e))
            else:
                logging.error("Exception:" + str(e))
        except Exception as ex:
            logging.error("Exception:" + str(ex))
            sleep(10)
