'''
Please add your name: Wang Yao Feng
Please add your matric number: A0121802X
'''
import time
import sys
import os
from sets import Set

from pox.core import core

import pox.openflow.libopenflow_01 as of
import pox.openflow.discovery
import pox.openflow.spanning_forest

import pox.lib.packet as pkt
from pox.lib.revent import EventMixin
from pox.lib.util import dpid_to_str
from pox.lib.addresses import IPAddr, EthAddr

log = core.getLogger()

TTL = 65535 # in seconds
FIREWALL_PRIORITY = 100
PREMIUM_TRAFFIC_PRIORITY = 10
LEARNING_SWITCH_PRIORITY = 1

def ip_to_mac(ip):
    b = ["0" + hex(int(v)).split("x")[-1] if len(hex(int(v)).split("x")[-1]) == 1 else hex(int(v)).split("x")[-1] for v in ip.split(".")]
    return "00:00:00:%s:%s:%s" % (b[1], b[2], b[3])

class Controller(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        core.openflow_discovery.addListeners(self)
        self.storage = dict()
        self.ttl = TTL

        self.premium_addr = [
            ip_to_mac("10.0.0.1"),
            ip_to_mac("10.0.0.3"),
            ip_to_mac("10.0.0.7")
        ]

        self.policies = [
            ["10.0.0.1", 4001],
            ["10.0.0.1", "10.0.0.2", 1000],
        ]

        print "Firewall rules:"

        for policy in self.policies:
            if len(policy) == 2:
                print "{'src': '%s', 'port':'%d\\n'}\n" % \
                    (policy[0], policy[1])
            elif len(policy) == 3:
                print "{'src': '%s', 'dst': '%s', 'port':'%d\\n'}\n" % \
                    (policy[0], policy[1], policy[2])

        print "Premium connections:"
        for conn in self.premium_addr:
            print "%s\n" % conn

    def resend_packet(self, dpid, packet_in, out_port, qid):
        """
        Instructs the switch to resend a packet that it had sent to us.
        "packet_in" is the ofp_packet_in object the switch had sent to the
        controller due to a table-miss.
        """
        msg = of.ofp_packet_out()
        msg.data = packet_in
        # action = of.ofp_action_enqueue(port = out_port, queue_id=qid)
        # msg.actions.append(action)
        action = of.ofp_action_output(port = out_port)
        msg.actions.append(action)
        core.openflow.sendToDPID(dpid, msg)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        log.debug("%s arrived", packet)

        dpid = event.dpid
        packet_in = event.ofp
        dst = packet.dst
        src = packet.src
        qid = 1 if (str(dst) in self.premium_addr and str(src) in self.premium_addr) else 2
        # priority = LEARNING_SWITCH_PRIORITY if qid == 2 else PREMIUM_TRAFFIC_PRIORITY
        if dpid not in self.storage:
            self.storage[dpid] = dict()
        mac_to_port = self.storage[dpid]
        current_time = time.time()
        mac_to_port[src] = (packet_in.in_port, current_time)

        if dst in mac_to_port and current_time - mac_to_port[dst][1] <= self.ttl:
            log.debug("Installing flow for %s", packet)

            dst_port = mac_to_port[dst][0]
            self.resend_packet(dpid, packet_in, dst_port, qid)

            msg = of.ofp_flow_mod()
            # msg.priority = priority
            msg.hard_timeout = self.ttl
            msg.match = of.ofp_match() # redundant
            msg.match.dl_dst = dst
            action = of.ofp_action_enqueue(port=dst_port, queue_id=qid)
            msg.actions.append(action)
            # action = of.ofp_action_output(port = dst_port)
            # msg.actions.append(action)
            core.openflow.sendToDPID(dpid, msg)
        elif dst in mac_to_port:
            log.debug("Flood with expired entry")
            mac_to_port.pop(dst)
            self.resend_packet(dpid, packet_in, of.OFPP_ALL, qid)
        else:
            log.debug("Flood")
            self.resend_packet(dpid, packet_in, of.OFPP_ALL, qid)

        for k, v in self.storage.items():
            log.debug("switch %s: %s...(%s)", k, v.keys(), time.time())
        log.debug("\n")

    def _handle_ConnectionUp(self, event):
        dpid = dpid_to_str(event.dpid)
        log.debug("Switch %s has come up.", dpid)

        # Send the firewall policies to the switch
        def sendFirewallPolicy(connection, policy):
            msg = of.ofp_flow_mod()
            # msg.priority = FIREWALL_PRIORITY
            if len(policy) == 1:
                return
            elif len(policy) == 2:
                msg.match.dl_type = pkt.ethernet.IP_TYPE
                msg.match.nw_proto = pkt.ipv4.TCP_PROTOCOL
                msg.match.nw_dst = IPAddr(policy[0])
                msg.match.tp_dst = policy[1]
                msg.actions.append(of.ofp_action_output(port = of.OFPP_NONE))
                connection.send(msg)
            elif len(policy) == 3:
                msg.match.dl_type = pkt.ethernet.IP_TYPE
                msg.match.nw_proto = pkt.ipv4.TCP_PROTOCOL
                msg.match.nw_src = IPAddr(policy[0])
                msg.match.nw_dst = IPAddr(policy[1])
                msg.match.tp_dst = policy[2]
                msg.actions.append(of.ofp_action_output(port = of.OFPP_NONE))
                connection.send(msg)
            else:
                log.debug("Unknown policy")

        for policy in self.policies:
            sendFirewallPolicy(event.connection, policy)
        # print(dir(event.connection))
        # eth_addr = event.connection.eth_addr
        # self.premium_addr = [eth_addr if addr == eth_addr else addr for addr in self.premium_addr]

def launch():
    # Run discovery and spanning tree modules
    pox.openflow.discovery.launch()
    pox.openflow.spanning_forest.launch()

    # Starting the controller module
    core.registerNew(Controller)
