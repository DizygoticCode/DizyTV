import re
import tomllib
import unittest
from pathlib import Path

from dizytv import __version__


class VersionTests(unittest.TestCase):
    def test_runtime_version_matches_project_alpha_version(self):
        project = tomllib.loads(
            (Path(__file__).resolve().parents[1] / 'pyproject.toml').read_text(encoding='utf-8')
        )
        expected = re.sub(r'a\d+$', '-alpha', project['project']['version'])
        self.assertEqual(expected, __version__)
