'''
Please add your name:
Please add your matric number:
'''

import sys
import os
from sets import Set

from pox.core import core

import pox.openflow.libopenflow_01 as of
import pox.openflow.discovery
import pox.openflow.spanning_forest

from pox.lib.revent import EventMixin
from pox.lib.util import dpid_to_str
from pox.lib.addresses import IPAddr, EthAddr

log = core.getLogger()

class Controller(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        core.openflow_discovery.addListeners(self)
        self.storage = dict()

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
        dpid = event.dpid
        packet = event.parsed
        packet_in = event.ofp
        dst = packet.dst
        src = packet.src
        if dpid not in self.storage:
            self.storage[dpid] = dict()
        mac_to_port = self.storage[dpid]
        mac_to_port[src] = packet_in.in_port

        log.debug("Packet arrived at controller: %s", packet)

        if dst in mac_to_port:
            self.resend_packet(dpid, packet_in, mac_to_port[dst])

            log.debug("Installing flow for packets from %s, going to %s", src,dst)
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match()
            msg.match.dl_dst = dst
            msg.match.dl_src = src
            # msg.match = of.ofp_match.from_packet(packet)
            action = of.ofp_action_output(port=mac_to_port[dst])
            msg.actions.append(action)
            core.openflow.sendToDPID(dpid, msg)
        else:
            log.debug("Flood...")
            self.resend_packet(dpid, packet_in, of.OFPP_ALL)
        print self.storage


    def _handle_ConnectionUp(self, event):
        dpid = dpid_to_str(event.dpid)
        log.debug("Switch %s has come up.", dpid)

        # Send the firewall policies to the switch
        def sendFirewallPolicy(connection, policy):
            # define your message here

            # OFPP_NONE: outputting to nowhere
            # msg.actions.append(of.ofp_action_output(port = of.OFPP_NONE))
            pass

        # for i in [FIREWALL_POLICIES]:
        #     sendFirewallPolicy(event.connection, i)


def launch():
    # Run discovery and spanning tree modules
    pox.openflow.discovery.launch()
    pox.openflow.spanning_forest.launch()

    # Starting the controller module
    core.registerNew(Controller)
