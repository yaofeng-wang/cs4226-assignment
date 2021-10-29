# CS4226 Assignment

Name: Wang Yao Feng
Matric number: A0121802X

## Implementation design

### Task 1: Building a Virtual Network

- In mininetTopo.py, we will read the "topology.in" file and add the hosts, switchs, links accordingly.

### Task 2: Learning Switch

- In the controller, we store a per switch MAC address to port mapping. Since each switch is uniquely identified by their DPID, we will index each MAC address to port mapping by the DPID of each switch.

### Task 3: Fault Functionality

- In the flow tables, each entry will have a hard time out so that after the TTL has passed, the entries will be removed from the flow table.

- In the controller, we will also store the creation time for each
MAC address to port mapping so that if the difference between the current time and the creation time is more than the TTL, we will flood the event to all the ports, except for the incoming one.

### Task 4: Firewall

- In the controller, we will read the "policy.in" file and create permanent flow table entries in all of the switches to drop the packets
that matches the scenarios indicated.

### Task 5: Premium Traffic

- For all links connecting a switch and a host, we will create 3 queues via the `ovs-vsctl` command.

- In the controller, for each IP address under premium traffic, we will find its MAC address. Whenever a packet is sent to the controller,
we will check if the destination MAC address of that packet is one of those that are under premium traffic. If it is we will send, it to the queue for premium traffic. If not we will send it to the queue for normal traffic.
