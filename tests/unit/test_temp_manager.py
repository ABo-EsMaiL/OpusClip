from pathlib import Path

from opusclip.temp_manager import TempDir


class TestTempDirSuccess:
    def test_creates_temp_directory(self):
        with TempDir(prefix="opusclip_test_") as td:
            p = Path(td)
            assert p.exists()
            assert p.is_dir()

    def test_uses_custom_prefix(self):
        with TempDir(prefix="custom_prefix_") as td:
            assert td.name.startswith("custom_prefix_")

    def test_returns_path_object(self):
        with TempDir() as td:
            assert isinstance(td, Path)

    def test_cleanup_after_exit(self):
        td_path = None
        with TempDir() as td:
            td_path = Path(str(td))
            assert td_path.exists()
        assert not td_path.exists()

    def test_writable_directory(self):
        with TempDir() as td:
            test_file = td / "test.txt"
            test_file.write_text("hello", encoding="utf-8")
            assert test_file.exists()
            assert test_file.read_text(encoding="utf-8") == "hello"


class TestTempDirExceptionSafety:
    def test_cleanup_on_exception(self):
        td_path = None
        try:
            with TempDir() as td:
                td_path = Path(str(td))
                raise ValueError("test error")
        except ValueError:
            pass
        assert not td_path.exists()

    def test_default_prefix(self):
        with TempDir() as td:
            assert td.name.startswith("opusclip_")

    def test_reuse_prefix_for_cleanup(self):
        with TempDir(prefix="cleanup_test_") as td:
            (td / "temp_file.txt").write_text("data", encoding="utf-8")
        assert not td.exists()