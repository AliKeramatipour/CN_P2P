import datetime
import threading
import select
from socket import *
import time
import json
import random

nodes = []
sockets = []
ports = ["8080", "8081", "8082", "8083", "8084", "8085"]
hosts = []
lastTimeNodeWentOff = None
my_mutex = threading.Lock()
lastTimeNodeWentOff = time.time()-20


class Host:
    def __init__(self, IP = None, port = None):
        self.IP = IP
        self.port = port
    def show(self):
        print(self.IP, "    :   ", self.port)
    def equals(self, host):
        if self.port != host.port:
            return False
        return True

class NeighborsInformation:
    def __init__(self, host = None):
        self.host = host
        self.timeOfLastHello = 0
    def show(self):
        self.host.show()
        if timeOfLastHello == 0:
            print("no HelloMSG was received")
        print("last helloMSG was received ", datetime.datetime.now() - timeOfLastHello, " seconds ago")

    def equals(self, otherNeighbor):
        if self.host.equals(otherNeighbor.host):
            return True
        return False

    def updateTime(self, newTime):
        self.timeOfLastHello = newTime

class UdpSocket:
    def __init__(self):
        self.socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
        sockets.append(self.socket)
    def bindTo(self, port):
        try:
            self.socket.bind(("", int(port)))
        except:
            print("bind failed  ")
            return False
        return True
    def sendTo(self, message, dest):
        rand = random.randint(1, 100)   #   Packet Loss
        if rand <= 5:
            return
        self.socket.sendto(message.encode(), (dest.IP, int(dest.port)))

class HelloMessage:
    def __init__(self, sender, IP, port, bidirectionalNeighbors, lastPacketReceiverSentToSender):
        self.sender = sender
        self.IP = IP
        self.port = port
        self.type = HelloMessage
        self.bidirectionalNeighbors = bidirectionalNeighbors
        # self.lastPacketSenderSent = lastPacketSenderSent
        self.lastPacketReceiverSentToSender = lastPacketReceiverSentToSender
    def toJson(self):
        message = "{ \"IP\":" + "\"" + self.IP + "\"" + ', "port":' + "\"" + self.port + "\"" + ', "type":"HELLO_MSG"' + ', "bidirectionalNeighbors":' + "\"" + str(self.bidirectionalNeighbors) + "\"" + ', "lastPacketSenderSentToReceiver":' + "\"" + str(time.time()) + "\"" + ', "lastPacketReceiverSentToSender":' + "\"" + str(self.lastPacketReceiverSentToSender) + "\"" "}"
        return message

class Node:
    flag = True
    def __init__(self, host, temp, index):
        self.index = index
        self.host = host
        # self.tempNeighbors = []
        self.bidirectionalNeighbors = []
        self.unidirectionalNeighbors = []
        self.tempNeighbors = []
        self.udpSocket = UdpSocket()
        self.udpSocket.bindTo(host.port)
        self.start_time = None
        self.isOff = False
        self.timeOff = None
        thread = threading.Thread(target=self.handler, args=())
        thread.start()
    
    def handler(self):
        global lastTimeNodeWentOff, my_mutex
        self.start_time = time.time()
        firstTime = True
        while(True):
            #   is Node off ###########################################
            if self.isOff:
                if time.time() - self.timeOff >= 20:
                    self.isOff = False
                else:
                    continue

            #   Turn a random node off  ###############################
            my_mutex.acquire()
            if time.time() - lastTimeNodeWentOff >= 10:
                while(True):
                    print("HEREE", self.index, lastTimeNodeWentOff)
                    try:
                        rand = random.randint(0, 5)
                        nodes[rand].timeOff = time.time()
                        nodes[rand].isOff = True
                        lastTimeNodeWentOff = time.time()
                        break
                    except IndexError:
                        continue
            my_mutex.release()

            #   send message every second   ###########################
            if time.time() - self.start_time >= 1 or firstTime:
                #   check if has enough bi neighbors
                if len(self.bidirectionalNeighbors) < 3:
                    my_mutex.acquire()
                    while (len(self.bidirectionalNeighbors) + len(self.tempNeighbors)) < 3:
                        rand = random.randint(0, 5)
                        if self.index-1 == rand or self.inList(self.unidirectionalNeighbors, hosts[rand].port) or self.inList(self.bidirectionalNeighbors, hosts[rand].port):
                            continue
                        self.tempNeighbors.append(NeighborsInformation(hosts[rand]))
                    for node in self.tempNeighbors:
                        message = HelloMessage(self.index, self.host.IP, self.host.port, self.bidirectionalNeighbors, node.timeOfLastHello)
                        self.udpSocket.sendTo(message.toJson(), node.host)
                    my_mutex.release()
                #   send hello to other neighbors too
                for node in self.unidirectionalNeighbors:
                    if not self.inList(self.tempNeighbors, node.host.port):
                        message = HelloMessage(self.index, self.host.IP, self.host.port, self.bidirectionalNeighbors, node.timeOfLastHello)
                        self.udpSocket.sendTo(message.toJson(), node.host)
                for node in self.bidirectionalNeighbors:
                    if not self.inList(self.tempNeighbors, node.host.port) and not self.inList(self.unidirectionalNeighbors, node.host.port):
                        message = HelloMessage(self.index, self.host.IP, self.host.port, self.bidirectionalNeighbors, node.timeOfLastHello)
                        self.udpSocket.sendTo(message.toJson(), node.host)
                self.start_time = time.time()
                firstTime = False

            #   recieve all the time    ###############################
            self.udpSocket.socket.setblocking(0)
            try:
                received = self.udpSocket.socket.recv(2048)
                received = str(received, 'utf-8')
                received = json.loads(received)
                receivedPort = received["port"]
            except:
                continue

            # change neighbours #######################################
            #   1.
            if self.inList(self.unidirectionalNeighbors, receivedPort):
                if self.inList(self.tempNeighbors, receivedPort):
                    self.unidirectionalNeighbors, self.bidirectionalNeighbors = self.moveFromTo(self.unidirectionalNeighbors, self.bidirectionalNeighbors, receivedPort)
                    self.tempNeighbors[self.findInList(self.tempNeighbors, receivedPort)].updateTime(time.time())
                    self.unidirectionalNeighbors[self.findInList(self.unidirectionalNeighbors, receivedPort)].updateTime(time.time())
            #   2.
            elif self.inList(self.bidirectionalNeighbors, receivedPort):
                if not self.inList(self.tempNeighbors, receivedPort):
                    self.bidirectionalNeighbors, self.unidirectionalNeighbors = self.moveFromTo(self.bidirectionalNeighbors, self.unidirectionalNeighbors, receivedPort)
                    bidirectionalNeighbors[self.findInList(bidirectionalNeighbors, receivedPort)].updateTime(time.time())
            #   3.
            else:
                if self.inList(self.tempNeighbors, receivedPort):
                    self.bidirectionalNeighbors = self.copyTo(self.tempNeighbors, self.bidirectionalNeighbors, receivedPort)
                    self.bidirectionalNeighbors[self.findInList(self.bidirectionalNeighbors, receivedPort)].updateTime(time.time())
                else:
                    newNeighbor = NeighborsInformation(Host(received["IP"], receivedPort))
                    newNeighbor.updateTime(time.time())
                    self.unidirectionalNeighbors.append(newNeighbor)

            for neighbor in self.bidirectionalNeighbors:
                if time.time() - neighbor.timeOfLastHello >= 8:
                    self.bidirectionalNeighbors.remove(neighbor)

            for neighbor in self.unidirectionalNeighbors:
                if time.time() - neighbor.timeOfLastHello >= 8:
                    self.unidirectionalNeighbors.remove(neighbor)

            print(received)
            # print("port: ", self.host.port, "temp: ", len(self.tempNeighbors), "uni: ", len(self.unidirectionalNeighbors), "bi: ", len(self.bidirectionalNeighbors))

    def findInList(self, list, port):
        for i in range (0, len(list)):
            if list[i].host.port == port:
                return i
    def inList(self, list, port):
        for i in list:
            if port == i.host.port:
                return True
        return False

    def copyTo(self, list1, list2, port):
        for i in list1:
            if i.host.port == port:
                list2.append(i)
                break
        return list2

    def moveFromTo(self, list1, list2, port):
        for i in list1:
            if i.host.port == port:
                list2.append(i)
                list1.remove(i)
                break
        return list1, list2

def initialize():
    for port in ports:
        hosts.append(Host("", port))
    counter = 1
    for host in hosts:
        temp = []
        for host2 in hosts:
            if host.equals(host2):
                continue
            temp.append(NeighborsInformation(host2))
        nodes.append(Node(host, temp, counter))
        counter += 1

initialize()