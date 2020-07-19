import datetime
import threading
import select
from socket import *
import time
import json
import random
import copy

nodes = []
sockets = []
ports = ["8080", "8081", "8082", "8083", "8084", "8085"]
hosts = []
lastTimeNodeWentOff = None
my_mutex = threading.Lock()
lastTimeNodeWentOff = time.time()-20
start = time.time()


class Host:
    def __init__(self, IP, port):
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
        self.timeOfLastReceivedHello = 0
        self.packetsReceievedFromThisNeighbor = 0
        self.packetsWereSentToThisNeighbor = 0
        self.timeBecameBi = 0
        self.allTheTimeNeighborWasAvailable = 0
    def show(self):
        self.host.show()
        if timeOfLastReceivedHello == 0:
            print("no HelloMSG was received")
        print("last helloMSG was received ", datetime.datetime.now() - timeOfLastReceivedHello, " seconds ago")

    def equals(self, otherNeighbor):
        if self.host.equals(otherNeighbor.host):
            return True
        return False

    def updateTime(self, newTime):
        self.timeOfLastReceivedHello = newTime

    def updateAvailableTime(self):
        if self.timeBecameBi == 0:
            print("ERROR")
            return
        self.allTheTimeNeighborWasAvailable += (time.time() - self.timeBecameBi)
        self.timeBecameBi = 0

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
    def __init__(self, host, index):
        self.index = index
        self.host = host
        self.allNeighbors = []
        self.bidirectionalNeighbors = []
        self.unidirectionalNeighbors = []
        self.tempNeighbors = []
        self.udpSocket = UdpSocket()
        self.udpSocket.bindTo(host.port)
        self.start_time = None
        self.isOff = False
        self.timeOff = time.time() - 100
        thread = threading.Thread(target=self.handler, args=())
        thread.start()
    
    def handler(self):
        global lastTimeNodeWentOff, my_mutex, start
        self.start_time = time.time()
        firstTime = True
        while(True):
            if time.time() - start > 300:
                for neighbor in self.bidirectionalNeighbors:
                    neighbor.updateAvailableTime()
                break
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
                        rand = random.randint(0, 50)%6
                        nodes[rand].timeOff = time.time()
                        nodes[rand].isOff = True
                        lastTimeNodeWentOff = time.time()
                        break
                    except IndexError:
                        continue
            my_mutex.release()
            #   recieve all the time    ###############################
            # print("IN RECEIVE")
            try:
                readable, writable, exceptional = select.select([self.udpSocket.socket], [], [], 0.2)
                for s in readable:
                    if s == self.udpSocket.socket:
                        rand = random.randint(1, 100)   #   Packet Loss
                        if rand <= 5:
                            continue
                        s.setblocking(0)
                        received = s.recvfrom(2048)[0].decode()
                        received = json.loads(received)
                        receivedPort = received["port"]
                        if self.findInList(self.allNeighbors, receivedPort) != None:
                            neighborInAllNeighbors = self.allNeighbors[self.findInList(self.allNeighbors, receivedPort)]
                            neighborInAllNeighbors.updateTime(time.time())
                            neighborInAllNeighbors.packetsReceievedFromThisNeighbor += 1

                        # change neighbours #######################################
                        #   1.
                        if self.inList(self.unidirectionalNeighbors, receivedPort):
                            if self.inList(self.tempNeighbors, receivedPort):
                                self.unidirectionalNeighbors, self.bidirectionalNeighbors = self.moveFromTo(self.unidirectionalNeighbors, self.bidirectionalNeighbors, receivedPort)
                                self.tempNeighbors[self.findInList(self.tempNeighbors, receivedPort)].updateTime(time.time())
                                neighbor = self.bidirectionalNeighbors[self.findInList(self.bidirectionalNeighbors, receivedPort)]
                                neighbor.updateTime(time.time())
                                # self.tempNeighbors[self.findInList(self.tempNeighbors, receivedPort)].packetsReceievedFromThisNeighbor += 1
                                # self.unidirectionalNeighbors[self.findInList(self.unidirectionalNeighbors, receivedPort)].packetsReceievedFromThisNeighbor += 1
                                neighborInAllNeighbors.timeBecameBi = time.time()

                        #   2.
                        elif self.inList(self.bidirectionalNeighbors, receivedPort):
                            if not self.inList(self.tempNeighbors, receivedPort):
                                self.bidirectionalNeighbors, self.unidirectionalNeighbors = self.moveFromTo(self.bidirectionalNeighbors, self.unidirectionalNeighbors, receivedPort)
                                neighbor = self.unidirectionalNeighbors[self.findInList(unidirectionalNeighbors, receivedPort)]
                                neighbor.updateTime(time.time())
                                # self.bidirectionalNeighbors[self.findInList(self.bidirectionalNeighbors, receivedPort)].packetsReceievedFromThisNeighbor += 1
                                neighborInAllNeighbors.updateAvailableTime()

                        else:
                            #   3.
                            if self.inList(self.tempNeighbors, receivedPort):
                                self.bidirectionalNeighbors = self.copyTo(self.tempNeighbors, self.bidirectionalNeighbors, receivedPort)
                                neighbor = self.bidirectionalNeighbors[self.findInList(self.bidirectionalNeighbors, receivedPort)]
                                neighbor.updateTime(time.time())
                                # self.bidirectionalNeighbors[self.findInList(self.bidirectionalNeighbors, receivedPort)].packetsReceievedFromThisNeighbor += 1
                                neighborInAllNeighbors.timeBecameBi = time.time()
                            #   4.
                            else:
                                newNeighbor = NeighborsInformation(Host(received["IP"], receivedPort))
                                newNeighbor.packetsReceievedFromThisNeighbor += 1
                                newNeighbor.updateTime(time.time())
                                self.unidirectionalNeighbors.append(newNeighbor)
                                if self.findInList(self.allNeighbors, receivedPort) == None:
                                    self.allNeighbors.append(newNeighbor)

            except BlockingIOError:
                pass
            
            #   remove from neighbor list if no packets were receieved in last 8 seconds
            for neighbor in self.bidirectionalNeighbors:
                if time.time() - neighbor.timeOfLastReceivedHello >= 8:
                    self.bidirectionalNeighbors.remove(neighbor)
                    neighbor.updateAvailableTime()

            for neighbor in self.unidirectionalNeighbors:
                if time.time() - neighbor.timeOfLastReceivedHello >= 8:
                    self.unidirectionalNeighbors.remove(neighbor)

            #   send message every second   ###########################
            # print("IN SEND")
            if time.time() - self.start_time >= 2 or firstTime:
                #   check if has enough bi neighbors
                if len(self.bidirectionalNeighbors) < 3:
                    my_mutex.acquire()
                    while (len(self.bidirectionalNeighbors) + len(self.tempNeighbors)) < 3:
                        rand = random.randint(0, 5)
                        if self.index-1 == rand or self.inList(self.unidirectionalNeighbors, hosts[rand].port) or self.inList(self.bidirectionalNeighbors, hosts[rand].port) or self.inList(self.tempNeighbors, hosts[rand].port):
                            continue
                        newNeighbor = NeighborsInformation(hosts[rand])
                        if self.findInList(self.allNeighbors, hosts[rand].port) == None:
                            self.tempNeighbors.append(newNeighbor)
                            self.allNeighbors.append(newNeighbor)
                    for node in self.tempNeighbors:
                        message = HelloMessage(self.index, self.host.IP, self.host.port, self.bidirectionalNeighbors, node.timeOfLastReceivedHello)
                        self.udpSocket.sendTo(message.toJson(), node.host)
                        # self.tempNeighbors[self.findInList(self.tempNeighbors, node.host.port)].packetsWereSentToThisNeighbor += 1
                        self.allNeighbors[self.findInList(self.allNeighbors, node.host.port)].packetsWereSentToThisNeighbor += 1
                    my_mutex.release()
                #   send Hello to unidirectional neighbors
                for node in self.unidirectionalNeighbors:
                    if not self.inList(self.tempNeighbors, node.host.port):
                        message = HelloMessage(self.index, self.host.IP, self.host.port, self.bidirectionalNeighbors, node.timeOfLastReceivedHello)
                        self.udpSocket.sendTo(message.toJson(), node.host)
                        # self.unidirectionalNeighbors[self.findInList(self.unidirectionalNeighbors, node.host.port)].packetsWereSentToThisNeighbor += 1
                        self.allNeighbors[self.findInList(self.allNeighbors, node.host.port)].packetsWereSentToThisNeighbor += 1
                #   send Hello to bidirectional neighbors
                for node in self.bidirectionalNeighbors:
                    if not self.inList(self.tempNeighbors, node.host.port) and not self.inList(self.unidirectionalNeighbors, node.host.port):
                        message = HelloMessage(self.index, self.host.IP, self.host.port, self.bidirectionalNeighbors, node.timeOfLastReceivedHello)
                        self.udpSocket.sendTo(message.toJson(), node.host)
                        # self.bidirectionalNeighbors[self.findInList(self.bidirectionalNeighbors, node.host.port)].packetsWereSentToThisNeighbor += 1
                        self.allNeighbors[self.findInList(self.allNeighbors, node.host.port)].packetsWereSentToThisNeighbor += 1
                self.start_time = time.time()
                firstTime = False
                

            # if self.index == 1:
            
            # print(received)
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

def writeJsonFile():
        data = []
        for node in nodes:
            data_ = []
            for i in node.allNeighbors:
                data_.append("IP: " + str(i.host.IP) + ", port: " +  str(i.host.port) + ", packetsReceievedFromThisNeighbor: " + str(i.packetsReceievedFromThisNeighbor) + ", packetsWereSentToThisNeighbor: " + str(i.packetsWereSentToThisNeighbor))
            data.append(data_)
        
        data2 = []
        for node in nodes:
            data_ = []
            for i in node.allNeighbors:
                data_.append(i.allTheTimeNeighborWasAvailable/300)
            data2.append(data_)

        counter = 0
        for node in nodes:
            fileName = str(node.index) + ".json"
            with open(fileName, 'w', encoding='utf-8') as f:
                json.dump(data[counter], f, ensure_ascii=False, indent=4)
                json.dump(data2[counter], f, ensure_ascii=False, indent=4)
                counter += 1

def initialize():
    for port in ports:
        hosts.append(Host("", port))
    counter = 1
    for host in hosts:
        nodes.append(Node(host, counter))
        counter += 1
    while time.time() - start < 301:
        continue
    writeJsonFile()

initialize()