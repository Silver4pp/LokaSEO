"""Uji berkas paket Windows: manifest, sumber daya versi, ikon, dan skrip build."""

import re
import sys
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lokaseo_desktop import config  # noqa: E402

DESKTOP = Path(__file__).resolve().parent.parent
ASSETS = DESKTOP / "assets"
# Alat pembangun dikumpulkan di satu folder supaya tidak bercampur dengan kode
# aplikasi; panduan pengguna hidup di docs/lokaseo bersama dokumentasi lain.
ALAT = DESKTOP / "alat"
REPO_ROOT = DESKTOP.parent
DOKUMEN = REPO_ROOT / "docs" / "lokaseo"


class PackagingTest(unittest.TestCase):
    def test_manifest_is_valid_xml_with_expected_settings(self):
        manifest = ASSETS / "lokaseo.manifest"
        tree = ElementTree.parse(manifest)
        text = manifest.read_text(encoding="utf-8")
        self.assertIn('level="asInvoker"', text, "aplikasi tidak boleh meminta hak admin")
        self.assertIn("permonitorv2", text, "skala tampilan tinggi perlu penanda DPI")
        self.assertEqual(tree.getroot().tag.endswith("assembly"), True)

    def test_version_info_matches_app_version(self):
        source = (ALAT / "version_info.txt").read_text(encoding="utf-8")
        compile(source, "version_info.txt", "exec")  # sintaks harus sah
        parts = tuple(int(piece) for piece in config.APP_VERSION.split("."))
        expected = f"filevers=({','.join(str(piece) for piece in parts + (0,))})"
        self.assertIn(expected, source.replace(" ", ""))
        self.assertIn(f'StringStruct("FileVersion", "{config.APP_VERSION}")', source)

    def test_package_json_version_matches(self):
        package = (REPO_ROOT / "package.json").read_text(encoding="utf-8")
        self.assertIn(f'"version": "{config.APP_VERSION}"', package)

    def test_icons_exist_and_have_multiple_sizes(self):
        ico = ASSETS / "lokaseo.ico"
        self.assertTrue(ico.is_file(), "ikon .ico diperlukan untuk EXE Windows")
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow tidak terpasang; ukuran ikon tidak diperiksa")
        with Image.open(ico) as image:
            sizes = sorted(image.info.get("sizes", []))
        self.assertIn((256, 256), sizes)
        self.assertGreaterEqual(len(sizes), 4)

    def test_spec_targets_windows_exe_names(self):
        spec = (ALAT / "lokaseo.spec").read_text(encoding="utf-8")
        self.assertIn('name="LokaSEO"', spec)
        self.assertIn('name="LokaSEO-console"', spec)
        self.assertIn('console=False', spec)
        self.assertIn("version_info.txt", spec)
        self.assertIn("lokaseo.manifest", spec)

    def test_build_script_and_usage_note_present(self):
        script = (ALAT / "build-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("PyInstaller", script)
        self.assertIn("Compress-Archive", script)
        self.assertIn("LICENSE", script)
        usage = (DOKUMEN / "cara-pakai-desktop.txt").read_text(encoding="utf-8")
        for phrase in ["127.0.0.1", "LICENSE.txt", "SmartScreen", "--offline", "system tray", "Hentikan LokaSEO"]:
            self.assertIn(phrase, usage)

    def test_windows_default_data_dir(self):
        paths = (DESKTOP / "lokaseo_desktop" / "paths.py").read_text(encoding="utf-8")
        self.assertIn("sys.platform.startswith(\"win\")", paths)
        self.assertIn("APPDATA", paths)
        self.assertIn("config.APP_NAME", paths)

    def test_workflow_builds_windows_artifact(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "loka-desktop.yml").read_text(encoding="utf-8")
        self.assertIn("runs-on: windows-latest", workflow)
        self.assertNotIn("macos-latest", workflow)
        self.assertNotIn("ubuntu-latest", workflow)
        self.assertIn("pywebview", workflow)
        self.assertIn("LokaSEO-Windows.zip", workflow)
        # Hanya membaca source dan mengunggah artefak.
        self.assertIn("contents: read", workflow)
        for forbidden in ["softprops/action-gh-release", "npm publish", "gh release"]:
            self.assertNotIn(forbidden, workflow)

    def test_workflow_has_no_hardcoded_secrets(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "loka-desktop.yml").read_text(encoding="utf-8")
        suspicious = re.findall(r"(?:sk-|ghp_|AKIA)[A-Za-z0-9]{6,}", workflow)
        self.assertEqual(suspicious, [], f"nilai menyerupai rahasia di workflow: {suspicious}")


if __name__ == "__main__":
    unittest.main()
