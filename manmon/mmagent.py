import re, os, time, datetime
import requests
import sys
import logging
import subprocess
import os, signal
import os.path
from manmon.get_long import getLong
from manmon.classes import NetInterface, DiskStats
from manmon.database import ManmonAgentDatabase

d='/proc'
loadEveryCpuStats=False
loadTopLists = True

getTimeInMilliseconds = lambda: int(round(time.time() * 1000))

db=ManmonAgentDatabase()

class ManmonAgent():
    def __init__(self):
        self.loadUsernames()
        self.firstLoadDone = False
        self.topListCount = 30
        self.topListLowestValue = 1
        self.tempDiskDevTicks = {}
        self.tempNetInterfaces = {}
        self.seconds = 60
        self.clockTicks = 1
        self.topListLowestValue = 1

    def load(self):
        if not self.firstLoadDone:
            self.loadCpuStats()
            self.loadProcInfo()

            self.loadDiskIoStats()
            self.loadNetDevStats()
            self.session = requests.session()
            self.firstLoadDone = True

    def calc(self):
        self.loadUsernames()

        if loadTopLists:
            self.calcProcCpuUsage()
            self.calcProcIo()
            self.calcOpenFiles()
            self.calcUserStats()

        self.calcCpuStats()
        self.calcDiskIoStats()
        self.calcDiskStats()
        self.calcNetDevStats()
        self.calcMemoryInfo()
        # TODO remove?
        self.loadProcInfo()

    def loadCpuStats(self):
        newCpuData = {}
        try:
            statFile = open(d + '/stat')

            for row in statFile:
                if re.match('^cpu', row):
                    rowPieces = re.split('\s+', row)
                    cpu = rowPieces[0]
                    newCpuData[cpu] = row.strip()
            statFile.close()
        except IOError:
            logging.debug("Error loading " + d + "/stat")
        self.cpuData = newCpuData

    def calcCpuStats(self):
        newCpuData = {}
        try:
            statFile = open(d + '/stat')
            cpuUsage = {}
            cpuIoWaitUsage = {}
            for row in statFile:
                if re.match('^cpu', row):
                    rowPieces = re.split('\s+', row)
                    cpu = rowPieces[0]
                    newCpuData[cpu] = row.strip()
                    userNew = float(rowPieces[1])
                    niceNew = float(rowPieces[2])
                    systemNew = float(rowPieces[3])
                    idleNew = float(rowPieces[4])
                    iowaitNew = float(rowPieces[5])
                    irqNew = float(rowPieces[6])
                    softirqNew = float(rowPieces[7])

                    if cpu in self.cpuData:
                        rowPiecesOld = re.split('\s+', self.cpuData[cpu])
                        userOld = float(rowPiecesOld[1])
                        niceOld = float(rowPiecesOld[2])
                        systemOld = float(rowPiecesOld[3])
                        idleOld = float(rowPiecesOld[4])
                        iowaitOld = float(rowPiecesOld[5])
                        irqOld = float(rowPiecesOld[6])
                        softirqOld = float(rowPiecesOld[7])

                        cpuUsage[cpu] = getLong(round(
                            ((userNew - userOld) + (niceNew - niceOld) + (systemNew - systemOld)) * float(100) / (
                                        (userNew - userOld) + (niceNew - niceOld) + (systemNew - systemOld) + (
                                            idleNew - idleOld)) * float(100)));
                        cpuIoWaitUsage[cpu] = getLong(round((iowaitNew - iowaitOld) * 100 / (
                                    (userNew - userOld) + (niceNew - niceOld) + (systemNew - systemOld) + (
                                        idleNew - idleOld) + (iowaitNew - iowaitOld)) * float(100)));
            statFile.close()
            self.saveCpuDataInfo(cpuUsage, cpuIoWaitUsage)
        except IOError:
            logging.debug("Error loading " + d + "/stat")

        self.cpuData = newCpuData


    def saveCpuDataInfo(self, cpuUsage, cpuIoWaitUsage):
        data = sorted(cpuUsage.items(), key=lambda x: x[1], reverse=True)
        count = 0
        if loadEveryCpuStats:
            for cpu, value in data:
                if cpu != "cpu":
                    if count < self.topListCount and value > self.topListLowestValue:
                        db.insertDataToDb('mmCpuLoad', value)
                        count += 1
        db.insertDataToDb('mmTotalCpuLoad', cpuUsage['cpu'])
        db.insertDataToDb('mmTotalCpuIOWait', cpuIoWaitUsage['cpu'])

    def loadProcInfo(self):
        self.pids = []
        self.tempProcCpuTime = {}
        # self.tempProcRchar = {}
        # self.tempProcWchar = {}
        self.cpuData = {}
        self.procIdToProcName = {}
        self.tempReadBytes = {}
        self.tempWriteBytes = {}

        for pid in [o for o in os.listdir(d) if os.path.isdir(os.path.join(d, o)) and re.match('^\d+$', o)]:
            self.pids.append(pid)
            try:
                statFile = open(d + '/' + pid + '/stat', 'r')
                for row in statFile:
                    statStrPieces = re.split('\s+', row.strip())
                    statUtime = int(statStrPieces[13])
                    statStime = int(statStrPieces[14])
                    # cUtime = int(statStrPieces[15])
                    # cStime = int(statStrPieces[16])
                    totalTime = statUtime + statStime
                    self.tempProcCpuTime[pid] = int(totalTime)
                statFile.close()
            except IOError:
                logging.debug("File not found " + d + '/' + pid + '/stat')

            try:
                ioFile = open(d + '/' + pid + '/io', 'r')
                for row in ioFile:
                    #                    if re.match('^rchar:', row):
                    #                        self.tempProcRchar[pid] = long(re.split('\s+', row)[1])
                    #                    if re.match('^wchar:', row):
                    #                        self.tempProcWchar[pid] = long(re.split('\s+', row)[1])
                    if re.match('^read_bytes:', row):
                        self.tempReadBytes[pid] = getLong(re.split('\s+', row)[1])
                    elif re.match('^write_bytes:', row):
                        self.tempWriteBytes[pid] = getLong(re.split('\s+', row)[1])

                ioFile.close()
            except IOError:
                logging.debug("File not found " + d + '/' + pid + '/io')

            try:
                rootStatFile = open(d + '/stat', 'r')
                for row in rootStatFile:
                    if re.match('^cpu', row):
                        cpu = re.split('\s+', row.strip())[0]
                        self.cpuData[cpu] = row.strip()
                rootStatFile.close()
            except IOError:
                logging.debug("File not found " + d + '/stat')

            try:
                statusFile = open(d + '/' + pid + '/status', 'r')
                for row in statusFile:
                    if re.match('^Name:', row):
                        self.procIdToProcName[pid] = re.split('\s', row.strip())[1]
                statusFile.close()
            except IOError:
                logging.debug("File not found " + d + '/' + pid + '/status')

    def loadNetDevStats(self):
        try:
            self.netDevStatsLoadTime = getTimeInMilliseconds()

            netFile = open(d + '/net/dev', 'r')
            for row in netFile:
                if re.match('.*:.*', row):
                    rowPieces = re.split(': *', row.strip())
                    dev = rowPieces[0]
                    data = re.split('\s+', rowPieces[1])
                    receivedBytes = getLong(data[0])
                    receivedPackets = getLong(data[1])
                    sentBytes = getLong(data[8])
                    sentPackets = getLong(data[9])
                    self.tempNetInterfaces[dev] = NetInterface(dev, receivedBytes, receivedPackets, sentBytes,
                                                               sentPackets)
            netFile.close()
        except IOError:
            logging.debug("File not found " + d + '/net/dev')

    def loadDiskIoStats(self):
        try:
            self.diskIoStatsLoadTime = getTimeInMilliseconds()
            diskFile = open(d + '/diskstats', 'r')
            for row in diskFile:
                linePieces = re.split('\s+', row.strip())
                devName = linePieces[2]
                if not re.match('^ram\d+', devName) and not re.match('^loop\d+', devName) and not re.match('^sr\d+',
                                                                                                           devName):
                    self.tempDiskDevTicks[devName] = linePieces[12];
            diskFile.close()
        except IOError:
            logging.debug("File not found " + d + '/diskstats')

    def calcProcCpuUsage(self):
        self.procCpuUsage = {}
        for pid in self.pids:
            if os.path.isdir(d + '/' + pid):
                try:
                    statFile = open(d + '/' + pid + '/stat')
                    for row in statFile:
                        statStrPieces = re.split('\s+', row.strip())
                        statUtime = int(statStrPieces[13])
                        statStime = int(statStrPieces[14])
                        cUtime = int(statStrPieces[15])
                        cStime = int(statStrPieces[16])
                        totalTime = statUtime + statStime
                        cpuUsage = (float(totalTime - self.tempProcCpuTime[pid]) * 100.00 / float(
                            self.seconds))  # / self.clockTicks * 100;
                        self.procCpuUsage[pid] = int(cpuUsage)
                    statFile.close()
                except IOError:
                    logging.debug("File not found " + d + '/' + pid + '/stat')

        self.saveProcCpuUsage(self.procCpuUsage)

    def saveProcCpuUsage(self, procCpuUsage):
        data = sorted(procCpuUsage.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for procId, value in data:
            if count < self.topListCount and value > self.topListLowestValue:
                db.insertDataToDbWithKeys('mmProcTopCpuLoad', self.procIdToProcName[procId], procId, value)
                count += 1

    def calcProcIo(self):
#        procChar = {}
        procBytes  = {}
        for pid in self.pids:
            if os.path.isdir(d+'/'+pid):
                try:
                    ioFile = open(d+'/'+pid+'/io')
                    for row in ioFile:
                        if re.match('^read_bytes:', row):
                            rbytes = getLong(round((getLong(re.split('\s+', row.strip())[1])  - getLong(self.tempReadBytes[pid])) / self.seconds))
                            if pid in procBytes:
                                procBytes[pid] += rbytes
                            else:
                                procBytes[pid] = rbytes
                        elif re.match('^write_bytes:', row):
                            wbytes = getLong(round((getLong(re.split('\s+', row.strip())[1])  - getLong(self.tempWriteBytes[pid])) / self.seconds))
                            if pid in procBytes:
                                procBytes[pid] += wbytes
                            else:
                                procBytes[pid] = wbytes
#                        if re.match('^rchar:', row.strip()):
#                            rchar = (long(re.split('\s+', row.strip())[1])  - long(self.tempProcRchar[pid])) / self.seconds
#                            if pid in procChar:
#                                procChar[pid] = procChar[pid] + rchar
#                            else:
#                                procChar[pid] = rchar
#                        if re.match('^wchar:', row.strip()):
#                            wchar = (long(re.split('\s+', row.strip())[1]) - long(self.tempProcWchar[pid])) / self.seconds
#                            if pid in procChar:
#                                procChar[pid] = procChar[pid] + wchar
#                            else:
#                                procChar[pid] = wchar
                    ioFile.close()
                except IOError:
                    logging.debug("File not found "+d+'/'+pid+'/io')
#        self.procIoUsage = procChar
        self.procIoUsage = procBytes
#        self.printProcIoUsage(procChar)
        self.saveProcIoUsage(procBytes)

    def saveProcIoUsage(self, procBytes):
        data = sorted(procBytes.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for procId, value in data:
            if count < self.topListCount and value > self.topListLowestValue:
                db.insertDataToDbWithKeys('mmProcTopIOUsage', self.procIdToProcName[procId], procId, value)
                count += 1

    def loadUsernames(self):
        self.uidsToUserNames = {}
        pwdFile = open("/etc/passwd", "r")
        for row in pwdFile:
            rowPieces = re.split(":", row)
            self.uidsToUserNames[getLong(rowPieces[2])] = rowPieces[0]
        pwdFile.close()

    def calcOpenFiles(self):
        totalOpenFiles = 0
        openFilesByPid = {}
        openFileSoftLimitByPid = {}
        openFileHardLimitByPid = {}

        totalOpenProcessses = 0
        runningProcessesByUid = {}
        softLimitOpenProcsByUid = {}
        hardLimitOpenProcsByUid = {}

        for pid in self.pids:
            totalOpenProcessses += 1
            if os.path.isdir(d + '/' + pid):
                openFilesCount = 0
                for f in os.listdir(d + '/' + pid + '/fd'):
                    if os.path.exists(d + '/' + pid + '/fd/' + f):
                        openFilesCount += 1
                openFilesByPid[pid] = openFilesCount
                totalOpenFiles = totalOpenFiles + openFilesCount

                try:
                    uid = None
                    statusFile = open(d + '/' + pid + '/status', 'r')
                    for row in statusFile:
                        if re.match("^Uid:", row.strip()):
                            uid = getLong(re.split('\s+', row.strip())[1])
                            if uid in runningProcessesByUid:
                                runningProcessesByUid[uid] = runningProcessesByUid[uid] + 1
                            else:
                                runningProcessesByUid[uid] = 1
                    statusFile.close()

                    limitsFile = open(d + '/' + pid + '/limits', 'r')
                    for row in limitsFile:
                        if re.match('^Max open files', row.strip()):
                            rowPieces = re.split('\s+', row.strip())
                            openFileSoftLimitByPid[pid] = getLong(rowPieces[3])
                            openFileHardLimitByPid[pid] = getLong(rowPieces[4])
                        if re.match('^Max processes', row.strip()):
                            if uid != None:
                                rowPieces = re.split('\s+', row.strip())
                                if rowPieces[2] != "unlimited" and rowPieces[3] != "unlimited":
                                    softProcLimit = getLong(rowPieces[2])
                                    hardProcLimit = getLong(rowPieces[3])
                                    if uid in softLimitOpenProcsByUid:
                                        if softLimitOpenProcsByUid[uid] < softProcLimit:
                                            softLimitOpenProcsByUid[uid] = softProcLimit
                                    else:
                                        softLimitOpenProcsByUid[uid] = softProcLimit

                                    if uid in hardLimitOpenProcsByUid:
                                        if hardLimitOpenProcsByUid[uid] < hardProcLimit:
                                            hardLimitOpenProcsByUid[uid] = hardProcLimit
                                    else:
                                        hardLimitOpenProcsByUid[uid] = hardProcLimit
                    limitsFile.close()
                except IOError:
                    logging.debug("File not found " + d + '/' + pid + '/limits')

        db.insertDataToDb('mmOpenFiles',totalOpenFiles)
        db.insertDataToDb('mmOpenProcesses', totalOpenProcessses)
        try:
            fileMaxFile = open(d + '/sys/fs/file-max')
            fileMax = getLong(fileMaxFile.read())
            fileMaxFile.close()
            pidMaxFile = open(d + '/sys/kernel/pid_max')
            pidMax = getLong(pidMaxFile.read())
            pidMaxFile.close()

            db.insertDataToDb('mmOpenFilesPercentInUse',(totalOpenFiles*100*100 / fileMax))
            db.insertDataToDb('mmOpenProcessesPercentInUse', (totalOpenProcessses*100*100 / pidMax))
        except IOError:
            logging.error("Error reading " + d + "/sys/fs/file-max or " + d + "/sys/kernel/pid_max")

        softLimitUsedByPid = {}
        hardLimitUsedByPid = {}
        for pid in openFilesByPid:
            softLimitUsedByPid[pid] = (openFilesByPid[pid] * 100 * 100) / openFileSoftLimitByPid[pid]
            hardLimitUsedByPid[pid] = (openFilesByPid[pid] * 100 * 100) / openFileHardLimitByPid[pid]

        procSoftLimitUsedByUid = {}
        procHardLimitUsedByUid = {}
        for uid in runningProcessesByUid:
            username=self.uidToUsername(uid)
            userShell=subprocess.Popen("getent passwd "+username+" | cut -d: -f7", shell=True, stdout=subprocess.PIPE).stdout.read()
            if userShell == "/bin/bash" or userShell == "/bin/sh":
                softLimit = int(subprocess.Popen("su - "+username+" -c 'ulimit -Sn'", shell=True, stdout=subprocess.PIPE).stdout.read())
                hardLimit=int(subprocess.Popen("su - "+username+" -c 'ulimit -Hn'", shell=True, stdout=subprocess.PIPE).stdout.read())
                procSoftLimitUsedByUid[uid] = (runningProcessesByUid[uid] * 100 * 100) / softLimit
                procHardLimitUsedByUid[uid] = (runningProcessesByUid[uid] * 100 * 100) / hardLimit
            else:
                procSoftLimitUsedByUid[uid] = (runningProcessesByUid[uid] * 100 * 100) / softLimitOpenProcsByUid[uid]
                procHardLimitUsedByUid[uid] = (runningProcessesByUid[uid] * 100 * 100) / hardLimitOpenProcsByUid[uid]

        self.saveSoftOpenFilesInfo(softLimitUsedByPid)
        self.saveHardOpenFilesInfo(hardLimitUsedByPid)

        self.saveSoftRunningProcsInfo(procSoftLimitUsedByUid)
        self.saveHardRunningProcsInfo(procHardLimitUsedByUid)

    def saveSoftRunningProcsInfo(self, procSoftLimitUsedByUid):
        data = sorted(procSoftLimitUsedByUid.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for userId, value in data:
            if count < self.topListCount and value > self.topListLowestValue:
                db.insertDataToDbWithKeys('mmUsersOpenProcessesSoftLimitUsedPercent', self.uidToUsername(userId), userId, value)
                count += 1

    def saveHardRunningProcsInfo(self, procHardLimitUsedByUid):
        data = sorted(procHardLimitUsedByUid.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for userId, value in data:
            if count < self.topListCount and value > self.topListLowestValue:
                db.insertDataToDbWithKeys('mmUsersOpenProcessesHardLimitUsedPercent', self.uidToUsername(userId), userId, value)
                count += 1
                
    def saveSoftOpenFilesInfo(self, softLimitUsedByPid):
        data = sorted(softLimitUsedByPid.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for procId, value in data:
            if count < self.topListCount and value > self.topListLowestValue:
                db.insertDataToDbWithKeys('mmProcOpenFilesSoftPercentInUse', self.procIdToProcName[procId], procId, value)
                count += 1

    def saveHardOpenFilesInfo(self, hardLimitUsedByPid):
        data = sorted(hardLimitUsedByPid.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for procId, value in data:
            if count < self.topListCount and value > self.topListLowestValue:
                db.insertDataToDbWithKeys('mmProcOpenFilesHardPercentInUse', self.procIdToProcName[procId], procId, value)
                count += 1

    def uidToUsername(self, uid):
        if uid in self.uidsToUserNames:
            return self.uidsToUserNames[uid]
        else:
            return str(uid)

    def calcDiskIoStats(self):
        self.diskIo = {}
        try:
            diskFile = open(d+'/diskstats', 'r')
            currentTime = getTimeInMilliseconds()
            newTempDiskDevTicks = {}
            for row in diskFile:
                linePieces = re.split('\s+', row.strip())
                devName = linePieces[2]
                if not re.match('^ram\d+', devName) and not re.match('^loop\d+', devName) and not re.match('^sr\d+', devName):
                    if devName in self.tempDiskDevTicks:
                        diskTicks = linePieces[12];
                        newTempDiskDevTicks[devName] = diskTicks
                        load = int(round( ( getLong(diskTicks) - getLong(self.tempDiskDevTicks[devName]) ) * 100 * 100 / ( float(currentTime - self.diskIoStatsLoadTime )) ))
                        if load > 10000:
                            self.diskIo[devName] = 10000;
                        else:
                            self.diskIo[devName] = load;
            diskFile.close()
            self.diskIoStatsLoadTime = getTimeInMilliseconds()
            self.tempDiskDevTicks = newTempDiskDevTicks
        except IOError:
            logging.error("File not found "+d+'/diskstats')

    def calcNetDevStats(self):
        netIfData = {}
        try:
            currentTime = getTimeInMilliseconds()
            netFile = open(d + '/net/dev', 'r')
            for row in netFile:
                if re.match('.*:.*', row):
                    rowPieces = re.split(': *', row.strip())
                    dev = rowPieces[0]
                    if dev in self.tempNetInterfaces:
                        data = re.split('\s+', rowPieces[1])
                        receivedBytes = getLong(data[0])
                        receivedPackets = getLong(data[1])
                        sentBytes = getLong(data[8])
                        sentPackets = getLong(data[9])
                        timeDiff = float(float(currentTime - self.netDevStatsLoadTime) / 1000)
                        tempNetIf = self.tempNetInterfaces[dev]
                        netIfData[dev] = NetInterface(dev, receivedBytes, receivedPackets, sentBytes, sentPackets)
                        netIfData[dev].receivedBytesPerSec = getLong(round((receivedBytes - tempNetIf.receivedBytes) / timeDiff))
                        netIfData[dev].receivedPacketsPerSec = getLong(round((receivedPackets - tempNetIf.receivedPackets) / timeDiff))
                        netIfData[dev].sentBytesPerSec = getLong(round((sentBytes - tempNetIf.sentBytes) / timeDiff))
                        netIfData[dev].sentPacketsPerSec = getLong(round((sentPackets - tempNetIf.sentPackets) / timeDiff))

            netFile.close()
            self.netDevStatsLoadTime = getTimeInMilliseconds()
            self.tempNetInterfaces = netIfData
            self.saveNetDevStats(netIfData)
        except IOError:
            logging.error("File not found " + d + '/net/dev')


    def saveNetDevStats(self, netIfData):
        data = sorted(netIfData.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for netDevName, netDev in data:
            if count < self.topListCount:
                db.insertDataToDbWithKeys('mmNetRecvBytesPerSecond', netDevName, None, netDev.receivedBytesPerSec)
                db.insertDataToDbWithKeys('mmNetRecvPacketsPerSecond', netDevName, None, netDev.receivedPacketsPerSec)
                db.insertDataToDbWithKeys('mmNetSentBytesPerSecond', netDevName, None, netDev.sentBytesPerSec)
                db.insertDataToDbWithKeys('mmNetSentPacketsPerSecond', netDevName, None, netDev.sentPacketsPerSec)
                count += 1

    def calcDiskStats(self):
        diskStats = {}
        mountsFile = open(d + "/mounts", "r")
        for row in mountsFile:
            if re.match("^/dev", row) and not row.startswith("/dev/loop") and not row.startswith("/dev/fuse"):
                rowPieces = re.split("\s+", row)
                devName = ""
                if (re.match("^/dev/mapper", row)):
                    devName = re.sub("^/dev/", "", os.path.realpath(rowPieces[0]))
                else:
                    devName = re.sub("^/dev/", "", rowPieces[0])
                mountPoint = rowPieces[1]
                # print devName, mountPoint
                s = os.statvfs(mountPoint)
                size = getLong(s.f_bsize) * getLong(s.f_blocks)
                used = size - (getLong(s.f_bsize) * getLong(s.f_bavail))
                free = getLong(s.f_bsize) * getLong(s.f_bavail) / 1024
                isize = getLong(s.f_files)
                iused = isize - getLong(s.f_favail)
                ifree = getLong(s.f_favail)
                iousage = self.diskIo[devName]
                if not devName in diskStats:
                    diskStats[devName] = DiskStats(mountPoint, size, used, free, isize, iused, ifree, iousage)
        mountsFile.close()
        self.saveDiskStats(diskStats)

    def saveDiskStats(self, diskStats):
        data = sorted(diskStats.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for devName, stats in data:
            # if count < self.topListCount:
            if True:
                if stats.mountpoint != "/boot" and stats.mountpoint != "/boot/efi":
                #db.insertDataToDbWithKeys('mmDiskDev', stats.mountpoint, None, devName)
                    db.insertDataToDbWithKeys('mmDiskUsedPercent', stats.mountpoint, None, stats.percentUsed)
                    db.insertDataToDbWithKeys('mmDiskInodeUsedPercent', stats.mountpoint, None, stats.ipercentUsed)
                    db.insertDataToDbWithKeys('mmDiskIOPercent', stats.mountpoint, None, stats.iousage)
                    db.insertDataToDbWithKeys('mmDiskFreeValue', stats.mountpoint, None, stats.size)
                    db.insertDataToDbWithKeys('mmDiskFreeInodesValue', stats.mountpoint, None, stats.isize)
                    count += 1
                else:
                    db.insertDataToDbWithKeys('mmBootUsedPercent', stats.mountpoint, None, stats.percentUsed)
                    db.insertDataToDbWithKeys('mmBootInodeUsedPercent', stats.mountpoint, None, stats.ipercentUsed)
                    db.insertDataToDbWithKeys('mmBootIOPercent', stats.mountpoint, None, stats.iousage)
                    db.insertDataToDbWithKeys('mmBootFreeValue', stats.mountpoint, None, stats.size)
                    db.insertDataToDbWithKeys('mmBootFreeInodesValue', stats.mountpoint, None, stats.isize)
                    count += 1


    def calcUserStats(self):
        usersMemoryUsage = {}
        usersIoUsage = {}
        usersCpuUsage = {}
        processesByUid = {}
        pidsToProcNames = {}
        procsMemUsage = {}

        for pid in [o for o in os.listdir(d) if os.path.isdir(os.path.join(d, o)) and re.match('^\d+$', o)]:
            if pid in self.procCpuUsage:
                try:
                    statusFile = open(d + "/" + pid + "/status", "r")
                    uid = getLong(-1)
                    for row in statusFile:
                        if re.match("^Uid:", row):
                            uid = getLong(re.split("\s+", row)[1])
                            if uid in processesByUid:
                                processesByUid[uid] = processesByUid[uid] + 1
                            else:
                                processesByUid[uid] = 1
                            if uid in usersCpuUsage:
                                usersCpuUsage[uid] = usersCpuUsage[uid] + self.procCpuUsage[pid]
                            else:
                                usersCpuUsage[uid] = self.procCpuUsage[pid]
                            if uid in usersIoUsage:
                                usersIoUsage[uid] = usersIoUsage[uid] + self.procIoUsage[pid]
                            else:
                                usersIoUsage[uid] = self.procIoUsage[pid]
                        elif re.match("^Name:", row):
                            pidsToProcNames[pid] = re.split("\s+", row)[1]
                        elif re.match("^VmRSS:", row):
                            procMem = getLong(re.split("\s+", row)[1])
                            procsMemUsage[pid] = procMem
                            if uid in usersMemoryUsage:
                                usersMemoryUsage[uid] = usersMemoryUsage[uid] + getLong(procMem)
                            else:
                                usersMemoryUsage[uid] = getLong(procMem)
                        elif re.match("^Threads:", row):
                            threadCount = getLong(re.split("\s+", row)[1])
                            # TODO check
                            if uid in processesByUid:
                                processesByUid[uid] = processesByUid[uid] + threadCount
                            else:
                                processesByUid[uid] = threadCount

                    statusFile.close()
                except IOError:
                    logging.debug("File not found " + d + '/status')
        else:
            # TODO
            a = 1

        self.__saveUsersMemoryUsage(usersMemoryUsage)
        self.__saveProcsMemoryUsage(procsMemUsage, pidsToProcNames)
        self.__saveUsersProcesses(processesByUid)
        self.__saveUsersCpuUsage(usersCpuUsage)
        self.__saveUsersIoUsage(usersIoUsage)

    def __saveUsersMemoryUsage(self, usersMemoryUsage):
        data = sorted(usersMemoryUsage.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for uid, value in data:
            if count < self.topListCount and value > self.topListLowestValue:
                db.insertDataToDbWithKeys('mmUsersTopMemUsage', self.uidToUsername(uid), uid, value)
                count += 1

    def __saveProcsMemoryUsage(self, procsMemUsage, pidsToProcNames):
        data = sorted(procsMemUsage.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for pid, value in data:
            if count < self.topListCount and value > self.topListLowestValue:
                db.insertDataToDbWithKeys('mmProcTopMemUsage', pidsToProcNames[pid], pid, value)
                count += 1

    def __saveUsersProcesses(self, processesByUid):
        data = sorted(processesByUid.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for uid, value in data:
            if count < self.topListCount and value > self.topListLowestValue:  # mmUsersOpenProcessesSoftLimitUsedPercent mmUsersOpenProcessesHardLimitUsedPercent
                db.insertDataToDbWithKeys('mmUsersOpenProcessesCount', self.uidToUsername(uid), uid, value)
                count += 1

    def __saveUsersCpuUsage(self, usersCpuUsage):
        data = sorted(usersCpuUsage.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for uid, value in data:
            if count < self.topListCount and value > self.topListLowestValue:
                db.insertDataToDbWithKeys('mmUsersTopCpuLoad', self.uidToUsername(uid), uid, value)
                count += 1

    def __saveUsersIoUsage(self, usersIoUsage):
        data = sorted(usersIoUsage.items(), key=lambda x: x[1], reverse=True)
        count = 0
        for uid, value in data:
            if count < self.topListCount and value > self.topListLowestValue:
                db.insertDataToDbWithKeys('mmUsersTopIOUsage', self.uidToUsername(uid), uid, value)
                count += 1

    def calcMemoryInfo(self):
        memData = {}
        memData['swapTotalSize'] = 0
        memData['swapTotalUsed'] = 0
        swapFile = open(d + '/swaps')
        for row in swapFile:
            if not re.match('^Filename', row):
                rowPieces = re.split('\s+', row)
                swapSize = getLong(rowPieces[2])
                swapUsed = getLong(rowPieces[3])
                memData['swapTotalSize'] = memData['swapTotalSize'] + swapSize
                memData['swapTotalUsed'] = memData['swapTotalUsed'] + swapUsed
        swapFile.close()

        memFile = open(d + '/meminfo')
        for row in memFile:
            if re.match('^MemTotal:', row):
                value = re.split('\s+', row)[1]
                memData['memTotal'] = getLong(value)
            elif re.match('^MemFree:', row):
                value = re.split('\s+', row)[1]
                memData['memFree'] = getLong(value)
            elif re.match('^Buffers:', row):
                value = re.split('\s+', row)[1]
                memData['buffers'] = getLong(value)
            elif re.match('^Cached:', row):
                value = re.split('\s+', row)[1]
                memData['cached'] = getLong(value)
            elif re.match('^Shmem:', row):
                value = re.split('\s+', row)[1]
                memData['shmem'] = getLong(value)
            elif re.match('^MemAvailable:', row):
                value = re.split('\s+', row)[1]
                memData['memAvailable'] = getLong(value)
            elif re.match('^Slab:', row):
                value = re.split('\s+', row)[1]
                memData['slab'] = getLong(value)

        memFile.close()
        memData['memUsedPercent'] = getLong(round(float(memData['memTotal'] - memData['memFree'] - memData['buffers'] - memData['cached'] - memData['slab']) / memData['memTotal'] * 100 * 100))
        memData['memCached'] = memData['buffers'] + memData['cached'] + memData['slab']
        memData['cacheUsedPercent'] = getLong(10000 - round(float(memData['memTotal'] - memData['buffers'] - memData['cached'] - memData['slab']) / memData['memTotal'] * 100 * 100))
        if memData['swapTotalUsed'] > 0:
            memData['swapUsedPercent'] = getLong(round(float(memData['swapTotalUsed'] / float(memData['swapTotalSize']) * 100 * 100)))
            memData['swapFree'] = getLong(round(float(memData['swapTotalSize'] - float(memData['swapTotalUsed']))))
        else:
            memData['swapUsedPercent'] = 0
            memData['swapFree'] = 0

        self.__saveMemoryInfo(memData)

    def __saveMemoryInfo(self, memData):
        #db.insertDataToDb('mmMemTotal', memData['memTotal'])
        db.insertDataToDb('mmMemAvailable', memData['memAvailable'])
        db.insertDataToDb('mmMemUsedPercent', memData['memUsedPercent'])
        #db.insertDataToDb('mmMemCached', memData['memCached'])
        #db.insertDataToDb('mmMemCacheUsedPercent', memData['cacheUsedPercent'])
        db.insertDataToDb('mmMemSwapFree', memData['swapFree'])
        db.insertDataToDb('mmMemSwapUsedPercent', memData['swapUsedPercent'])
        #db.insertDataToDb('mmMemAvailable', memData['memAvailable'])

    def runDataProcessing(self):
        db.processData()


manmonAgent=ManmonAgent()
manmonAgent.load()
time.sleep(10)

logging.basicConfig(filename='/var/lib/manmon/agent.log',level=logging.DEBUG,format='%(asctime)-15s %(levelname)s %(message)s')
logging.info("Initialized agent")

p = None
while True:
    try:
        time.sleep(0.01)
#        if int(datetime.datetime.utcnow().strftime('%S')) == 50:
#            p = subprocess.Popen("/usr/bin/python /usr/lib/python2.7/site-packages/manmon/manmonPluginRunner.pyc", shell=True)
#            time.sleep(1.1)
        if int(datetime.datetime.utcnow().strftime('%S')) == 0:
#            if p.poll() == None:
#                os.killpg(p.pid, signal.SIGTERM)
            manmonAgent.calc()
            manmonAgent.runDataProcessing()
            time.sleep(1.1)
#            if p.poll() is None:
#                os.killpg(p.pid, signal.SIGKILL)
            p = None
    except:
        logging.exception("Exception running mmagent")
        time.sleep(10)
