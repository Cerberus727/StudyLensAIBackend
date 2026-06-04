from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from app.config import WEBSHARE_PROXY_USERNAME, WEBSHARE_PROXY_PASSWORD


def _build_api() -> YouTubeTranscriptApi:
    """
    Return a YouTubeTranscriptApi instance.
    If WebShare proxy credentials are configured (required on cloud deployments
    where YouTube blocks datacenter IPs), routes all requests through the proxy.
    Falls back to direct connection when running locally.
    """
    if WEBSHARE_PROXY_USERNAME and WEBSHARE_PROXY_PASSWORD:
        from youtube_transcript_api.proxies import WebshareProxyConfig
        return YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=WEBSHARE_PROXY_USERNAME,
                proxy_password=WEBSHARE_PROXY_PASSWORD,
            )
        )
    return YouTubeTranscriptApi()


def extract_video_id(url: str) -> str:
    parsed_url = urlparse(url)

    if parsed_url.hostname == "youtu.be":
        return parsed_url.path[1:]

    if parsed_url.hostname in ("www.youtube.com", "youtube.com"):
        return parse_qs(parsed_url.query)["v"][0]

    raise ValueError("Invalid YouTube URL")


def get_transcript_with_timestamps(youtube_url: str):
    video_id = extract_video_id(youtube_url)
    api = _build_api()

    transcript = api.fetch(video_id, languages=["en", "hi"])

    return [
        {"text": snippet.text, "start": snippet.start}
        for snippet in transcript
    ]


def get_transcript(youtube_url: str) -> str:
    video_id = extract_video_id(youtube_url)
    api = _build_api()

    transcript = api.fetch(video_id, languages=["hi", "en"])

    return " ".join(snippet.text for snippet in transcript)