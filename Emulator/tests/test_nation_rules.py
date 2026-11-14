"""EU rules (user, 2026-11-14): only the V-grade part system and the battle zone / channel battle rules tied to it
differ from US, and the stats (no points for the player's level) and the drops (by V grade); emulator.ini's [nation] lines say the same."""
import asyncio
import configparser
import os
import struct
import unittest
from unittest import mock

from dcemu.native import auth, context, nation
from dcemu.wire import Frame

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIFFER = {'part_level', 'part_grade', 'battle_levels', 'level_points', 'drop_by_grade'}


class NationRulesTest(unittest.TestCase):
    def check(self, rules):
        self.assertEqual(set(rules['us']), set(rules['eu']))
        differ = {k for k in rules['us'] if rules['us'][k] != rules['eu'][k]}
        self.assertEqual(differ, DIFFER)
        self.assertTrue(rules['eu']['part_grade'])
        self.assertFalse(rules['eu']['part_level'])
        self.assertFalse(rules['eu']['battle_levels'])
        self.assertFalse(rules['eu']['level_points'])
        self.assertTrue(rules['us']['level_points'])
        self.assertTrue(rules['eu']['drop_by_grade'])

    def test_defaults(self):
        self.check(nation.RULES)

    def test_emulator_ini(self):
        cp = configparser.ConfigParser(inline_comment_prefixes=(';', '#'))
        cp.read(os.path.join(HERE, 'emulator.ini'))
        rules = {g: dict(r) for g, r in nation.RULES.items()}
        for key, value in cp['nation'].items():
            g, _, r = key.partition('.')
            if g in rules and r in rules[g]:
                rules[g][r] = value.strip() not in ('0', 'no', 'off')
        self.check(rules)


class Log:
    def note(self, text):
        pass


class Session:
    def __init__(self):
        self.state, self.log, self.sent = {}, Log(), []
        self.client_w = mock.Mock(get_extra_info=lambda k: ('127.0.0.1', 0))

    def to_client(self, frame):
        self.sent.append(frame)

    def close(self):
        pass


class LoginNationTest(unittest.TestCase):
    """The US client with the launcher's EU rules sends 0x7cf (nation 8) right behind its login; with allow = all the
    login is answered without waiting, and the account must still get the EU nation."""

    def setUp(self):
        self.saved = {k: getattr(context, k, None) for k in ('nation_allow', 'nation_forced', 'nation_eu_client',
                                                            'public_host', 'server_list')}
        context.nation_allow = context.nation_forced = None
        context.nation_eu_client = False
        context.public_host, context.server_list = '127.0.0.1', []
        nation._login_nation.clear()

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(context, k, v)
        nation._login_nation.clear()

    def login(self, send_nation):
        s = Session()

        async def check(member, password):
            if send_nation:              # the 0x7cf arrives while the password is checked
                await nation.nation(s, Frame(nation.NATION, struct.pack('<I', 8)))
            return auth.OK

        async def run():
            with mock.patch.object(auth, 'check_login', check), mock.patch.object(auth, 'ticket_for', lambda m: 1):
                await auth.answer_login(s, 'tester', b'secret'.ljust(0x40, b'\0'))
        asyncio.run(run())
        self.assertEqual(struct.unpack_from('<i', s.sent[0].payload, 4)[0], auth.OK)
        return nation.of_member('tester')

    def test_eu_rules_from_the_us_client(self):
        self.assertEqual(self.login(True), 8)
        self.assertTrue(nation.rule(type('P', (), {'nation': 8})(), 'part_grade'))

    def test_us_rules(self):
        self.assertEqual(self.login(False), nation.US)

    def test_texts_stay_us(self):
        p = type('P', (), {'nation': 8})()
        self.assertFalse(nation.eu_client(p))
        self.assertEqual(nation.login_result(8, auth.NO_ID, ''), auth.NO_ID)
        context.nation_eu_client = True
        self.assertTrue(nation.eu_client(p))
        self.assertEqual(nation.login_result(8, auth.NO_ID, ''), 2)


if __name__ == '__main__':
    unittest.main()
