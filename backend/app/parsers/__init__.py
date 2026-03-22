from .twitter import parse_twitter_likes, parse_twitter_tweets, parse_twitter_bookmarks
from .linkedin import (
    parse_linkedin, parse_linkedin_reactions, parse_linkedin_comments,
    parse_linkedin_shares, parse_linkedin_saved,
)
from .reddit import parse_reddit
from .instagram import parse_instagram
from .chatgpt import parse_chatgpt
from .claude_export import parse_claude
from .facebook import (
    parse_facebook_likes, parse_facebook_pages, parse_facebook_posts,
    parse_facebook_comments, parse_facebook_group_posts,
    parse_facebook_group_comments, parse_facebook_other_pages_posts,
)
from .youtube import (
    parse_youtube_watch_history, parse_youtube_likes_json,
    parse_youtube_likes_csv, parse_youtube_playlist,
    parse_youtube_comments_html,
)

PARSERS = {
    "twitter_likes": parse_twitter_likes,
    "twitter_tweets": parse_twitter_tweets,
    "twitter_bookmarks": parse_twitter_bookmarks,
    "linkedin": parse_linkedin,
    "linkedin_reactions": parse_linkedin_reactions,
    "linkedin_comments": parse_linkedin_comments,
    "linkedin_shares": parse_linkedin_shares,
    "linkedin_saved": parse_linkedin_saved,
    "reddit": parse_reddit,
    "instagram": parse_instagram,
    "chatgpt": parse_chatgpt,
    "claude": parse_claude,
    "facebook_likes": parse_facebook_likes,
    "facebook_pages": parse_facebook_pages,
    "facebook_posts": parse_facebook_posts,
    "facebook_comments": parse_facebook_comments,
    "facebook_group_posts": parse_facebook_group_posts,
    "facebook_group_comments": parse_facebook_group_comments,
    "facebook_other_pages": parse_facebook_other_pages_posts,
    "youtube_history": parse_youtube_watch_history,
    "youtube_likes_json": parse_youtube_likes_json,
    "youtube_likes_csv": parse_youtube_likes_csv,
    "youtube_playlist": parse_youtube_playlist,
    "youtube_comments": parse_youtube_comments_html,
}
