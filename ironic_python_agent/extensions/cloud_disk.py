from oslo_log import log
from oslo_concurrency import processutils
from oslo_utils import units
from ironic_python_agent.extensions import base
from ironic_python_agent.utils import execute
import hashlib
from werkzeug.exceptions import BadRequest
import json
import os
import time
LOG = log.getLogger(__name__)


class RpcCommandError(Exception):  
    """Custom exception for RPC command errors."""
    def __init__(self, message, cmd_result):
        super(RpcCommandError, self).__init__(message)  
        self.cmd_result = cmd_result

    def __str__(self):
        base_msg = super(RpcCommandError, self).__str__() 
        return f"{base_msg}. Cmd Result: {self.cmd_result}"

class DeviceManager:
    """Manage device names."""
    def __init__(self):
        self._created_devices = set()
        self.load_devices() 
    
    def persist_devices(self):
        try:
            with open('devices.json', 'w') as f:
                json.dump(list(self._created_devices), f)
        except IOError as e:
            LOG.error(f"IOError occurred while persisting devices: {e}")
        except Exception as e:
            LOG.error(f"Unexpected error occurred while persisting devices: {e}")
                
    def load_devices(self):
        try:
            if os.path.exists('devices.json'):
                with open('devices.json', 'r') as f:
                    devices = json.load(f)
                    self._created_devices = set(devices)
            else:
                print("No existing devices.json file found. Starting with an empty set.")
        except json.JSONDecodeError:
            LOG.warning("Error reading devices.json. Starting with an empty set.")
        except Exception as e:
            LOG.warning(f"An unexpected error occurred: {e}. Starting with an empty set.")                

    def _find_unique_name(self, prefix, ip, iqn):
        """Find unique device name using ip and iqn."""
        unique_hash = hashlib.md5(f"{ip}_{iqn}".encode()).hexdigest()[:8]
        unique_name = f"{prefix}{unique_hash}"
        return unique_name

    def _generate_unique_name(self, prefix, ip, iqn):
        """Generate unique device name using ip and iqn."""
        unique_hash = hashlib.md5(f"{ip}_{iqn}".encode()).hexdigest()[:8]
        unique_name = f"{prefix}{unique_hash}"
        if unique_name in self._created_devices:
            raise ValueError(f"Device name '{unique_name}' already exists.")
        return unique_name

    def add_device_name(self, device_name):
        """Add the device name to the set."""
        self._created_devices.add(device_name)
        self.persist_devices()

    def remove_device_name(self, device_name):
        """Remove the device name from the set."""
        self._created_devices.discard(device_name)
        self.persist_devices()

    def get_iscsi_name(self, ip, iqn):
        """Generate iSCSI device name."""
        return self._generate_unique_name("iscsi", ip, iqn)

    def get_blk_name(self, ip, iqn):
        """Generate block device name."""
        return self._generate_unique_name("blk", ip, iqn)

    def check_iscsi_name(self, ip, iqn):
        """Check if the iSCSI name exists."""
        iscsi_name = self._find_unique_name("iscsi", ip, iqn)
        if iscsi_name not in self._created_devices:
            raise ValueError(f"iSCSI name '{iscsi_name}' does not exist.")
        return iscsi_name

    def check_blk_name(self, ip, iqn):
        """Check if the block device name exists."""
        blk_name = self._find_unique_name("blk", ip, iqn)
        if blk_name not in self._created_devices:
            raise ValueError(f"Block device name '{blk_name}' does not exist.")
        return blk_name

    def print_all_device_names(self):
      """Print all device names."""
      if self._created_devices:
          LOG.warning("Device Names:")
          for device_name in self._created_devices:
              print(device_name)
      else:
          LOG.warning("No devices found.")
            
class RpcManager:
    """Manage RPC commands."""
    def __init__(self):
        self.device_manager = DeviceManager()

    # instance: nbl_stor_rpc.py bdev_iscsi_create -b <iscsi00> -i <iqn.2016-06.io.spdk:disk1/0> --url <iscsi://T_ip/iqn.2016-06.io.spdk:disk1/0>
    def execute_rpc_create_iscsi_bdev(self, iqn, ip):
        """Execute the RPC command to create iSCSI bdev."""
        iscsi_value = self.device_manager.get_iscsi_name(ip, iqn)
        cmd = ['nbl_stor_rpc.py', 'bdev_iscsi_create', '-b', iscsi_value, '-i', iqn + '/0', '--url', f'iscsi://{ip}/{iqn}/0']
        try:
            stdout, stderr = execute(*cmd)
            LOG.info(stdout)
            if stderr:
                raise RpcCommandError(f"Error executing bdev_iscsi_create command. Error: {stderr}", {'stdout': stdout, 'stderr': stderr})
            
            self.device_manager.add_device_name(iscsi_value)
            return iscsi_value
        except Exception as e:  
            msg = f"Failed to execute bdev_iscsi_create command for IQN {iqn} and IP {ip}: {e}"
            LOG.error(msg)
            raise RpcCommandError(msg, {'stdout': '', 'stderr': str(e)})

    # instance: nbl_rpc.py emulator_virtio_blk_device_create --name <blk00> --cpumask 0x2 --num_queues 1 --bdev_name <iscsixx> --rom_idx 0
    def execute_rpc_emulator_virtio_blk_device_create(self, iscsi_value, ip, iqn):
        """Execute the RPC command to create emulator virtio block device."""
        blk_value = self.device_manager.get_blk_name(ip, iqn)
        cmd = [
            'nbl_rpc.py',
            'emulator_virtio_blk_device_create',
            '--name',
            blk_value,
            '--cpumask',
            '0x2',
            '--num_queues',
            '1',
            '--bdev_name',
            iscsi_value,
            '--rom_idx',
            '0'
        ]
        try:
            stdout, stderr = execute(*cmd)
            LOG.info(stdout)
            if stderr:
                raise RpcCommandError(f"Error executing emulator_virtio_blk_device_create command. Error: {stderr}", {'stdout': stdout, 'stderr': stderr})
            
            self.device_manager.add_device_name(blk_value)
            return blk_value
        except Exception as e: 
            msg = f"Failed to execute emulator_virtio_blk_device_create command for iscsi_value {iscsi_value}: {e}"
            LOG.error(msg)
            raise RpcCommandError(msg, {'stdout': '', 'stderr': str(e)})

    def execute_rpc_emulator_virtio_blk_device_delete(self, blk_name):
        """Execute the RPC command to delete emulator virtio block device."""
        cmd = ['nbl_rpc.py', 'emulator_virtio_blk_device_delete', '--name', blk_name]
        try:
            stdout, stderr = execute(*cmd)
            LOG.info(stdout)
            if stderr:
                raise RpcCommandError(f"Error executing emulator_virtio_blk_device_delete command. Error: {stderr}", {'stdout': stdout, 'stderr': stderr})
            self.device_manager.remove_device_name(blk_name)  
        except Exception as e:
            msg = f"Failed to execute emulator_virtio_blk_device_delete command for block device name {blk_name}: {e}"
            LOG.error(msg)
            raise RpcCommandError(msg, {'stdout': '', 'stderr': str(e)})

    def execute_rpc_bdev_iscsi_delete(self, iscsi_name):
        """Execute the RPC command to delete iSCSI bdev."""
        cmd = ['nbl_stor_rpc.py', 'bdev_iscsi_delete', iscsi_name]
        try:
            stdout, stderr = execute(*cmd)
            LOG.info(stdout)
            if stderr:
                raise RpcCommandError(f"Error executing bdev_iscsi_delete command. Error: {stderr}", {'stdout': stdout, 'stderr': stderr})
            self.device_manager.remove_device_name(iscsi_name)
        except Exception as e:
            msg = f"Failed to execute bdev_iscsi_delete command for iSCSI name {iscsi_name}: {e}"
            LOG.error(msg)
            raise RpcCommandError(msg, {'stdout': '', 'stderr': str(e)})

class CloudDiskExtension(base.BaseAgentExtension):
    """Cloud disk extension for handling cloud disk related commands."""
    def __init__(self, agent=None):
        super(CloudDiskExtension, self).__init__(agent=agent)
        self.rpc_manager = RpcManager()

    @base.sync_command('connect_cloud_disk')
    def connect_cloud_disk(self, iqn, ip):
        """Connect cloud disk using the given iqn and ip."""
        iscsi_value = None
        blk_value = None
        try:
            LOG.info("Received IP: %s", ip)
            LOG.info("Received IQN: %s", iqn)
          
            # Step 1: Create iSCSI bdev
            iscsi_value = self.rpc_manager.execute_rpc_create_iscsi_bdev(iqn, ip)
            
            # Step 2: Create emulator virtio block device
            blk_value = self.rpc_manager.execute_rpc_emulator_virtio_blk_device_create(iscsi_value, ip, iqn)
            
            LOG.info(f"Successfully connected cloud disk for IP {ip} and IQN {iqn}.")
            return {'result': 'Cloud disk connected successfully.'}
        except RpcCommandError as e:
            msg = f"Failed to connect cloud disk for IP {ip} and IQN {iqn}: {e}"
            LOG.error(msg)
            raise BadRequest('Cloud disk connection failed.') # Real scene on, virtual scene off
            #return {'result': 'Cloud disk connection failed.', 'error': str(e)} # Real scene off, virtual scene on
        except ValueError as ve:
            LOG.error(ve)
            raise BadRequest('Command failed with error')     # Real scene on, virtual scene off
            #return {"status": f"Command failed with error: {str(ve)}"}  # Real scene off, virtual scene on
        finally:      
            if iscsi_value and not blk_value:
               LOG.warning(f"Rolling back due to error. Deleting iSCSI bdev: {iscsi_value}")
               try:
                    self.rpc_manager.execute_rpc_bdev_iscsi_delete(iscsi_value)
               except Exception as rollback_err:
                    LOG.error(f"Error during rollback operation: {rollback_err}")

    @base.sync_command('disconnect_cloud_disk')
    def disconnect_cloud_disk(self, iqn, ip):
        """Disconnect cloud disk using the given iqn and ip."""
        try:

            self.print_all_devices()
            LOG.info("Received IP: %s", ip)
            LOG.info("Received IQN: %s", iqn)

            # Step 1: Get the block device name
            blk_name = self.rpc_manager.device_manager.check_blk_name(ip, iqn)
            
            # Step 2: Delete emulator virtio block device
            self.rpc_manager.execute_rpc_emulator_virtio_blk_device_delete(blk_name)
            
            # Step 3: Get the iSCSI name
            iscsi_name = self.rpc_manager.device_manager.check_iscsi_name(ip, iqn)
            time.sleep(10)
            # Step 4: Delete iSCSI bdev
            self.rpc_manager.execute_rpc_bdev_iscsi_delete(iscsi_name)
            
            LOG.info(f"Successfully disconnected cloud disk for IP {ip} and IQN {iqn}.")
            return {'result': 'Cloud disk disconnected successfully.'}
        except RpcCommandError as e:
            msg = f"Failed to disconnect cloud disk for IP {ip} and IQN {iqn}: {e}"
            LOG.error(msg)
            raise BadRequest('Cloud disk disconnection failed.') # Real scene on, virtual scene off
            #return {'result': 'Cloud disk disconnection failed.', 'error': str(e)}  # Real scene off, virtual scene on
        except ValueError as ve:
            LOG.error(ve)
            raise BadRequest('Command failed with error.') # Real scene on, virtual scene off
            #return {"status": f"Command failed with error: {str(ve)}"}  # Real scene off, virtual scene on
            
    @base.async_command('check_heartbeat')
    def check_heartbeat(self, ip):
        """Disconnect cloud disk using the given iqn and ip."""
  
        LOG.info("Received heartbeat from IP: %s", ip)     
        return {'result': 'Cloud disk heartbeat successfully.'}
        
    @base.async_command('print_all_devices')
    def print_all_devices(self):
        """Async command to print all device names."""
 
        if not self.rpc_manager.device_manager._created_devices:
            LOG.warning("No registered devices found.")
            return {'result': 'No device names to print.'}
    
        try:

            self.rpc_manager.device_manager.print_all_device_names()
            return {'result': 'Printed all device names successfully.'}
        except Exception as e:
            LOG.error(f"Error printing device names: {e}")
            return {'result': 'Failed to print device names.'}

