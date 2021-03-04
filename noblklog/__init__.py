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

from .stream import AsyncStreamHandler
from .syslog import (
    AsyncSysLogHandler,
    SYSLOG_FORMAT_RFC3164,
    SYSLOG_FORMAT_RFC5424,
    SYSLOG_FRAMING_NON_TRANSPARENT,
    SYSLOG_FRAMING_OCTET_COUNTING,
)

__all__ = (
    'AsyncStreamHandler',
    'AsyncSysLogHandler',
    'SYSLOG_FORMAT_RFC3164',
    'SYSLOG_FORMAT_RFC5424',
    'SYSLOG_FRAMING_NON_TRANSPARENT',
    'SYSLOG_FRAMING_OCTET_COUNTING',
)
