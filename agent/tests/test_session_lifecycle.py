"""Session finalization must remain stable while analytics watches saved files."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from agent.core.agent import AgentTurn, SupportAgent
from agent.core.session import Session


class SessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.agent = SupportAgent.__new__(SupportAgent)
        self.agent._ended = False
        self.agent.escalated = False
        self.agent.session = Session.start('u_demo_double', 'ses', 'Test prompt')
        self.agent.transcripts = Mock()

    def test_finalization_does_not_rewrite_completed_transcripts(self):
        self.agent.session.log('user', 'Goodbye')
        self.agent.end(user_left=True)
        self.agent.end()
        self.agent.transcripts.write.assert_called_once_with(self.agent.session, end_reason='user_left')
        with self.assertRaises(ValueError):
            self.agent.handle('Another turn')

    def test_empty_session_does_not_create_completed_transcript(self):
        self.agent.end()
        self.agent.transcripts.write.assert_not_called()

    def test_escalation_reason_takes_precedence_over_user_exit(self):
        self.agent.session.log('user', 'Please involve support')
        self.agent.escalated = True
        self.agent.end(user_left=True)
        self.agent.transcripts.write.assert_called_once_with(self.agent.session, end_reason='escalated')


if __name__ == '__main__':
    unittest.main()
