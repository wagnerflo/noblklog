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
        if default:
            default = ''.join(
                ch for ch in str(default)[:max_len] if 33 <= ord(ch) <= 126
            )
            break

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
    ''' Asynchronous logging handler for sending RFC 3164 or 5424
        compatible messages to Syslog.

        This handler only implements sending log messages to a local
        unix domain socket. Usually this is ``/dev/log`` to get them
        delivered to the local Syslog daemon. Delivering directly to
        remote destinations is not implemented as I see no need to
        increase code complexity when just about every Syslog daemon
        already supports forwarding messages.

        Traditionally Syslog uses UDP (:data:`~socket.SOCK_DGRAM`) for
        transport. This is usually also the case for delivery over the
        local Unix domain socket. Using a Datagram protocol has the
        advantage of keeping all messages seperate but limits the
        maximum message size. The protcol limit is usually not a problem
        as Syslog daemons set smaller limits by default.

        In addition to tuning your Syslog daemon you'll also need to
        to switch to a TCP / stream transport if you really want to go
        above the ~65k bytes message limit of UDP. Take a minute to also
        review the parameter ``message_framing`` and your Syslog
        daemon's settings if you go that way.

        This handler will encode messages contents in UTF-8. For RFC
        5424 this is the specified behaviour. For RFC 3164 this simply
        works usually. (That's all you can ever hope for the old
        Syslog protocol.)

        :param facility: Set the Syslog facility to send messages with.
                   See :meth:`~logging.handlers.SysLogHandler.encodePriority`
                   for possible values. Defaults to ``'user'``.
        :type facility: str

        :param hostname: Specify the default hostname to send messages
                   with. Defaults to the value returned by
                   :func:`socket.gethostname`. Individual messages can
                   overwrite this by passing
                   ``extra={'hostname': 'string}`` to the logging
                   method.
        :type hostname: str

        :param appname: Specify the default appname (or tag in RFC 3164
                   jargon) to send messages with. Defaults to ``'-'`` to
                   denote uspecified as per RFC 5424. Use
                   ``extra={'appname': 'string'}`` to overwrite this for
                   individual messages.
        :type appname: str

        :param procid: Specify the default process id to send with the
                   messages with. Defaults to ``'-'`` for RFC 5424 mode
                   and completly dropping the field for RFC 3164. Since
                   the :mod:`logging` module will be default pass the
                   result of :func:`os.getpid` for each message logged
                   and this handler will use the value there's usually
                   no reason to use this. Use
                   ``extra={'procid': 'string', ...}`` to overwrite this
                   for individual messages.
        :type procid: str

        :param structured_data: Reserved for future use.
        :param enterprise_id: Reserved for future use.

        :param socket_path: Path of the Unix domain socket to connect
                   and deliver messages to. On common Unix systems with
                   common configurations there's no need to use any
                   value but the default (``'/dev/log'``).
        :type socket_path: str

        :param socket_types: List of socket types to try connecting to
                   the Syslog socket with. The first type for which a
                   connection succeeds will be used. By default
                   :data:`~socket.SOCK_DGRAM` will be tried before
                   :data:`~socket.SOCK_STREAM`.
        :type socket_types: list

        :param message_format: Specify how to format the sent messages.
                   Usually you should use the default of
                   ``SYSLOG_FORMAT_RFC5424`` as this format is simply
                   much better. With ``SYSLOG_FORMAT_RFC3164`` you get
                   the predecessor that should work just about
                   everywhere but is much well defined.
        :type message_format: int

        :param message_framing: Tell's the handler how to delimit
                   messages on stream transports. For datagramm (UDP)
                   mode this parameter is ignored. The default value of
                   ``SYSLOG_FRAMING_NON_TRANSPARENT`` will simply end
                   each message with a newline character. This can break
                   if you're into logging newlines. Try using
                   ``SYSLOG_FRAMING_OCTET_COUNTING`` then but be warned
                   that some Syslog deamons might need configuration
                   changes or simply not support this mode.
        :type message_framing: int

        :param utf8_bom: Some RFC 5424 Syslog deamons will trip over the
                   UTF-8 byte order mark required by the standard. This
                   is obviously broken behaviour but since a workaround
                   is trivial here you go. Set this parameter to False
                   to write the message without a BOM between header and
                   content.
        :type utf8_bom: bool

        :param utc_timestamp: Send message timestamp as UTC instead of
                   localtime with timezone information. Will be ignored
                   in RFC 3164 mode. This can be useful if your log
                   messages originate in different timezones but some
                   component of your logging stack can't handle the
                   timezones in the Syslog timestamps.
        :type utc_timestamp:  bool
    '''

    def __init__(self,
                 facility='user',
                 hostname=None,
                 appname=None,
                 procid=None,
                 structured_data=None,
                 enterprise_id=None,
                 socket_path='/dev/log',
                 socket_types=[SOCK_DGRAM, SOCK_STREAM],
                 message_format=SYSLOG_FORMAT_RFC5424,
                 message_framing=SYSLOG_FRAMING_NON_TRANSPARENT,
                 utf8_bom=True,
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
            if (procid := self._get_procid(record)) is not None:
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
