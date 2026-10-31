"""CLI lifecycle regression without requiring MCP or a live model."""

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class ChatExitTests(unittest.TestCase):
    def test_terminal_exit_marks_customer_departure_and_closes_provider(self):
        provider = Mock()
        agent = Mock()
        agent.tools._providers = [provider]
        modules = {
            'agent.factory': SimpleNamespace(build_agent=Mock(return_value=agent)),
            'agent.settings': SimpleNamespace(load_settings=Mock(return_value=SimpleNamespace(logging=None))),
            'agent.logging_config': SimpleNamespace(setup_logging=Mock()),
        }
        path = Path(__file__).resolve().parents[1] / 'scripts/chat.py'
        with patch.dict(sys.modules, modules), patch.object(sys, 'argv', ['chat', 'u_demo_double']), patch('builtins.input', return_value='exit'):
            spec = importlib.util.spec_from_file_location('chat_exit_check', path)
            chat = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(chat)
            self.assertEqual(chat.main(), 0)
        agent.end.assert_called_once_with(user_left=True)
        provider.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
