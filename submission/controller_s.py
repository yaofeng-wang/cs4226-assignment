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
LOG_UNKOWN_POLICY = "Unknown policy"
LOG_PACKET_ARRIVED_FMT = "%d:%s arrived"
LOG_INSTALLING_FLOW_FMT = "%d:Installing flow for %s"
LOG_FLOOD_WITH_EXPIRED_ENTRY_FMT = "%d:Flood with expired entry"
LOG_FLOOD_FMT = "%d:Flood"
LOG_SWITCH_CAME_UP_FMT = "Switch %s has come up."

TTL = 20 # in seconds
FIREWALL_PRIORITY = 100
PREMIUM_TRAFFIC_PRIORITY = 10
LEARNING_SWITCH_PRIORITY = 1
POLICY_FILE_NAME = "policy.in"
READ_MODE = "r"

def ip_to_mac(ip):
    b = ["0" + hex(int(v)).split("x")[-1] if len(hex(int(v)).split("x")[-1]) == 1 else hex(int(v)).split("x")[-1] for v in ip.split(".")]
    return "00:00:00:%s:%s:%s" % (b[1], b[2], b[3])

class Controller(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        core.openflow_discovery.addListeners(self)
        self.storage = dict()
        self.ttl = TTL
        self.num_firewall_policies = 0
        self.num_premium_addr = 0
        self.policies = []
        self.premium_addr = []
        self.read_policies()

    def read_policies(self):
        with open(POLICY_FILE_NAME, READ_MODE) as infile:
            for i, line in enumerate(infile):
                if i == 0:
                    self.num_firewall_policies, self.num_premium_addr = [int(v) for v in line.split()]
                elif i <= self.num_firewall_policies:
                    l = line.split(',')
                    l[-1] = int(l[-1].strip())
                    self.policies.append(l)
                else:
                    self.premium_addr.append(ip_to_mac(line))

        print("%d, %d" % (self.num_firewall_policies, self.num_premium_addr))
        print("Firewall rules:")

        for policy in self.policies:
            if len(policy) == 2:
                print("{'src': '%s', 'port':'%d\\n'}\n" % (policy[0], policy[1]))
            elif len(policy) == 3:
                print("{'src': '%s', 'dst': '%s', 'port':'%d\\n'}\n" % (policy[0], policy[1], policy[2]))

        print("Premium connections:")
        for conn in self.premium_addr:
            print("%s\n" % conn)


    def resend_packet(self, dpid, packet_in, out_port, qid):
        msg = of.ofp_packet_out()
        msg.data = packet_in
        action = of.ofp_action_output(port = out_port)
        msg.actions.append(action)
        core.openflow.sendToDPID(dpid, msg)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        dpid = event.dpid
        log.debug(LOG_PACKET_ARRIVED_FMT % (dpid, packet))
        packet_in = event.ofp
        dst = packet.dst
        src = packet.src
        # qid = 1 if (str(dst) in self.premium_addr and str(src) in self.premium_addr) else 2
        qid = 1 if str(dst) in self.premium_addr else 2
        priority = LEARNING_SWITCH_PRIORITY if qid == 2 else PREMIUM_TRAFFIC_PRIORITY
        if dpid not in self.storage:
            self.storage[dpid] = dict()
        mac_to_port = self.storage[dpid]
        current_time = time.time()
        mac_to_port[src] = (packet_in.in_port, current_time)

        if dst in mac_to_port and current_time - mac_to_port[dst][1] <= self.ttl:
            log.debug(LOG_INSTALLING_FLOW_FMT % (dpid, packet))

            dst_port = mac_to_port[dst][0]
            self.resend_packet(dpid, packet_in, dst_port, qid)

            msg = of.ofp_flow_mod()
            msg.priority = priority
            msg.hard_timeout = self.ttl
            msg.match.dl_dst = dst
            msg.match.dl_src = src
            action = of.ofp_action_enqueue(port=dst_port, queue_id=qid)
            msg.actions.append(action)
            core.openflow.sendToDPID(dpid, msg)
        elif dst in mac_to_port:
            log.debug(LOG_FLOOD_WITH_EXPIRED_ENTRY_FMT % dpid)
            mac_to_port.pop(dst)
            self.resend_packet(dpid, packet_in, of.OFPP_FLOOD, qid)
        else:
            log.debug(LOG_FLOOD_FMT % dpid)
            self.resend_packet(dpid, packet_in, of.OFPP_FLOOD, qid)

    def _handle_ConnectionUp(self, event):
        dpid = dpid_to_str(event.dpid)
        log.debug(LOG_SWITCH_CAME_UP_FMT % dpid)

        def sendFirewallPolicy(connection, policy):
            msg = of.ofp_flow_mod()
            msg.priority = FIREWALL_PRIORITY
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
                log.debug(LOG_UNKOWN_POLICY)

        for policy in self.policies:
            sendFirewallPolicy(event.connection, policy)

def launch():
    pox.openflow.discovery.launch()
    pox.openflow.spanning_forest.launch()

    core.registerNew(Controller)
