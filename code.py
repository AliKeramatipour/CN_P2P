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
lastTimeNodeWentOff = 0
start = time.time()

TARGET_NUMBER_OF_NEIGHBORS = 3
RUN_TIME = 300
TIME_TO_REMOVE_A_NEIGHBOR = 8
TIME_TO_SEND_A_MESSAGE = 2


class Host:
    def __init__(self, IP, port):
        self.IP = IP
        self.port = port

class NeighborsInformation:
    def __init__(self, host):
        self.host = host
        self.timeOfLastReceivedHello = 0
        self.packetsReceievedFromThisNeighbor = 0
        self.packetsWereSentToThisNeighbor = 0
        self.timeBecameBi = 0
        self.allTheTimeNeighborWasAvailable = 0
        self.bidirectionalNeighbors = []

    def updateTime(self):
        self.timeOfLastReceivedHello = time.time()

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

    def recvFrom(self):
        self.socket.setblocking(0)
        received = self.socket.recvfrom(2048)[0].decode()
        return received

class HelloMessage:
    def __init__(self, sender, IP, port, bidirectionalNeighbors, lastPacketReceiverSentToSender):
        self.sender = sender
        self.IP = IP
        self.port = port
        self.type = HelloMessage
        self.bidirectionalNeighbors = []
        for i in bidirectionalNeighbors:
            self.bidirectionalNeighbors.append(i.host.port)
        self.lastPacketReceiverSentToSender = lastPacketReceiverSentToSender
    def toJson(self):
        message = "{ \"IP\":" + "\"" + self.IP + "\"" + ', "port":' + "\"" + self.port + "\"" + ', "type":"HELLO_MSG"' + ', "bidirectionalNeighbors":' +  "\"" + str(self.bidirectionalNeighbors) +  "\"" + ', "lastPacketReceiverSentToSender":' + "\"" + str(self.lastPacketReceiverSentToSender) + "\"" + ', "lastPacketSenderSentToRecevier":' + "\"" + str(time.time()) + "\"" "}"
        return message

class Node:
    def __init__(self, host, index):
        self.index = index
        self.host = host
        self.requested = []
        self.allNeighbors = []
        self.bidirectionalNeighbors = []
        self.udpSocket = UdpSocket()
        self.udpSocket.bindTo(host.port)
        self.start_time = 0
        self.isOff = False
        self.timeOff = 0
        thread = threading.Thread(target=self.handler, args=())
        thread.start()
    
    def handler(self):
        global lastTimeNodeWentOff, my_mutex, start
        self.start_time = time.time()
        firstTime = True
        while(True):
            if time.time() - start > RUN_TIME:
                for neighbor in self.bidirectionalNeighbors:
                    neighborInAllNeighbors = self.allNeighbors[self.findInList(self.allNeighbors, neighbor.host.port)]
                    neighborInAllNeighbors.updateAvailableTime()
                break
            
            #   is Node off? ###########################################
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

            #   recieve all the time    ###############################
            self.recevie()
        
            #   remove from neighbor list if no packets were receieved in last 8 seconds
            for neighbor in self.bidirectionalNeighbors:
                if time.time() - neighbor.timeOfLastReceivedHello >= TIME_TO_REMOVE_A_NEIGHBOR:
                    self.bidirectionalNeighbors.remove(neighbor)
                    neighborInAllNeighbors = self.allNeighbors[self.findInList(self.allNeighbors, neighbor.host.port)]
                    neighborInAllNeighbors.updateAvailableTime()

            for neighbor in self.requested:
                if time.time() - neighbor.timeOfLastReceivedHello >= TIME_TO_REMOVE_A_NEIGHBOR:
                    self.requested.remove(neighbor)

            #   send message every second   ###########################
            if time.time() - self.start_time >= TIME_TO_SEND_A_MESSAGE or firstTime:
                self.send(firstTime)
                firstTime = False

    def send(self, firstTime):
        #   check if has enough bidirectional neighbors
        if len(self.bidirectionalNeighbors) < 3:
            rand = random.randint(0, 5)
            if not self.index-1 == rand or self.inList(self.requested, hosts[rand].port) or self.inList(self.bidirectionalNeighbors, hosts[rand].port):
                tempNeighbor = NeighborsInformation(hosts[rand])
                if not self.inList(self.allNeighbors, hosts[rand].port):
                    self.allNeighbors.append(tempNeighbor)
                self.requested.append(tempNeighbor)

        #   send Hello to requested
        for node in self.requested:
            message = HelloMessage(self.index, self.host.IP, self.host.port, self.bidirectionalNeighbors, node.timeOfLastReceivedHello)
            self.udpSocket.sendTo(message.toJson(), node.host)
            self.allNeighbors[self.findInList(self.allNeighbors, node.host.port)].packetsWereSentToThisNeighbor += 1
        
        #   send Hello to bidirectional neighbors
        for node in self.bidirectionalNeighbors:
            message = HelloMessage(self.index, self.host.IP, self.host.port, self.bidirectionalNeighbors, node.timeOfLastReceivedHello)
            self.udpSocket.sendTo(message.toJson(), node.host)
            self.allNeighbors[self.findInList(self.allNeighbors, node.host.port)].packetsWereSentToThisNeighbor += 1
            #   ali khate bala lazame??
        self.start_time = time.time()

    def recevie(self):
        try:
            rand = random.randint(1, 100)   #   Packet Loss
            if rand <= 5:
                return
            # self.udpSocket.socket.setblocking(0)
            received = self.udpSocket.recvFrom()
            received = json.loads(received)
            receivedPort = received["port"]
            recentlyHeard = []
            recentlyHeard.append(received["bidirectionalNeighbors"])

            #   check if in bidirectional, update time
            if self.inList(self.bidirectionalNeighbors, receivedPort):
                neighbor = self.bidirectionalNeighbors[self.findInList(self.bidirectionalNeighbors, receivedPort)]
                neighbor.updateTime()

            if self.inList(self.requested, receivedPort):
                neighbor = self.requested[self.findInList(self.requested, receivedPort)]
                neighbor.updateTime()
            
            if self.inList(self.allNeighbors, receivedPort):
                neighborInAllNeighbors = self.allNeighbors[self.findInList(self.allNeighbors, receivedPort)]
                neighborInAllNeighbors.packetsReceievedFromThisNeighbor += 1
            else:
                newNeighbor = NeighborsInformation(Host(received["IP"], receivedPort))
                newNeighbor.packetsReceievedFromThisNeighbor += 1
                self.allNeighbors.append(newNeighbor)
            
            #   if full, do nothing
            if len(self.bidirectionalNeighbors) < TARGET_NUMBER_OF_NEIGHBORS:
                # change neighbours #######################################

                
                if self.inListNeighbor(recentlyHeard) and not self.inList(self.bidirectionalNeighbors, receivedPort):
                    self.requested, self.bidirectionalNeighbors = self.moveFromTo(self.requested, self.bidirectionalNeighbors, receivedPort)
                    if not self.inList(self.allNeighbors, receivedPort):
                        newNeighbor.timeBecameBi = time.time()
                        self.allNeighbors.append(newNeighbor)
                    else:
                        neighborInAllNeighbors = self.allNeighbors[self.findInList(self.allNeighbors, receivedPort)]
                        if neighborInAllNeighbors.timeBecameBi == 0:
                            neighborInAllNeighbors.timeBecameBi = time.time()

                elif self.inList(self.requested, receivedPort):
                    if not self.inList(self.bidirectionalNeighbors, receivedPort):
                        self.requested, self.bidirectionalNeighbors = self.moveFromTo(self.requested, self.bidirectionalNeighbors, receivedPort)
                        neighborInAllNeighbors = self.allNeighbors[self.findInList(self.allNeighbors, receivedPort)]
                        neighborInAllNeighbors.timeBecameBi = time.time()
                    else:   #   remove from requested
                        temp = []
                        self.requested, temp = self.moveFromTo(self.requested, temp, receivedPort)
                
                else:
                    newNeighbor = NeighborsInformation(Host(received["IP"], receivedPort))
                    newNeighbor.packetsReceievedFromThisNeighbor += 1
                    newNeighbor.updateTime()
                    self.requested.append(newNeighbor)
                    #   ali yadam bendaz ye chizi beporsam azat

                    # print(received)
        except BlockingIOError:
            pass

    def findInList(self, list, port):
        for i in range (0, len(list)):
            if list[i].host.port == port:
                return i

    def inList(self, list, port):
        for i in list:
            if port == i.host.port:
                return True
        return False

    def inListNeighbor(self, li):
        res = li[0].strip('][').split(', ')
        for port in res:
            if ("'" + self.host.port  + "'") == port:
                return True
        return False

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
            for i in node.bidirectionalNeighbors:
                print(i)
                data_.append(i.host.port)
            data2.append(data_)
             
        data3 = []
        for node in nodes:
            data_ = []
            for i in node.allNeighbors:
                data_.append(i.allTheTimeNeighborWasAvailable/300)
            data3.append(data_)

        data4 = []
        for node in nodes:
            data_ = []
            for i in node.requested:
                print(i)
                data_.append(i.host.port)
            data4.append(data_)

        counter = 0
        for node in nodes:
            fileName = str(node.index) + ".json"
            with open(fileName, 'w', encoding='utf-8') as f:
                print(data2[counter])
                json.dump(data[counter], f, ensure_ascii=False, indent=4)
                json.dump(data2[counter], f, ensure_ascii=False, indent=4)
                json.dump(data3[counter], f, ensure_ascii=False, indent=4)
                json.dump("Bidirectional Neighbors", f, ensure_ascii=False, indent=4)
                json.dump(data2[counter], f, ensure_ascii=False, indent=4)
                json.dump("Uidirectional Neighbors", f, ensure_ascii=False, indent=4)
                json.dump(data4[counter], f, ensure_ascii=False, indent=4)
                counter += 1

def initialize():
    for port in ports:
        hosts.append(Host("", port))
    counter = 1
    for host in hosts:
        nodes.append(Node(host, counter))
        counter += 1
    while time.time() - start < RUN_TIME + 1:
        continue

initialize()
writeJsonFile()