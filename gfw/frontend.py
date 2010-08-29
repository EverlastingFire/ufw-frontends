#
# frontend.py: Base frontend for ufw
#
# Copyright (C) 2010  Darwin M. Bautista <djclue917@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import ufw.common
import ufw.frontend
from ufw.util import valid_address

from gfw.i18n import _
from gfw.util import ANY_ADDR


def _error(msg, exit=True):
    raise ufw.common.UFWError(msg)

# Override the error function used by UFWFrontend
ufw.frontend.error = _error


class Frontend(ufw.frontend.UFWFrontend, object):

    def __init__(self):
        super(Frontend, self).__init__(False)

    @staticmethod
    def _get_ip_version(rule):
        """Determine IP version of rule.
        Extracted from ufw.parser.UFWCommandRule.parse
        """
        # Determine src type
        if rule.src == ANY_ADDR:
            from_type = 'any'
        else:
            from_type = ('v6' if valid_address(rule.src, '6') else 'v4')
        # Determine dst type
        if rule.dst == ANY_ADDR:
            to_type = 'any'
        else:
            to_type = ('v6' if valid_address(rule.dst, '6') else 'v4')
        # Figure out the type of rule (IPv4, IPv6, or both)
        if from_type == 'any' and to_type == 'any':
            ip_version = 'both'
        elif from_type != 'any' and to_type != 'any' and from_type != to_type:
            err_msg = _("Mixed IP versions for 'from' and 'to'")
            raise ufw.common.UFWError(err_msg)
        elif from_type != 'any':
            ip_version = from_type
        elif to_type != 'any':
            ip_version = to_type
        return ip_version

    def enable_ipv6(self, enable=True):
        conf = ('yes' if enable else 'no')
        self.backend.set_default(self.backend.files['defaults'], 'IPV6', conf)

    def reload(self):
        """Reload firewall"""
        if self.backend._is_enabled():
            self.set_enabled(False)
            self.set_enabled(True)
            return True
        else:
            return False

    def get_rules(self):
        """Returns a generator of processed rules"""
        app_rules = []
        for i, r in enumerate(self.backend.get_rules()):
            if r.dapp or r.sapp:
                t = r.get_app_tuple()
                if t in app_rules:
                    continue
                else:
                    app_rules.append(t)
            yield (i, r)

    def set_rule(self, rule, ip_version=None):
        """set_rule(rule, ip_version=None)

        Changes:
            * ip_version is optional
            * the recently added rule's position is reset
        """
        if ip_version is None:
            ip_version = self._get_ip_version(rule)
        rule = rule.dup_rule()
        # Fix any inconsistency
        if rule.sapp or rule.dapp:
            rule.set_protocol('any')
            if rule.sapp:
                rule.sport = rule.sapp
            if rule.dapp:
                rule.dport = rule.dapp
        # If trying to insert beyond the end, just set position to 0
        if rule.position and not self.backend.get_rule_by_number(rule.position):
            rule.set_position(0)
        res = super(Frontend, self).set_rule(rule, ip_version)
        # Reset the positions of the recently inserted rule and adjacent rules
        if rule.position:
            s = (rule.position - 2 if rule.position > 1 else 0)
            e = rule.position + 1
            for r in self.backend.get_rules()[s:e]:
                r.set_position(0)
        return res

    def update_rule(self, pos, rule):
        self.delete_rule(pos, True)
        if not rule.position:
            rule.set_position(pos)
        self.set_rule(rule)

    def move_rule(self, old, new):
        if old == new:
            return
        rule = self.backend.get_rule_by_number(old).dup_rule()
        self.delete_rule(old, True)
        rule.set_position(new)
        self.set_rule(rule)