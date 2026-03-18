import os
import logging
from datetime import datetime, timezone

import praw
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from .database import SessionLocal, engine
from .models import Base, RedditComment


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

TRACKED_PLAYERS = [
    "LeBron James",
    "Stephen Curry",
    "Nikola Jokic",
    "Luka Doncic",
    "Jayson Tatum",
]

SUBREDDITS = ["nba", "basketball"]

COMMENTS_LIMIT = 100


def get_reddit_client() -> praw.Reddit:
    client = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT"),
    )
    logger.info("Reddit client initialized (read-only mode)")
    return client


# Deduplication Check:
# Fetch all comment IDs already in PostgreSQL into set
# Before passing commnet to the HuggingFace model, check to see if it exists
def get_existing_comment_ids(db: Session) -> set[str]:
    results = db.query(RedditComment.comment_id).all()
    return {row.comment_id for row in results}


def scrape_player_comments(
    reddit: praw.Reddit,
    player_name: str,
    existing_ids: set[str],
    db: Session,
) -> list[RedditComment]:
    new_comments = []

    for subreddit_name in SUBREDDITS:
        logger.info(f"Scraping r/{subreddit_name} for '{player_name}'...")
        try:
            subreddit = reddit.subreddit(subreddit_name)
            # Search for posts mentioning the player, sorted by newest
            for submission in subreddit.search(
                player_name, sort="new", limit=10
            ):
                # Expand all comments in the thread (replace "load more")
                submission.comments.replace_more(limit=0)

                for comment in submission.comments.list()[:COMMENTS_LIMIT]:
                    if comment.id in existing_ids:
                        continue
                    if not comment.body or comment.body in [
                        "[deleted]", "[removed]"
                    ]:
                        continue
                    new_comment = RedditComment(
                        comment_id=comment.id,
                        player_name=player_name,
                        body=comment.body[:2000],
                        subreddit=subreddit_name,
                        score=comment.score,
                        created_utc=datetime.fromtimestamp(
                            comment.created_utc, tz=timezone.utc
                        ).replace(tzinfo=None),
                    )
                    db.add(new_comment)
                    existing_ids.add(comment.id)
                    new_comments.append(new_comment)

        except Exception as e:
            logger.error(f"Error scraping r/{subreddit_name} "
                         f"for {player_name}: {e}")
            continue

    # Commit all new comments to PostgreSQL in one transaction
    if new_comments:
        db.commit()
        for comment in new_comments:
            db.refresh(comment)
        logger.info(
            f"Inserted {len(new_comments)} new comments for '{player_name}'"
        )
    else:
        logger.info(f"No new comments found for '{player_name}' — skipping ML")

    return new_comments

# Create DB tables if they don't exist, scrapes all tracked players
# Returns all newly found comments across all players
def run_scraper() -> list[RedditComment]:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created")

    reddit = get_reddit_client()
    db = SessionLocal()
    all_new_comments = []

    try:
        existing_ids = get_existing_comment_ids(db)
        logger.info(
            f"Loaded {len(existing_ids)} existing comment IDs from database"
        )

        for player in TRACKED_PLAYERS:
            new_comments = scrape_player_comments(
                reddit, player, existing_ids, db
            )
            all_new_comments.extend(new_comments)

    finally:
        db.close()

    logger.info(
        f"Scraping complete. Total new comments this run: "
        f"{len(all_new_comments)}"
    )
    return all_new_comments


if __name__ == "__main__":
    run_scraper()