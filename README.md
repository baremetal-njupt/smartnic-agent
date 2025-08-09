
# Ironic Agent on the SmartNIC
The code for this project resides on and runs within the SmartNIC’s (DPU) embedded operating system, continuously receiving control messages from the cloud platform and triggering the corresponding hardware functions in real time. The SmartNIC includes two internally interconnected Ethernet ports: one connects to the cloud platform network for message exchange and remote management, while the other links to the bare-metal server’s BMC interface for local device control. In addition, the optical port on the SmartNIC is used to connect to a remote storage server, providing storage services. Since the SmartNIC draws power from the host server, and power connectors or cable layouts may vary between server models, it is recommended to verify the correct wiring or consult the SmartNIC vendor prior to deployment to avoid potential damage.

## Code Repositories

The relevant code is organized as follows:

- The code running on the SmartNIC is available at:  
  [https://github.com/baremetal-njupt/smartnic-agent.git](https://github.com/baremetal-njupt/smartnic-agent.git)

- The code running on the OpenStack control node is available at:  
  [https://github.com/baremetal-njupt/NBBM.git](https://github.com/baremetal-njupt/NBBM.git)

- The code implementing the SmartNIC-based forwarding logic for bare-metal traffic is available at:  
  [https://github.com/baremetal-njupt/smartnic-forwarding.git](https://github.com/baremetal-njupt/smartnic-forwarding.git)


# Quick Start

## Installation and Running of the SmartNIC-side Module

### Install

You can follow the instrucitons below to quickly install ironic-ipa component.

- Use the following command to clone the project:
```bash
git clone https://github.com/baremetal-njupt/smartnic-agent.git
```

- Enter the project directory
```bash
cd ../../smartnic-agent-main
```

- Install the new ironic-ipa code
```bash
python3 setup.py install
```

### Run the Ironic Python Agent
```bash
ironic-python-agent --config-file ipa.conf &
```
> 💡 The ipa.conf file is already in the project directory—no edits are required unless you have custom settings.

> 💡 To enable automatic start on SmartNIC(DPU) reboot, consider adding the agent launch command to your system’s service manager (e.g., a systemd unit).

# Extended Functionality
All commands are pre-integrated. If you define new commands on the cloud-platform side that should be received and handled by the SmartNIC (DPU), add your processing logic in ironic_python_agent/extensions/cloud_disk.py and register the new command names in setup.cfg so they’ll be recognized.
> 💡 Newly unboxed SmartNIC devices may require a firmware upgrade before deployment; our unit is model D1055AS running firmware version B509.

Our approach is fully generic. Any SmartNIC (DPU) that runs an embedded operating system, supports the required hardware functions and interfaces, and exposes those interfaces can achieve rapid boot in OpenStack with only minor modifications. Simply invoke the new device’s interfaces in ironic_python_agent/extensions/cloud_disk.py to complete the adaptation.

If you don’t have SmartNIC (DPU) hardware but still want to validate the cloud platform’s driver logic, you can install this project on any Linux machine. The project includes a mock script in `nbl_rpc.py` that returns `ok` for all hardware operations without actually performing them, enabling a full simulation of cloud-side commands and workflows.
