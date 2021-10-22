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

TTL = 15 # in seconds

class Controller(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        core.openflow_discovery.addListeners(self)
        self.storage = dict()
        self.ttl = TTL

    def resend_packet (self, dpid, packet_in, out_port):
        """
        Instructs the switch to resend a packet that it had sent to us.
        "packet_in" is the ofp_packet_in object the switch had sent to the
        controller due to a table-miss.
        """
        msg = of.ofp_packet_out()
        msg.data = packet_in
        action = of.ofp_action_output(port = out_port)
        msg.actions.append(action)
        core.openflow.sendToDPID(dpid, msg)

    def _handle_PacketIn (self, event):
        packet = event.parsed
        log.debug("%s arrived at controller", packet)

        dpid = event.dpid
        packet_in = event.ofp
        dst = packet.dst
        src = packet.src
        if dpid not in self.storage:
            self.storage[dpid] = dict()
        mac_to_port = self.storage[dpid]
        current_time = time.time()
        mac_to_port[src] = (packet_in.in_port, current_time)

        if dst in mac_to_port and current_time - mac_to_port[dst][1] <= self.ttl:
            log.debug("Installing flow for %s, %d", packet, current_time - mac_to_port[dst][1])

            destination_port = mac_to_port[dst][0]
            self.resend_packet(dpid, packet_in, destination_port)

            msg = of.ofp_flow_mod()
            msg.hard_timeout = self.ttl
            msg.match = of.ofp_match() # redundant
            msg.match.dl_dst = dst
            action = of.ofp_action_output(port=destination_port)
            msg.actions.append(action)
            core.openflow.sendToDPID(dpid, msg)
        elif dst in mac_to_port:
            log.debug("Flood with expired entry")
            mac_to_port.pop(dst)
            self.resend_packet(dpid, packet_in, of.OFPP_ALL)
        else:
            log.debug("Flood")
            self.resend_packet(dpid, packet_in, of.OFPP_ALL)
        # log.debug("self.storage: %s", self.storage)

    def _handle_ConnectionUp(self, event):
        dpid = dpid_to_str(event.dpid)
        log.debug("Switch %s has come up.", dpid)
        policies = [
            ["10.0.0.1", 4001],
            ["10.0.0.1", "10.0.0.2", 1000],
            # ["10.0.0.1"],
            # ["10.0.0.3"],
            # ["10.0.0.7"]
        ]

        # Send the firewall policies to the switch
        def sendFirewallPolicy(connection, policy):
            log.debug("Set policy")
            msg = of.ofp_flow_mod()
            if len(policy) == 1:
                return
            elif len(policy) == 2:
                msg.match.dl_type = pkt.ethernet.IP_TYPE
                msg.match.nw_proto = pkt.ipv4.TCP_PROTOCOL
                msg.match.nw_dst = IPAddr(policy[0])
                msg.match.tp_dst = policy[1]
            elif len(policy) == 3:
                msg.match.dl_type = pkt.ethernet.IP_TYPE
                msg.match.nw_proto = pkt.ipv4.TCP_PROTOCOL
                msg.match.nw_src = IPAddr(policy[0])
                msg.match.nw_dst = IPAddr(policy[1])
                msg.match.tp_dst = policy[2]
            else:
                log.debug("Unknown policy")
            msg.actions.append(of.ofp_action_output(port = of.OFPP_NONE))
            connection.send(msg)

        for policy in policies:
            sendFirewallPolicy(event.connection, policy)



def launch():
    # Run discovery and spanning tree modules
    pox.openflow.discovery.launch()
    pox.openflow.spanning_forest.launch()

    # Starting the controller module
    core.registerNew(Controller)
