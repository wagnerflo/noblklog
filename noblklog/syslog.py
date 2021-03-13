# Copyright 2021 Florian Wagner <florian@wagner-flo.net>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from logging import Handler
from logging.handlers import SysLogHandler
from math import modf
from os import stat
from socket import (
    gethostname,
    socket,
    AF_UNIX, SOCK_STREAM, SOCK_DGRAM,
)
from stat import S_ISSOCK
from time import gmtime,localtime,strftime
from .util import AsyncEmitMixin

SYSLOG_FORMAT_RFC3164 = 1
SYSLOG_FORMAT_RFC5424 = 2

SYSLOG_FRAMING_UNFRAMED        = 0
SYSLOG_FRAMING_NON_TRANSPARENT = 1
SYSLOG_FRAMING_OCTET_COUNTING  = 2

PRIORITY_MAP = {
    'alert':    SysLogHandler.LOG_ALERT,
    'crit':     SysLogHandler.LOG_CRIT,
    'critical': SysLogHandler.LOG_CRIT,
    'CRITICAL': SysLogHandler.LOG_CRIT,
    'debug':    SysLogHandler.LOG_DEBUG,
    'DEBUG':    SysLogHandler.LOG_DEBUG,
    'emerg':    SysLogHandler.LOG_EMERG,
    'err':      SysLogHandler.LOG_ERR,
    'error':    SysLogHandler.LOG_ERR,
    'ERROR':    SysLogHandler.LOG_ERR,
    'info':     SysLogHandler.LOG_INFO,
    'INFO':     SysLogHandler.LOG_INFO,
    'notice':   SysLogHandler.LOG_NOTICE,
    'panic':    SysLogHandler.LOG_EMERG,
    'warn':     SysLogHandler.LOG_WARNING,
    'warning':  SysLogHandler.LOG_WARNING,
    'WARNING':  SysLogHandler.LOG_WARNING,
}

MONTH_MAP = {
     1: 'Jan',
     2: 'Feb',
     3: 'Mar',
     4: 'Apr',
     5: 'May',
     6: 'Jun',
     7: 'Jul',
     8: 'Aug',
     9: 'Sep',
    10: 'Oct',
    11: 'Nov',
    12: 'Dec',
}

def encode_priority(facility, priority):
    if isinstance(priority, str):
        priority = PRIORITY_MAP.get(priority, SysLogHandler.LOG_WARNING)
    return (facility << 3) | priority

def mk_get_from_record(defaults, record_properties, max_len):
    for default in defaults:
        if not default:
            continue

        default = ''.join(
            ch for ch in str(default)[:max_len] if 33 <= ord(ch) <= 126
        )

    def func(record):
        for prop in record_properties:
            if (val := getattr(record, prop, None)):
                break

        if val is None:
            return default

        return ''.join(
            ch for ch in str(val)[:max_len] if 33 <= ord(ch) <= 126
        )

    return func

class AsyncSyslogHandler(AsyncEmitMixin, Handler):
    def __init__(self,
                 facility='user',
                 hostname=None,
                 appname=None,
                 procid=None,
                 structured_data=None,
                 enterprise_id=None,
                 socket_path='/dev/log',
                 socket_types=[SOCK_STREAM, SOCK_DGRAM],
                 message_format=SYSLOG_FORMAT_RFC5424,
                 message_framing=SYSLOG_FRAMING_NON_TRANSPARENT,
                 utf8_bom=False,
                 utc_timestamp=False):
        # first things first: try connecting
        if not S_ISSOCK(stat(socket_path).st_mode):
            raise Exception(f"Not a unix domain socket: '{socket_path}'")

        sock = self._try_connect(socket_path, socket_types)

        # prepare settings
        self._is_5424 = message_format == SYSLOG_FORMAT_RFC5424
        self._facility = SysLogHandler.facility_names[facility]
        self._get_hostname = mk_get_from_record(
            (hostname, gethostname()),
            ('hostname',),
            255
        )
        self._get_appname = mk_get_from_record(
            (appname, '-'),
            ('appname',),
            48
        )
        self._get_msgid = mk_get_from_record(
            (procid, '-'),
            ('msgid',),
            32
        )
        self._get_procid = mk_get_from_record(
            (procid, '-' if self._is_5424 else None),
            ('process', 'procid'),
            128
        )

        # prepare message assembly methods
        if sock.type == SOCK_STREAM:
            self._message_framing = message_framing
        else:
            self._message_framing = SYSLOG_FRAMING_UNFRAMED

        self._msg_encoding = \
            'utf-8-sig' if self._is_5424 and utf8_bom else 'utf8'
        self._sec_to_struct = \
            gmtime if self._is_5424 and utc_timestamp else localtime

        Handler.__init__(self)
        AsyncEmitMixin.__init__(self, sock.fileno(), sock.send)

    def prepareMessage(self, record):
        if self._is_5424:
            frac,stamp = modf(record.created)
            structured_data = '-'
            msg = bytearray(
                (
                    f'<{encode_priority(self._facility, record.levelname)}>'
                    f'1 '
                    f'{strftime("%Y-%m-%dT%H:%M:%S", self._sec_to_struct(stamp))}.'
                    f'{round(frac * 1e6):06d}Z '
                    f'{self._get_hostname(record)} '
                    f'{self._get_appname(record)} '
                    f'{self._get_procid(record)} '
                    f'{self._get_msgid(record)} '
                    f'{structured_data} '
                ).encode('ascii')
            )

        else:
            struct_time = self._sec_to_struct(record.created)
            msg = bytearray(
                (
                    f'<{encode_priority(self._facility, record.levelname)}>'
                    f'{MONTH_MAP[struct_time.tm_mon]} '
                    f'{strftime("%d %H:%M:%S", struct_time)} '
                    f'{self._get_hostname(record)} '
                    f'{self._get_appname(record)}'
                ).encode('ascii')
            )
            if (procid := self._get_procid) is not None:
                msg.extend(f'[{procid}]'.encode('ascii'))

        if record.msg:
            msg.extend(self.format(record).encode(self._msg_encoding))

        if self._message_framing == SYSLOG_FRAMING_NON_TRANSPARENT:
            msg.extend(b'\n')

        elif self._message_framing == SYSLOG_FRAMING_OCTET_COUNTING:
            msg[0:0] = f'{len(msg)} '.encode('ascii')

        return msg

    def _try_connect(self, path, types):
        exc = None
        for socket_type in types:
            try:
                sock = socket(AF_UNIX, socket_type)
                sock.setblocking(False)
                sock.connect(path)
                return sock
            except OSError as e:
                exc = e
                if e.errno != 91:
                    break
        raise exc
