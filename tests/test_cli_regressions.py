import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from amzsear import AmzProduct
from amzsear.cli import cli


class CliRegressionTest(unittest.TestCase):
    def test_run_single_string_argument_is_one_query(self):
        self.assertEqual(cli._coerce_argv(("Harry Potter",)), ["Harry Potter"])

    def test_select_treats_numeric_asin_as_asin_before_position(self):
        results = mock.Mock()
        product = AmzProduct.from_asin("1234567890")
        results.get.return_value = product

        selected = cli.select_product(results, "1234567890")

        self.assertIs(selected, product)
        results.get.assert_called_once_with("1234567890", raise_error=True)
        results.rget.assert_not_called()

    def test_region_is_case_insensitive(self):
        parser = cli.get_parser()

        args = parser.parse_args(["Harry Potter", "-r", "us"])

        self.assertEqual(args.region, "US")

    def test_page_must_be_positive(self):
        parser = cli.get_parser()

        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parser.parse_args(["Harry Potter", "-p", "0"])

    def test_product_fetch_failure_exits_nonzero_and_uses_stderr(self):
        def fail_fetch(product, level=None, region=None):
            product._set_fetch_error("blocked")
            return product

        stderr = io.StringIO()
        stdout = io.StringIO()
        with mock.patch.object(AmzProduct, "fetch_details", fail_fetch):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as cm:
                    cli.run(["--asin", "B000123456"])

        self.assertEqual(cm.exception.code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("blocked", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
