import unittest

from magazine.cli import parser


class CliTests(unittest.TestCase):
    def test_capture_requires_author_identity_mode(self):
        with self.assertRaises(SystemExit):
            parser().parse_args([
                "capture",
                "https://example.com/article",
                "--snapshot",
                "article.html",
                "--author",
                "A. Writer",
            ])

    def test_capture_accepts_provenance_backed_author_note(self):
        args = parser().parse_args([
            "capture",
            "https://example.com/article",
            "--snapshot",
            "article.html",
            "--author",
            "A. Writer",
            "--author-note",
            "A. Writer is chief architect at Example Company.",
            "--author-evidence",
            "https://example.com/author",
            "author.html",
        ])

        self.assertEqual(args.author, "A. Writer")
        self.assertEqual(
            args.author_evidence,
            [["https://example.com/author", "author.html"]],
        )

    def test_capture_accepts_explicit_institutional_author(self):
        args = parser().parse_args([
            "capture",
            "https://example.com/article",
            "--snapshot",
            "article.html",
            "--author",
            "Example Research",
            "--institutional-author",
        ])

        self.assertTrue(args.institutional_author)
        self.assertIsNone(args.author_note)
