import pytest

from opusclip.input_validator import validate_video_path, validate_youtube_url
from opusclip.exceptions import InputValidationError


class TestValidateVideoPathSuccess:
    def test_valid_mp4(self, tmp_path):
        p = tmp_path / "video.mp4"
        p.write_bytes(b"\x00" * 10)
        result = validate_video_path(str(p))
        assert result == p.resolve()

    def test_valid_mkv(self, tmp_path):
        p = tmp_path / "video.mkv"
        p.write_bytes(b"\x00" * 10)
        result = validate_video_path(str(p))
        assert result.suffix == ".mkv"

    def test_valid_mov(self, tmp_path):
        p = tmp_path / "video.mov"
        p.write_bytes(b"\x00" * 10)
        result = validate_video_path(str(p))
        assert result.suffix == ".mov"

    def test_valid_avi(self, tmp_path):
        p = tmp_path / "video.avi"
        p.write_bytes(b"\x00" * 10)
        result = validate_video_path(str(p))
        assert result.suffix == ".avi"

    def test_resolves_symlink(self, tmp_path):
        target = tmp_path / "real.mp4"
        target.write_bytes(b"\x00" * 10)
        link = tmp_path / "link.mp4"
        link.symlink_to(target)
        result = validate_video_path(str(link))
        assert result == target.resolve()


class TestValidateVideoPathFailure:
    def test_file_does_not_exist(self):
        with pytest.raises(InputValidationError, match="does not exist"):
            validate_video_path("/nonexistent/video.mp4")

    def test_unsupported_extension(self, tmp_path):
        p = tmp_path / "video.txt"
        p.write_bytes(b"\x00" * 10)
        with pytest.raises(InputValidationError, match="Unsupported video extension"):
            validate_video_path(str(p))

    def test_path_is_directory(self, tmp_path):
        with pytest.raises(InputValidationError, match="not a file"):
            validate_video_path(str(tmp_path))

    def test_empty_path(self):
        with pytest.raises(InputValidationError):
            validate_video_path("")

    def test_no_extension(self, tmp_path):
        p = tmp_path / "video"
        p.write_bytes(b"\x00" * 10)
        with pytest.raises(InputValidationError, match="Unsupported video extension"):
            validate_video_path(str(p))


class TestValidateYouTubeUrlSuccess:
    def test_standard_youtube_com(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert validate_youtube_url(url) == url

    def test_short_youtu_be(self):
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert validate_youtube_url(url) == url

    def test_with_query_params(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30"
        assert validate_youtube_url(url) == url

    def test_https_required(self):
        url = "https://youtube.com/watch?v=abc123"
        assert validate_youtube_url(url) == url


class TestValidateYouTubeUrlFailure:
    def test_http_scheme_rejected(self):
        with pytest.raises(InputValidationError, match="URL scheme"):
            validate_youtube_url("ftp://youtube.com/watch?v=abc")

    def test_invalid_domain(self):
        with pytest.raises(InputValidationError, match="YouTube domain"):
            validate_youtube_url("https://vimeo.com/12345")

    def test_malformed_url(self):
        with pytest.raises(InputValidationError, match="URL scheme"):
            validate_youtube_url("not-a-url")

    def test_empty_url(self):
        with pytest.raises(InputValidationError):
            validate_youtube_url("")

    def test_no_scheme(self):
        with pytest.raises(InputValidationError, match="URL scheme"):
            validate_youtube_url("youtube.com/watch?v=abc")