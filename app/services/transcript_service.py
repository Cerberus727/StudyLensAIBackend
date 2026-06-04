
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi

def extract_video_id(url: str) -> str:
    parsed_url = urlparse(url)

    if parsed_url.hostname == "youtu.be":
        return parsed_url.path[1:]

    if parsed_url.hostname in (
        "www.youtube.com",
        "youtube.com"
    ):
        return parse_qs(
            parsed_url.query
        )["v"][0]

    raise ValueError("Invalid YouTube URL")

def get_transcript_with_timestamps(
    youtube_url: str
):
    video_id = extract_video_id(
        youtube_url
    )

    ytt_api = YouTubeTranscriptApi()

    transcript = ytt_api.fetch(
        video_id,
        languages=["en", "hi"]
    )

    data = []

    for snippet in transcript:

        data.append(
            {
                "text": snippet.text,
                "start": snippet.start
            }
        )

    return data



def get_transcript(youtube_url: str) -> str:
    video_id = extract_video_id(youtube_url)

    ytt_api = YouTubeTranscriptApi()

    transcript = ytt_api.fetch(
        video_id,
        languages=["hi", "en"]
    )

    text = " ".join(
        snippet.text
        for snippet in transcript
    )

    return text