'''
Please add your name:
Please add your matric number:
'''

import os
import sys
import atexit
from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.link import Link
from mininet.node import RemoteController

net = None

class TreeTopo(Topo):

    def build(self):
        switches = dict()
        hosts = dict()
        N, M, L, = 0, 0 ,0

        with open("topology.in", "r") as infile:
                for i, line in enumerate(infile):
                        if i == 0:
                                N, M, L = [int(v) for v in line.split()]
                                for i in range(1, N+1):
                                        name = "h" + str(i)
                                        hosts[name] = self.addHost(name)
                                for i in range(1, M+1):
                                        name = "s" + str(i)
                                        switches[name] = self.addSwitch(name)
                        else:
                                h, s, bw = line.split(",")
                                dev2 = switches[s]
                                if h[0] == "h":
                                        dev1 = hosts[h]
                                else:
                                        dev1 = switches[h]
                                self.addLink(dev1, dev2, bw=int(bw))

def startNetwork():
    info('** Creating the tree network\n')
    topo = TreeTopo()

    global net
    net = Mininet(topo=topo, link = Link,
                  controller=lambda name: RemoteController(name, ip='192.168.56.1'),
                  listenPort=6633, autoSetMacs=True)

    info('** Starting the network\n')
    net.start()

    # Create QoS Queues
    # > os.system('sudo ovs-vsctl -- set Port [INTERFACE] qos=@newqos \
    #            -- --id=@newqos create QoS type=linux-htb other-config:max-rate=[LINK SPEED] queues=0=@q0,1=@q1,2=@q2 \
    #            -- --id=@q0 create queue other-config:max-rate=[LINK SPEED] other-config:min-rate=[LINK SPEED] \
    #            -- --id=@q1 create queue other-config:min-rate=[X] \
    #            -- --id=@q2 create queue other-config:max-rate=[Y]')

    info('** Running CLI\n')
    CLI(net)

def stopNetwork():
    if net is not None:
        net.stop()
        # Remove QoS and Queues
        os.system('sudo ovs-vsctl --all destroy Qos')
        os.system('sudo ovs-vsctl --all destroy Queue')


if __name__ == '__main__':
    # Force cleanup on exit by registering a cleanup function
    atexit.register(stopNetwork)

    # Tell mininet to print useful information
    setLogLevel('info')
    startNetwork()
