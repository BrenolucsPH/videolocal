import unittest
from pathlib import Path

from videolocal.downloader import Choice, build_options
from videolocal.platforms import INSTAGRAM, TWITTER, YOUTUBE, parse_link


class ParseLinkTests(unittest.TestCase):
    def test_recognizes_each_platform(self):
        cases = {
            "https://www.youtube.com/watch?v=abc": YOUTUBE,
            "https://youtu.be/abc": YOUTUBE,
            "https://x.com/user/status/123": TWITTER,
            "https://mobile.twitter.com/user/status/123": TWITTER,
            "https://www.instagram.com/reel/Cabc/": INSTAGRAM,
            "https://www.instagram.com/p/Cabc/": INSTAGRAM,
        }
        for link, platform in cases.items():
            with self.subTest(link=link):
                self.assertEqual(parse_link(link)[1], platform)

    def test_normalizes_scheme(self):
        self.assertEqual(parse_link("x.com/user/status/1")[0], "https://x.com/user/status/1")
        self.assertEqual(parse_link(" http://youtu.be/abc ")[0], "https://youtu.be/abc")

    def test_rejects_lookalikes_and_junk(self):
        for link in (
            "",
            "texto qualquer",
            "https://youtube.com",  # sem caminho
            "https://youtube.com.evil.net/watch?v=abc",
            "https://notx.com/user/status/1",
            "https://evil.net/?u=instagram.com/reel/abc",
            "ftp://youtube.com/watch",
            "file:///C:/Windows/win.ini",
        ):
            with self.subTest(link=link):
                self.assertIsNone(parse_link(link))


class BuildOptionsTests(unittest.TestCase):
    dest = Path("saida")

    def test_video_mp4_limits_resolution_and_prefers_h264(self):
        opts = build_options(Choice("Vídeo", "MP4", "1080p"), TWITTER, self.dest, "C:/ff/ffmpeg.exe")
        self.assertEqual(opts["format"], "bv*+ba/b")
        self.assertEqual(opts["format_sort"][0], "res:1080")
        self.assertIn("vcodec:h264", opts["format_sort"])
        self.assertEqual(opts["merge_output_format"], "mp4")

    def test_best_quality_has_no_resolution_cap(self):
        opts = build_options(Choice("Vídeo", "MP4", "Melhor disponível"), YOUTUBE, self.dest, "C:/ff/ffmpeg.exe")
        self.assertFalse(any(s.startswith("res:") for s in opts["format_sort"]))

    def test_without_ffmpeg_asks_for_single_file(self):
        opts = build_options(Choice("Vídeo", "MP4", "720p"), INSTAGRAM, self.dest, "")
        self.assertEqual(opts["format"], "b")
        self.assertNotIn("ffmpeg_location", opts)

    def test_webm_only_applies_to_youtube(self):
        yt = build_options(Choice("Vídeo", "WEBM", "1080p"), YOUTUBE, self.dest, "C:/ff/ffmpeg.exe")
        ig = build_options(Choice("Vídeo", "WEBM", "1080p"), INSTAGRAM, self.dest, "C:/ff/ffmpeg.exe")
        self.assertEqual(yt["merge_output_format"], "webm/mkv")
        self.assertEqual(ig["merge_output_format"], "mp4")

    def test_audio_uses_extract_postprocessor(self):
        opts = build_options(Choice("Áudio", "MP3", "320 kbps"), YOUTUBE, self.dest, "C:/ff/ffmpeg.exe")
        pp = opts["postprocessors"][0]
        self.assertEqual((pp["key"], pp["preferredcodec"], pp["preferredquality"]), ("FFmpegExtractAudio", "mp3", "320"))

    def test_cookies_are_opt_in(self):
        without = build_options(Choice("Vídeo", "MP4", "720p"), INSTAGRAM, self.dest, "")
        with_cookies = build_options(Choice("Vídeo", "MP4", "720p"), INSTAGRAM, self.dest, "", "firefox")
        self.assertNotIn("cookiesfrombrowser", without)
        self.assertEqual(with_cookies["cookiesfrombrowser"], ("firefox",))


if __name__ == "__main__":
    unittest.main()
