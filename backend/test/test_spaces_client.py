"""Regression coverage for downloaded Gradio TTS file outputs."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import spaces_client


class TTSAudioTests(unittest.TestCase):
    def test_downloaded_audio_is_read_and_cleaned_up(self):
        directories = []

        def make_client(space, *, download_files):
            directories.append(download_files)
            path = Path(download_files) / 'audio.wav'
            path.write_bytes(b'RIFF-test-audio')
            from unittest.mock import Mock
            return Mock(predict=Mock(return_value=str(path)))

        with patch.object(spaces_client, '_space_client', side_effect=make_client), patch.object(
            spaces_client.httpx, 'Client'
        ) as http:
            self.assertEqual(spaces_client.call_tts_space('Hello', 'Clear voice'), b'RIFF-test-audio')
            http.assert_not_called()
        self.assertFalse(Path(directories[0]).exists())

    def test_space_authentication_for_supported_client_versions(self):
        from types import SimpleNamespace
        import inspect

        for keyword in ('token', 'hf_token'):
            def make_client(space, **kwargs):
                self.assertEqual(space, 'owner/space')
                self.assertEqual(kwargs[keyword], 'hf_test_only')
                self.assertEqual(kwargs['download_files'], '/tmp/output')
                return 'client'

            signature = inspect.Signature([
                inspect.Parameter(keyword, inspect.Parameter.KEYWORD_ONLY)
            ])
            config = SimpleNamespace(get_settings=lambda: SimpleNamespace(huggingface_api_key='hf_test_only'))
            with self.subTest(keyword=keyword), patch.dict('sys.modules', {'config': config}), patch.object(
                spaces_client, 'Client', side_effect=make_client
            ) as client, patch.object(spaces_client.inspect, 'signature', return_value=signature):
                self.assertEqual(spaces_client._space_client('owner/space', download_files='/tmp/output'), 'client')
                client.assert_called_once()

    def test_file_data_local_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'audio.wav'
            path.write_bytes(b'audio')
            self.assertEqual(spaces_client._read_tts_audio({'path': str(path), 'url': None}), b'audio')

    def test_remote_url_and_file_data_fallback(self):
        url = 'https://example.com/audio.wav'
        for result in [url, {'path': '/missing/audio.wav', 'url': url}]:
            with self.subTest(result=result), patch.object(spaces_client.httpx, 'Client') as client:
                client.return_value.__enter__.return_value.get.return_value = httpx.Response(
                    200, content=b'audio', request=httpx.Request('GET', url)
                )
                self.assertEqual(spaces_client._read_tts_audio(result), b'audio')

    def test_invalid_results_do_not_make_http_requests(self):
        for result in [None, {}, '/missing/audio.wav', {'url': '/gradio_api/file=audio.wav'}]:
            with self.subTest(result=result), patch.object(spaces_client.httpx, 'Client') as http:
                with self.assertRaisesRegex(ValueError, 'no readable audio'):
                    spaces_client._read_tts_audio(result)
                http.assert_not_called()


if __name__ == '__main__':
    unittest.main()
