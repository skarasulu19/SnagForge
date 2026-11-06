import tempfile
import unittest
from pathlib import Path
from branding import ICON,register_desktop_icon


class BrandingTests(unittest.TestCase):
    def test_launcher_keeps_custom_command_and_action_icons(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'snagforge.desktop'
            path.write_text('[Desktop Entry]\nName=SnagForge\nExec=custom-launcher --native\nIcon=camera-photo\n[Desktop Action Extra]\nIcon=other-icon\n')
            self.assertTrue(register_desktop_icon(directory))
            content=path.read_text()
            self.assertIn('Exec=custom-launcher --native',content)
            self.assertIn('Icon='+str(ICON),content);self.assertIn('Icon=other-icon',content)
    def test_new_launcher_uses_real_application_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(register_desktop_icon(directory))
            content=(Path(directory)/'snagforge.desktop').read_text()
            self.assertIn('Name=SnagForge',content);self.assertIn('Terminal=false',content)
            self.assertIn('Icon='+str(ICON),content)
    def test_unrelated_launcher_is_not_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'snagforge.desktop';original='[Desktop Entry]\nName=Another app\nIcon=keep\n'
            path.write_text(original)
            self.assertFalse(register_desktop_icon(directory));self.assertEqual(path.read_text(),original)
