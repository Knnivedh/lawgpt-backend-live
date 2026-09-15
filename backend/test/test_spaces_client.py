"""Regression coverage for downloaded Gradio TTS file outputs."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import spaces_client


class TTSAudioTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(spaces_client, '_tts_spaces', return_value=['primary', 'fallback'])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_primary_success_does_not_call_fallback(self):
        with patch.object(spaces_client, '_space_client', return_value=Mock()) as client, patch.object(
            spaces_client, '_read_tts_audio', return_value=b'audio'
        ):
            self.assertEqual(spaces_client.call_tts_space('text', 'voice'), b'audio')
        self.assertEqual(client.call_count, 1)
        self.assertEqual(client.call_args.args[0], 'primary')

    def test_fallback_on_quota_startup_and_invalid_audio(self):
        for error in (RuntimeError('GPU quota exceeded'), ConnectionError('sleeping'), ValueError('bad output')):
            directories = []
            clients = []

            def make_client(space, *, download_files):
                directories.append(download_files)
                path = Path(download_files) / 'audio.wav'
                path.write_bytes(b'fallback audio')
                client = Mock()
                if space == 'primary':
                    client.predict.side_effect = error
                else:
                    client.predict.return_value = str(path)
                clients.append(client)
                return client

            with self.subTest(error=error), patch.object(spaces_client, '_space_client', side_effect=make_client):
                self.assertEqual(spaces_client.call_tts_space('मुले बागेत', 'Calm voice'), b'fallback audio')
                for client in clients:
                    client.predict.assert_called_once_with(text='मुले बागेत', description='Calm voice', api_name='/generate_finetuned')
                self.assertEqual(len(clients), 2)
                self.assertTrue(all(not Path(directory).exists() for directory in directories))

    def test_both_failures_are_reported(self):
        with patch.object(spaces_client, '_space_client', side_effect=[RuntimeError('quota'), RuntimeError('offline')]):
            with self.assertRaisesRegex(RuntimeError, 'primary: quota; fallback: offline'):
                spaces_client.call_tts_space('text', 'voice')

    def test_empty_primary_audio_uses_fallback(self):
        with patch.object(spaces_client, '_space_client', return_value=Mock()), patch.object(
            spaces_client, '_read_tts_audio', side_effect=[b'', b'fallback']
        ):
            self.assertEqual(spaces_client.call_tts_space('text', 'voice'), b'fallback')

    def test_settings_overrides_and_duplicate_provider(self):
        from types import SimpleNamespace
        config = SimpleNamespace(get_settings=lambda: SimpleNamespace(
            indic_tts_space_url='custom/primary', tts_fallback_space_url='custom/primary'
        ))
        # Exercise the real helper despite the default provider mock in setUp.
        with patch.dict('sys.modules', {'config': config}):
            self.assertEqual(self.real_tts_spaces(), ['custom/primary'])

    real_tts_spaces = staticmethod(spaces_client._tts_spaces)

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
