from manmon.get_long import getLong

class DiskStats():
    def __init__(self, mountpoint, size, used, free, isize, iused, ifree, iousage):
        self.mountpoint = mountpoint
        self.size = size
        self.used = used
        self.free = free
        self.percentUsed = getLong(round((self.used * 100 * 100) / float(self.size)))
        self.isize = isize
        self.iused = iused
        self.ifree = ifree
        if isize != 0:
            self.ipercentUsed = getLong(round((self.iused * 100 * 100) / float(self.isize)))
        else:
            self.ipercentUsed = getLong(0)
        self.iousage = iousage

    def __lt__(self, other):
        return self.free < other.free


class NetInterface():
    def __init__(self, dev, receivedBytes, receivedPackets, sentBytes, sentPackets):
        self.dev = dev
        self.receivedBytes = receivedBytes
        self.receivedPackets = receivedPackets
        self.sentBytes = sentBytes
        self.sentPackets = sentPackets
        self.receivedBytesPerSec = receivedBytes
        self.receivedPacketsPerSec = receivedPackets
        self.sentBytesPerSec = sentBytes
        self.sentPacketsPerSec = sentPackets

    def __str__(self):
        return "NetInterface " + self.dev + " recvBytes=" + str(self.receivedBytes) + " recvPackages=" + str(
            self.receivedPackets) + " sentBytes=" + str(self.sentBytes) + " sentPackets=" + str(self.sentPackets)

    def __lt__(self, other):
        return self.receivedBytes < other.receivedBytes
