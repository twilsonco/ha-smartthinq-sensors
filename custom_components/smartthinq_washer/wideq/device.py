"""A high-level, convenient abstraction for interacting with the LG
SmartThinQ API for most use cases.
"""
import requests
#import base64
import json
import datetime
from collections import namedtuple
import enum
import time
import logging
from typing import Any, Dict, Generator, List, Optional

from .core_exceptions import MonitorError

DEFAULT_TIMEOUT = 10 # seconds
DEFAULT_REFRESH_TIMEOUT = 20 # seconds

STATE_OPTIONITEM_ON = "On"
STATE_OPTIONITEM_OFF = "Off"
STATE_OPTIONITEM_UNKNOWN = "unknown"

OPTIONITEMMODES = {
    "ON": STATE_OPTIONITEM_ON,
    "OFF": STATE_OPTIONITEM_OFF,
    "unknown": STATE_OPTIONITEM_UNKNOWN,
}


class STATE_UNKNOWN(enum.Enum):
    UNKNOWN = STATE_OPTIONITEM_UNKNOWN


class DeviceType(enum.Enum):
    """The category of device."""
    REFRIGERATOR = 101
    KIMCHI_REFRIGERATOR = 102
    WATER_PURIFIER = 103
    WASHER = 201
    DRYER = 202
    STYLER = 203
    DISHWASHER = 204
    OVEN = 301
    MICROWAVE = 302
    COOKTOP = 303
    HOOD = 304
    AC = 401
    AIR_PURIFIER = 402
    DEHUMIDIFIER = 403
    ROBOT_KING = 501
    TV = 701
    BOILER = 801
    SPEAKER = 901
    HOMEVU = 902
    ARCH = 1001
    MISSG = 3001
    SENSOR = 3002
    SOLAR_SENSOR = 3102
    IOT_LIGHTING = 3003
    IOT_MOTION_SENSOR = 3004
    IOT_SMART_PLUG = 3005
    IOT_DUST_SENSOR = 3006
    EMS_AIR_STATION = 4001
    AIR_SENSOR = 4003
    PURICARE_AIR_DETECTOR = 4004
    V2PHONE = 6001
    HOMEROBOT = 9000
    UNKNOWN = STATE_OPTIONITEM_UNKNOWN


class PlatformType(enum.Enum):
    """The category of device."""
    THINQ1 = "thinq1"
    THINQ2 = "thinq2"
    UNKNOWN = STATE_OPTIONITEM_UNKNOWN


_LOGGER = logging.getLogger(__name__)


class Monitor(object):
    """A monitoring task for a device.
        
        This task is robust to some API-level failures. If the monitoring
        task expires, it attempts to start a new one automatically. This
        makes one `Monitor` object suitable for long-term monitoring.
        """

    def __init__(self, session, device_id: str) -> None:
        self.session = session
        self.device_id = device_id
    
    def start(self) -> None:
        self.work_id = self.session.monitor_start(self.device_id)
    
    def stop(self) -> None:
        self.session.monitor_stop(self.device_id, self.work_id)
    
    def poll(self) -> Optional[bytes]:
        """Get the current status data (a bytestring) or None if the
            device is not yet ready.
            """
        self.work_id = self.session.monitor_start(self.device_id)
        try:
            return self.session.monitor_poll(self.device_id, self.work_id)
        except MonitorError:
            # Try to restart the task.
            self.stop()
            self.start()
            return None

    @staticmethod
    def decode_json(data: bytes) -> Dict[str, Any]:
        """Decode a bytestring that encodes JSON status data."""
        
        return json.loads(data.decode('utf8'))
    
    def poll_json(self) -> Optional[Dict[str, Any]]:
        """For devices where status is reported via JSON data, get the
            decoded status result (or None if status is not available).
            """
        
        data = self.poll()
        return self.decode_json(data) if data else None
    
    def __enter__(self) -> 'Monitor':
        self.start()
        return self
    
    def __exit__(self, type, value, tb) -> None:
        self.stop()


class DeviceInfo(object):
    """Details about a user's device.
        
    This is populated from a JSON dictionary provided by the API.
    """
    def __init__(self, data: Dict[str, Any]) -> None:
        self.data = data

    def _get_data_key(self, keys):
        for key in keys:
            if key in self.data:
                return key
        return ""

    def _get_data_value(self, key):
        if isinstance(key, list):
            vkey = self._get_data_key(key)
        else:
            vkey = key

        return self.data.get(vkey, STATE_OPTIONITEM_UNKNOWN)

    @property
    def model_id(self) -> str:
        return self._get_data_value(['modelName', 'modelNm'])

    @property
    def id(self) -> str:
        return self._get_data_value('deviceId')
    
    @property
    def model_info_url(self) -> str:
        # for debug - this is a Washer ThinQ V2
        #return "https://objectstore.lgthinq.com/0dc06d18-81ce-4c7c-9ebc-6b2f6fd6b4bd?Expires=1645943733&Signature=hUkAOai3pKWk-O93foQxSVSPAaDHYT2vUDWxdPTd-FDype~Mr4pbfhAcSEDMu3rEixDBxE2l12ie6-czQMcPrjyxIiTojGxg~Mi~hC4zIzohrfqbgRKAJ-Hg2qd5~7Ge0uuK~6KJmxQeerI7BxedvXsP7aGmc2PloCWx7wtAPD1UsBzkrP6aACfRqQ3-0FnifULgiJenEfvJDQ6c6NjRLC0HYcdEG-vQOF~ZfslWUfyXTPNQBV~5c9mUO9J~CtPVLxRhrAvob-zbCyKhFiBw1ajRdmmRle9-mI0qjh3k58bC~5cAwzC-R~fbXuXj0GJcv-I8FXPO-Hic6AdFK44KgQ__&Key-Pair-Id=APKAI74R6YENXPGRIWLQ"
        # for debug - this is a Washer ThinQ V2
        return self._get_data_value(['modelJsonUrl', 'modelJsonUri'])
    
    @property
    def name(self) -> str:
        return self._get_data_value('alias')

    @property
    def macaddress(self) -> str:
        return self._get_data_value('macAddress')

    @property
    def model_name(self) -> str:
        return self._get_data_value(['modelName', 'modelNm'])

    @property
    def firmware(self) -> str:
        return self._get_data_value('fwVer')

    @property
    def devicestate(self) -> str:
        """The kind of device, as a `DeviceType` value."""
        return self._get_data_value('deviceState')

    @property
    def isonline(self) -> bool:
        """The kind of device, as a `DeviceType` value."""
        return self.data.get("online", False)

    @property
    def type(self) -> DeviceType:
        """The kind of device, as a `DeviceType` value."""
        return DeviceType(self._get_data_value('deviceType'))

    @property
    def platform_type(self) -> PlatformType:
        """The kind of device, as a `DeviceType` value."""
        # for debug
        #return PlatformType.THINQ2
        # for debug
        ptype = self.data.get('platformType')
        if not ptype:
            return PlatformType.THINQ1    # for the moment, probably not available in APIv1
        return PlatformType(ptype)

    @property
    def snapshot(self) -> Optional[Dict[str, Any]]:
        if "snapshot" in self.data:
            return self.data["snapshot"]
        return None

    def load_model_info(self):
        """Load JSON data describing the model's capabilities.
        """
        info_url = self.model_info_url
        if info_url == STATE_OPTIONITEM_UNKNOWN:
            return {}
        return requests.get(info_url, timeout = DEFAULT_TIMEOUT).json()


EnumValue = namedtuple('EnumValue', ['options'])
RangeValue = namedtuple('RangeValue', ['min', 'max', 'step'])
BitValue = namedtuple('BitValue', ['options'])
ReferenceValue = namedtuple('ReferenceValue', ['reference'])


class ModelInfo(object):
    """A description of a device model's capabilities.
        """
    
    def __init__(self, data):
        self.data = data

    @property
    def model_type(self):
        return self.data['Info']['modelType']
    
    def value_type(self, name):
        if name in self.data['Value']:
            return self.data['Value'][name]['type']
        else:
            return None

    def value(self, name):
        """Look up information about a value.
        
        Return either an `EnumValue` or a `RangeValue`.
        """
        d = self.data['Value'][name]
        if d['type'] in ('Enum', 'enum'):
            return EnumValue(d['option'])
        elif d['type'] == 'Range':
            return RangeValue(d['option']['min'], d['option']['max'], d['option']['step'])
        elif d['type'] == 'Bit':
            bit_values = {}
            for bit in d['option']:
                bit_values[bit['startbit']] = {
                'value' : bit['value'],
                'length' : bit['length'],
                }
            return BitValue(
                    bit_values
                    )
        elif d['type'] == 'Reference':
            ref =  d['option'][0]
            return ReferenceValue(
                    self.data[ref]
                    )
        elif d['type'] == 'Boolean':
            return EnumValue({'0': 'False', '1' : 'True'})
        elif d['type'] == 'String':
            pass 
        else:
            assert False, "unsupported value type {}".format(d['type'])


    def default(self, name):
        """Get the default value, if it exists, for a given value.
        """
            
        return self.data['Value'][name]['default']
        
    def enum_value(self, key, name):
        """Look up the encoded value for a friendly enum name.
        """
        
        options = self.value(key).options
        options_inv = {v: k for k, v in options.items()}  # Invert the map.
        return options_inv[name]

    def enum_name(self, key, value):
        """Look up the friendly enum name for an encoded value.
        """
        if not self.value_type(key):
            return str(value)
                
        options = self.value(key).options
        return options[value]

    def range_name(self, key):
        """Look up the value of a RangeValue.  Not very useful other than for comprehension
        """
            
        return key
        
    def bit_name(self, key, bit_index, value):
        """Look up the friendly name for an encoded bit value
        """
        if not self.value_type(key):
            return str(value)
        
        options = self.value(key).options
        
        if not self.value_type(options[bit_index]['value']):
            return str(value)
        
        enum_options = self.value(options[bit_index]['value']).options
        return enum_options[value]

    def reference_name(self, key, value):
        """Look up the friendly name for an encoded reference value
        """
        value = str(value)
        if not self.value_type(key):
            return value
                
        reference = self.value(key).reference
                    
        if value in reference:
            comment = reference[value]['_comment']
            return comment if comment else reference[value]['label']
        else:
            return '-'

    @property
    def binary_monitor_data(self):
        """Check that type of monitoring is BINARY(BYTE).
        """
        
        return self.data['Monitoring']['type'] == 'BINARY(BYTE)'
    
    def decode_monitor_binary(self, data):
        """Decode binary encoded status data.
        """
        
        decoded = {}
        for item in self.data['Monitoring']['protocol']:
            key = item['value']
            value = 0
            for v in data[item['startByte']:item['startByte'] + item['length']]:
                value = (value << 8) + v
            decoded[key] = str(value)
        return decoded
    
    def decode_monitor_json(self, data):
        """Decode a bytestring that encodes JSON status data."""
        
        return json.loads(data.decode('utf8'))
    
    def decode_monitor(self, data):
        """Decode  status data."""
        
        if self.binary_monitor_data:
            return self.decode_monitor_binary(data)
        else:
            return self.decode_monitor_json(data)

    def decode_snapshot(self, data, key):
        """Decode  status data."""
        return None


class ModelInfoV2(object):
    """A description of a device model's capabilities.
        """
    
    def __init__(self, data):
        self.data = data

    @property
    def model_type(self):
        return self.data['Info']['modelType']
    
    def value_type(self, name):
        if name in self.data['MonitoringValue']:
            return self.data['MonitoringValue'][name]['dataType']
        else:
            return None

    def value(self, name):
        """Look up information about a value.
        
        Return either an `EnumValue` or a `RangeValue`.
        """
        d = self.data['MonitoringValue'][name]
        if d['dataType'] in ('Enum', 'enum'):
            return d['valueMapping']
        elif d['dataType'] == 'range':
            return RangeValue(d['valueMapping']['min'], d['valueMapping']['max'])
        #elif d['dataType'] == 'Bit':
        #    bit_values = {}
        #    for bit in d['option']:
        #        bit_values[bit['startbit']] = {
        #        'value' : bit['value'],
        #        'length' : bit['length'],
        #        }
        #    return BitValue(
        #            bit_values
        #            )
        #elif d['dataType'] == 'Reference':
        #    ref =  d['option'][0]
        #    return ReferenceValue(
        #            self.data[ref]
        #            )
        #elif d['dataType'] == 'Boolean':
        #    return EnumValue({'0': 'False', '1' : 'True'})
        #elif d['dataType'] == 'String':
        #    pass
        else:
            assert False, "unsupported value type {}".format(d['type'])


    def default(self, name):
        """Get the default value, if it exists, for a given value.
        """
            
        return self.data['MonitoringValue'][name]['label']
        
    def enum_value(self, key, name):
        """Look up the encoded value for a friendly enum name.
        """

        options = self.value(key)
        options_inv = {v: k for k, v in options.items()}  # Invert the map.
        return options_inv[name]

    def enum_name(self, key, value):
        """Look up the friendly enum name for an encoded value.
        """
        if not self.value_type(key):
            return str(value)
                
        options = self.value(key)
        return options[value]["label"]

    def range_name(self, key):
        """Look up the value of a RangeValue.  Not very useful other than for comprehension
        """
        return key
        
    def bit_name(self, key, bit_index, value):
        """Look up the friendly name for an encoded bit value
        """
        return str(value)

    def reference_name(self, key, value):
        """Look up the friendly name for an encoded reference value
        """
        value = str(value)
        if not self.value_type(key):
            return value
                
        reference = self.value(key)
                    
        if value in reference:
            comment = reference[value].get('_comment')
            return comment if comment else reference[value]["label"]
        else:
            return '-'

    @property
    def binary_monitor_data(self):
        """Check that type of monitoring is BINARY(BYTE).
        """
        
        return self.data['Monitoring']['type'] == 'BINARY(BYTE)'
    
    def decode_monitor_binary(self, data):
        """Decode binary encoded status data.
        """
        
        decoded = {}
        for item in self.data['Monitoring']['protocol']:
            key = item['value']
            value = 0
            for v in data[item['startByte']:item['startByte'] + item['length']]:
                value = (value << 8) + v
            decoded[key] = str(value)
        return decoded
    
    def decode_monitor_json(self, data):
        """Decode a bytestring that encodes JSON status data."""
        
        return json.loads(data.decode('utf8'))
    
    def decode_monitor(self, data):
        """Decode  status data."""
        
        if self.binary_monitor_data:
            return self.decode_monitor_binary(data)
        else:
            return self.decode_monitor_json(data)
    
    def decode_snapshot(self, data, key):
        """Decode  status data."""
        return data.get(key)

class Device(object):
    """A higher-level interface to a specific device.
        
    Unlike `DeviceInfo`, which just stores data *about* a device,
    `Device` objects refer to their client and can perform operations
    regarding the device.
    """

    def __init__(self, client, device):
        """Create a wrapper for a `DeviceInfo` object associated with a
        `Client`.
        """

        self.client = client
        self.device = device
        model_data = client.model_info(device)
        if device.platform_type == PlatformType.THINQ2:
            self.model = ModelInfoV2(model_data)
        else:
            self.model = ModelInfo(model_data)
        self._should_poll = (device.platform_type == PlatformType.THINQ1)
        #self._should_poll = False
        
        # for logging unknown states received
        self._unknown_states = []

    def _set_control(self, key, value):
        """Set a device's control for `key` to `value`.
        """
        
        self.client.session.set_device_controls(
            self.device.id,
            {key: value},
            )
    
    def _get_config(self, key):
        """Look up a device's configuration for a given value.
            
        The response is parsed as base64-encoded JSON.
        """
        
        data = self.client.session.get_device_config(
               self.device.id,
               key,
        )
        return json.loads(base64.b64decode(data).decode('utf8'))
    
    def _get_control(self, key):
        """Look up a device's control value.
            """
        
        data = self.client.session.get_device_config(
               self.device.id,
                key,
               'Control',
        )

            # The response comes in a funky key/value format: "(key:value)".
        _, value = data[1:-1].split(':')
        return value

    def monitor_start(self):
        """Start monitoring the device's status."""
        if not self._should_poll:
            return
        mon = Monitor(self.client.session, self.device.id)
        mon.start()
        self.mon = mon

    def monitor_stop(self):
        """Stop monitoring the device's status."""
        if not self._should_poll:
            return
        self.mon.stop()

    def device_poll(self, snapshot_key=""):
        """Poll the device's current state.
        
        Monitoring must be started first with `monitor_start`. Return
        either a `Status` object or `None` if the status is not yet
        available.
        """
        
        # ThinQ V2 - Monitor data is with device info
        if not self._should_poll:
            snapshot = None
            self.client.refresh_devices()
            device_data = self.client.get_device(self.device.id)
            if device_data:
                snapshot = device_data.snapshot
            if not snapshot:
                return None
            res = self.model.decode_snapshot(snapshot, snapshot_key)

        # ThinQ V1 - Monitor data must be polled """
        else:
            # Abort if monitoring has not started yet.
            if not hasattr(self, 'mon'):
                return None
            data = self.mon.poll()
            if not data:
                return None
            res = self.model.decode_monitor(data)

        """
            with open('/config/wideq/washer_polled_data.json','w', encoding="utf-8") as dumpfile:
                json.dump(res, dumpfile, ensure_ascii=False, indent="\t")
        """
        return res

    def _delete_permission(self):
        self.client.session.delete_permission(
            self.device.id,
        )

    def is_unknown_status(self, status):
    
        if status in self._unknown_states:
            return False
            
        self._unknown_states.append(status)
        return True


class DeviceStatus(object):
    """A higher-level interface to a specific device status."""

    def __init__(self, device, data):
        self.device = device
        self.data = data

    def _get_data_key(self, keys):
        if isinstance(keys, list):
            for key in keys:
                if key in self.data:
                    return key
        elif keys in self.data:
            return keys

        return ""

    def set_unknown(self, state, key, type):
        if state:
            return state

        if self.device.is_unknown_status(key):
            _LOGGER.warning("Wideq: received unknown status '%s' of type '%s'", key, type)

        return STATE_UNKNOWN.UNKNOWN

    def lookup_enum(self, key):
        curr_key = self._get_data_key(key)
        if not curr_key:
            return STATE_OPTIONITEM_UNKNOWN
        return self.device.model.enum_name(curr_key, self.data[curr_key])

    def lookup_reference(self, key):
        curr_key = self._get_data_key(key)
        if not curr_key:
            return STATE_OPTIONITEM_UNKNOWN
        return self.device.model.reference_name(curr_key, self.data[curr_key])

    def lookup_bit(self, key, index):
        bit_value = int(self.data.get(key, -1))
        if bit_value == -1:
            return STATE_OPTIONITEM_UNKNOWN
        bit_value = int(self.data[key])
        bit_index = 2 ** index
        mode = bin(bit_value & bit_index)
        if mode == bin(0):
            return 'OFF'
        else:
            return 'ON'
