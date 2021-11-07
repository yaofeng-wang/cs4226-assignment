'''
Please add your name: Wang Yao Feng
Please add your matric number: A0121802X
'''
import os
import sys
import atexit
from mininet.net import Mininet
from mininet.log import setLogLevel, info, error, debug
from mininet.cli import CLI
from mininet.topo import Topo, SingleSwitchTopo
from mininet.link import Link, TCLink, TCIntf, Intf
from mininet.node import RemoteController
from mininet.util import dumpNodeConnections
Python3 = sys.version_info[0] == 3
BaseString = str if Python3 else getattr( str, '__base__' )
net = None

READ_MODE = "r"
TOPO_FILE_NAME = "topology.in"
class Link(Link):

    def __init__( self, node1, node2, port1=None, port2=None,
            intfName1=None, intfName2=None, addr1=None, addr2=None,
            intf=Intf, cls1=None, cls2=None, params1=None,
            params2=None, fast=True, **params ):
        # This is a bit awkward; it seems that having everything in
            # params is more orthogonal, but being able to specify
            # in-line arguments is more convenient! So we support both.
            params1 = dict( params1 ) if params1 else {}
            params2 = dict( params2 ) if params2 else {}
            if port1 is not None:
                params1[ 'port' ] = port1
            if port2 is not None:
                params2[ 'port' ] = port2
            if 'port' not in params1:
                params1[ 'port' ] = node1.newPort()
            if 'port' not in params2:
                params2[ 'port' ] = node2.newPort()
            if not intfName1:
                intfName1 = self.intfName( node1, params1[ 'port' ] )
            if not intfName2:
                intfName2 = self.intfName( node2, params2[ 'port' ] )

            # Update with remaining parameter list
            params1.update( params )
            params2.update( params )

            self.fast = fast
            if fast:
                params1.setdefault( 'moveIntfFn', self._ignore )
                params2.setdefault( 'moveIntfFn', self._ignore )
                self.makeIntfPair( intfName1, intfName2, addr1, addr2,
                            node1, node2, deleteIntfs=False )
            else:
                self.makeIntfPair( intfName1, intfName2, addr1, addr2 )

            if not cls1:
                cls1 = intf
            if not cls2:
                cls2 = intf

            intf1 = cls1( name=intfName1, node=node1,
                    link=self, mac=addr1, **params1  )
            intf2 = cls2( name=intfName2, node=node2,
                    link=self, mac=addr2, **params2 )

            # All we are is dust in the wind, and our two interfaces
            self.intf1, self.intf2 = intf1, intf2

class CustomTopo(Topo):

    def read_topo(self):
        N, M, L, = 0, 0 ,0
        with open(TOPO_FILE_NAME, READ_MODE) as infile:
            for i, line in enumerate(infile):
                if i == 0:
                    N, M, L = [int(v) for v in line.split()]
                    for i in range(1, N+1):
                        name = "h" + str(i)
                        self.addHost(name)
                    for i in range(1, M+1):
                        name = "s" + str(i)
                        self.addSwitch(name)
                    info("N = %d M = %d L = %d\n" % (N, M, L))
                else:
                    h, s, bw = line.split(",")
                    self.addLink(h, s, bw=int(bw))
                    info("dev1 = %s  dev2 = %s bw = %s\n" % (h, s, bw))

    def build(self):
        self.read_topo()

def startNetwork():
    info('** Creating the tree network\n')
    topo = CustomTopo()

    global net
    net = Mininet(topo=topo, link = Link,
            controller=lambda name: RemoteController(name, ip='192.168.56.1'),
            listenPort=6633,
            autoSetMacs=True,
            xterms=True)

    info('** Starting the network\n')
    net.start()
    for switch in net.switches:
        for intf in switch.intfList():
            if str(intf) == "lo":
                continue
            dev1 = str(intf.link).split("<->")[0].split("-")[0]
            dev2 = str(intf.link).split("<->")[1].split("-")[0]
            info("%s: %s<->%s (%d)\n" % (intf, dev1, dev2, intf.params["bw"]))

            if dev1[0] == "h" or dev2[0] == "h":
                bw = intf.params["bw"]*1000000 # in bits/s
                X = 0.8 * bw
                Y = 0.5 * bw
                os.system('sudo ovs-vsctl -- set Port %s qos=@newqos \
                        -- --id=@newqos create QoS type=linux-htb other-config:max-rate=%d queues=0=@q0,1=@q1,2=@q2 \
                        -- --id=@q0 create queue other-config:max-rate=%d other-config:min-rate=%d \
                        -- --id=@q1 create queue other-config:min-rate=%d \
                        -- --id=@q2 create queue other-config:max-rate=%d'
                        % (intf, bw, bw, bw, X, Y))
                info("Set up QoS Queue for %s: %s<->%s (%d)\n" %
                        (intf, dev1, dev2, intf.params["bw"]))
                info("%d %d %d\n\n" % (bw, X, Y))

    info('** Running CLI\n')
    CLI(net)

def perfTest():
    info('** Creating network and run simple performance test\n')
    topo = SingleSwitchTopo(n=4)
    # modify the ip address if you are using a remote pox controller
    net = Mininet(topo=topo, link=Link,
            controller=lambda name: RemoteController(name, ip='127.0.0.1'),
            listenPort=6633, autoSetMacs=True)
    net.start()
    info("Dumping host connections")
    dumpNodeConnections(net.hosts)
    info("Testing network connectivity")
    net.pingAll()

    h1, h4 = net.get('h1', 'h4')

    info("Testing connectivity between h1 and h4")
    net.ping((h1,h4))
    info("Testing bandwidth between h1 and h4")
    net.iperf((h1,h4),port=8080)
    net.stop()

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
    # run option1: start some basic test on your topology such as pingall, ping and iperf.
    #perfTest()
    # run option2: start a command line to explore more of mininet, you can try different commands.
    startNetwork()
