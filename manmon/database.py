import sqlite3
import datetime
import os
from io import StringIO
import gzip
#from mmauth import Authenticator
import requests
import logging
from os import chown
import pwd
from manmon.get_long import getLong

fileDir = '/var/lib/manmon'
copyDataLimit = 30

class ManmonAgentDatabase():
    def __init__(self):
        if not os.path.isdir(fileDir):
            os.makedirs(fileDir)
        self.createDbAndTables('data_min')
        self.mibConn = sqlite3.connect(fileDir+'/mib.db')
        self.mibCur = self.mibConn.cursor()
        self.setDts()
        self.lastSavedMinute = -1
        self.session = requests.session()

    def getUploadDataLimit(self, dataId):
        self.mibCur.execute("SELECT max_upload_list_size FROM mib_object WHERE id=?", (dataId,))
        return self.mibCur.fetchone()[0]

    def getOrder(self, dataId):
        self.mibCur.execute("SELECT descending_sort FROM mib_object WHERE id=?", (dataId,))
        if int(self.mibCur.fetchone()[0]) == 1:
            return "DESC"
        else:
            return "ASC"

    def getMibId(self, mibName):
        self.mibCur.execute("SELECT id FROM mib WHERE name=?", (mibName,))
        return self.mibCur.fetchone()[0]

    def getDataId(self, dataOidName):
        return self.getDataIdWithMib('MANMON-MIB', dataOidName)

    def getDataObjectId(self, dataOidName):
        return self.getDataObjectIdWithMib('MANMON-MIB', dataOidName)

    def getDataIdWithMib(self, mibName, dataOidName):
        mibId = self.getMibId(mibName)
        self.mibCur.execute("SELECT id,is_string_value FROM mib_object WHERE mib_id = ? AND value_column_name = ?", (mibId, dataOidName,))
        return self.mibCur.fetchone()

    def getDataObjectIdWithMib(self, mibName, dataOidName):
        mibId = self.getMibId(mibName)
        self.mibCur.execute("SELECT id,is_string_value FROM mib_object WHERE mib_id = ? AND name = ?", (mibId, dataOidName,))
        return self.mibCur.fetchone()

    def insertDataToDb(self, dataOidName, value):
        value=getLong(round(value))
        dataId = self.getDataObjectId(dataOidName)
        if dataId == None:
            logging.error("ERROR OID with name " + dataOidName + " not found")
        else:
            if dataId[1] == True:
                self.destCur.execute("INSERT INTO data_min_str VALUES (?,?,?,?,?)", (dataId[0], None, None, self.nextDt, value))
            else:
                self.destCur.execute("INSERT INTO data_min VALUES (?,?,?,?,?)", (dataId[0], None, None, self.nextDt, value))

    def insertDataToDbWithKeys(self, dataOidName, key1, key2, value):
        value = getLong(round(value))
        dataId = self.getDataId(dataOidName)
        if dataId == None:
            print ("ERROR OID with name " + dataOidName + " not found")
            logging.error("ERROR OID with name " + dataOidName + " not found")
        else:
            if dataId[1] == True:
                self.destCur.execute("INSERT INTO data_min_str VALUES (?,?,?,?,?)", (dataId[0], key1, key2, self.nextDt, value))
            else:
                self.destCur.execute("INSERT INTO data_min VALUES (?,?,?,?,?)", (dataId[0], key1, key2, self.nextDt, value))

    def createDbAndTables(self, tableName):
        if not os.path.isfile(fileDir + '/' + tableName + '.db'):
            conn = sqlite3.connect(fileDir + '/' + tableName + '.db')
            c = conn.cursor()
            c.execute(
                "CREATE TABLE " + tableName + " (dataid bigint, key1 varchar(255), key2 bigint, dt timestamp, value bigint)")
            c.execute("CREATE INDEX " + tableName + "_dataid_idx on " + tableName + "(dataid)")
            c.execute("CREATE INDEX " + tableName + "_key1_idx on " + tableName + "(key1)")
            c.execute("CREATE INDEX " + tableName + "_key2_idx on " + tableName + "(key2)")
            c.execute("CREATE INDEX " + tableName + "_dt_idx on " + tableName + "(dt)")
            c.execute("CREATE INDEX " + tableName + "_value_idx on " + tableName + "(value)")
            c.execute(
                "CREATE TABLE " + tableName + "_str (dataid bigint, key1 varchar(255), key2 bigint, dt timestamp, value varchar(1024))")
            c.execute("CREATE INDEX " + tableName + "_str_dataid_idx on " + tableName + "_str(dataid)")
            c.execute("CREATE INDEX " + tableName + "_str_key1_idx on " + tableName + "_str(key1)")
            c.execute("CREATE INDEX " + tableName + "_str_key2_idx on " + tableName + "_str(key2)")
            c.execute("CREATE INDEX " + tableName + "_str_dt_idx on " + tableName + "_str(dt)")
            c.execute("CREATE INDEX " + tableName + "_str_value_idx on " + tableName + "_str(value)")
            c.close()
            conn.commit()
            conn.close()

        if tableName == "data_min":
            self.recreateConns()

    def processData(self):
        self.setDts()
        if getCurrentMinute(self.dt) != self.lastSavedMinute:
            self.processMinuteData()
            if getCurrentMinute(self.dt) % 5 == 0:
                self.copyData("data_min", "data_5min", True, self.curDt)

            if getCurrentMinute(self.dt) % 15 == 0:
                self.copyData("data_5min", "data_15min", True, self.curDt)

            if getCurrentMinute(self.dt) == 0:
                self.copyData("data_15min", "data_hour", True, self.curDt)

            # if getCurrentMinute(self.dt) == 0 and getCurrentHour(self.dt) % 3 == 0:
            #    self.copyData("data_hour", "data_3hour", False, self.curDt)

            if getCurrentHour(self.dt) == 0 and getCurrentMinute(self.dt) == 0:
                self.copyData("data_hour", "data_day", True, self.lastDt)

            if getCurrentWeekDay(self.dt) == 1 and getCurrentHour(self.dt) == 0 and getCurrentMinute(self.dt) == 0:
                self.copyData("data_day", "data_week", True, self.lastDt)

            if getCurrentDay(self.dt) == 1 and getCurrentHour(self.dt) == 0 and getCurrentMinute(self.dt) == 0:
                self.copyData("data_week", "data_month", True, self.lastDt)

            self.lastSavedMinute = getCurrentMinute(self.dt)



    def getMinUploadValue(self, oidId):
        self.mibCur.execute("SELECT min_upload_value FROM mib_object WHERE id=?", (oidId,))
        tmpRow = self.mibCur.fetchone()
        if tmpRow == None:
            return None
        else:
            return tmpRow[0]

    def getMibDataIds(self):
        mibDataIds=[]
        for row in self.mibCur.execute("SELECT id FROM mib_object"):
            mibDataIds.append(row[0])
        return mibDataIds

    def copyData(self, sourceTableName, destTableName, removeSourceTable, curDt):
        self.createDbAndTables(destTableName)

        sourceConn = sqlite3.connect(fileDir + '/' + sourceTableName + '.db')
        sourceCur = sourceConn.cursor()
        destConn = sqlite3.connect(fileDir + '/' + destTableName + '.db')
        destCur = destConn.cursor()
        dataIds = []
        for row in sourceCur.execute("SELECT DISTINCT dataid FROM " + sourceTableName):
            dataIds.append(row[0])

        strDataIds = []
        for row in sourceCur.execute("SELECT DISTINCT dataid FROM " + sourceTableName + "_str"):
            strDataIds.append(row[0])

        dataCount = 0
        for row in sourceCur.execute("SELECT COUNT(DISTINCT dt) FROM " + sourceTableName + ""):
            dataCount = float(row[0])

        mibDataIds = self.getMibDataIds()
        uid = pwd.getpwnam("mmagent").pw_uid
        if not os.path.isdir(fileDir + "/uploads"):
            os.makedirs(fileDir + "/uploads")
        if not os.path.isdir(fileDir + "/uploads/" + destTableName):
            os.makedirs(fileDir + "/uploads/" + destTableName)
            chown(fileDir + "/uploads/" + destTableName, uid, 0)

        gzobj = gzip.GzipFile(filename=fileDir + '/uploads/' + destTableName + '/' + curDt + ".gz.notready", mode='w')
        firstRow = True
        for dataId in dataIds:
            if dataId in mibDataIds:
                rowCounter = 0
                # TODO other possibilities than average
                for row in sourceCur.execute(
                        "SELECT dataid,key1,key2,cast(round(sum(value)/?) as int) as avgvalue FROM " + sourceTableName + " WHERE dataid=? GROUP BY dataid,key1,key2 HAVING avgvalue>=? ORDER BY avgvalue "+self.getOrder(dataId)+" LIMIT ?",
                        (dataCount, dataId, self.getMinUploadValue(dataId), copyDataLimit)):
                    if firstRow:
                        x="###DT#" + curDt + "\n"
                        gzobj.write(x.encode())
                        firstRow = False
                    destCur.execute("INSERT INTO " + destTableName + "(dataid, key1, key2, dt, value) VALUES (?,?,?,?,?)",
                                    (row[0], row[1], row[2], curDt, row[3],))
                    if rowCounter < self.getUploadDataLimit(dataId):
                        x=getStr(row[0]) + "#" + getStr(row[1]) + "#" + getStr(row[2]) + "#" + getStr(row[3]) + "\n"
                        gzobj.write(x.encode())
                        rowCounter = rowCounter + 1

        firstStrRow = True
        for strDataId in strDataIds:
            if strDataId in mibDataIds:
                rowCounter = 0
                for row in sourceCur.execute(
                        "select dataid,key1,key2,value from " + sourceTableName + "_str where dt=(select max(dt) from " + sourceTableName + "_str where dataid=?) and dataid=? group by dataid,key1,key2 LIMIT ?",
                        (strDataId, strDataId, copyDataLimit)):
                    if firstStrRow:
                        x="###STR\n"
                        gzobj.write(x.encode())
                        firstStrRow = False
                    destCur.execute(
                        "INSERT INTO " + destTableName + "_str(dataid, key1, key2, dt, value) VALUES (?,?,?,?,?)",
                        (row[0], row[1], row[2], curDt, row[3],))
                    if rowCounter < self.getUploadDataLimit(dataId):
                        x=getStr(row[0]) + "#" + getStr(row[1]) + "#" + getStr(row[2]) + "#" + getStr(row[3]) + "\n"
                        gzobj.write(x.encode())
                        rowCounter = rowCounter + 1

        sourceCur.close()
        sourceConn.close()
        if removeSourceTable:
            os.remove(fileDir + '/' + sourceTableName + '.db')
            self.createDbAndTables(sourceTableName)
        destCur.close()
        destConn.commit()
        destConn.close()
        gzobj.flush()
        gzobj.close()
        os.rename(fileDir + '/uploads/' + destTableName + '/' + self.curDt + ".gz.notready", fileDir + '/uploads/' + destTableName + '/' + self.curDt + ".gz")
        chown(fileDir + '/uploads/' + destTableName + '/' + curDt + ".gz", uid, 0)

    def processMinuteData(self):
        destTableName = "data_min"
        uid = pwd.getpwnam("mmagent").pw_uid
        if not os.path.isdir(fileDir + "/uploads"):
            os.makedirs(fileDir + "/uploads")
        if not os.path.isdir(fileDir + "/uploads/" + destTableName):
            os.makedirs(fileDir + "/uploads/" + destTableName)
            chown(fileDir + "/uploads/" + destTableName, uid, 0)

        gzobj = gzip.GzipFile(filename=fileDir + '/uploads/' + destTableName + '/' + self.curDt + ".gz.notready", mode='w')
        self.loadPluginData(self.curDt)
        dataIds = []
        for row in self.destCur.execute("SELECT DISTINCT dataid FROM data_min WHERE dt=?", (self.curDt,)):
            dataIds.append(row[0])
        strDataIds = []
        for row in self.destCur.execute("SELECT DISTINCT dataid FROM data_min_str WHERE dt=?", (self.curDt,)):
            strDataIds.append(row[0])

        mibDataIds = self.getMibDataIds()

        firstRow = True
        for dataId in dataIds:
            if dataId in mibDataIds:
                for row in self.destCur.execute(
                        "SELECT dt,dataid,key1,key2,value FROM data_min WHERE dt=? AND dataid=? AND value >=? ORDER BY dt, value "+self.getOrder(dataId)+" LIMIT ?",
                        (self.curDt, dataId, self.getMinUploadValue(dataId), self.getUploadDataLimit(dataId),)):
                    if firstRow:
                        x="###DT#" + self.curDt + "\n"
                        gzobj.write(x.encode())
                        firstRow = False
                    x=getStr(row[1]) + "#" + getStr(row[2]) + "#" + getStr(row[3]) + "#" + getStr(row[4]) + "\n"
                    gzobj.write(x.encode())
        firstStrRow = True
        for strDataId in strDataIds:
            if strDataId in mibDataIds:
                for row in self.destCur.execute(
                        "SELECT dt,dataid,key1,key2,value FROM data_min_str WHERE dt=? AND dataid=? ORDER BY dt",
                        (self.curDt, strDataId,)):
                    if firstStrRow:
                        x="###STR\n"
                        gzobj.write(x.encode())
                        firstStrRow = False
                    x=getStr(row[1]) + "#" + getStr(row[2]) + "#" + getStr(row[3]) + "#" + getStr(row[4]) + "\n"
                    gzobj.write(x.encode())

        self.destConn.commit()
        gzobj.flush()
        gzobj.close()
        os.rename(fileDir + '/uploads/' + destTableName + '/' + self.curDt + ".gz.notready", fileDir + '/uploads/' + destTableName + '/' + self.curDt + ".gz")
        chown(fileDir + '/uploads/' + destTableName + '/' + self.curDt + ".gz", uid, 0)

    def recreateConns(self):
        try:
            self.destCur.close()
            self.destConn.close()
        except:
            a=1
        self.destConn = sqlite3.connect(fileDir+'/data_min.db')
        self.destCur = self.destConn.cursor()

    def setDts(self):
        self.curDt = str(datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:00"))
        self.nextDt = str((datetime.datetime.utcnow() + datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:00"))
        self.lastDt = str((datetime.datetime.utcnow() - datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:00"))
        self.dt = datetime.datetime.now()
        self.utcdt = datetime.datetime.now()

    def loadPluginData(self, dt):
        a=1
        # TODO implement

def getCurrentMinute(dt):
    return int(dt.strftime('%M'))

def getCurrentHour(dt):
    return int(dt.strftime('%H'))

def getCurrentDay(dt):
    return int(dt.strftime('%d'))

def getCurrentMonth(dt):
    return int(dt.strftime('%m'))

def getCurrentYear(dt):
    return int(dt.strftime('%Y'))

def getCurrentWeekDay(dt):
    return int(dt.strftime('%W'))

def getStr(value):
    if value == None:
        return "";
    else:
        return str(value)
